# ===================== ROTAS DE CHAT =====================
# Responsabilidade: receber mensagens do frontend, orquestrar o agente,
# salvar mensagens e devolver a resposta (via JSON ou via stream SSE).

import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncIterator

from .db import db_cursor, now_iso, new_id
from .orchestrator.loop import AgentLoop
from .orchestrator.router import select_agent
from .orchestrator.analyst import should_use_analyst_mode
from .llm import LLMClient, get_llm_client
from .profile_prompt import build_profile_system_section

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: Optional[str] = None          # "code", "engineer" ou "analyst"
    project_id: Optional[str] = None
    chat_id: str                        # obrigatório, pois já criamos antes
    show_thinking: bool = False         # ativa o streaming do raciocínio interno ("thinking")


class ChatResponse(BaseModel):
    reply: str


async def _build_chat_context(payload: ChatRequest) -> dict:
    """Valida o chat/projeto, monta o system prompt (perfil + projeto + modo)
    e o histórico de mensagens. Usado tanto pela rota /chat/ quanto por
    /chat/stream, para manter os dois fluxos idênticos exceto na entrega
    da resposta.
    """
    # 1. Validar que o chat existe
    with db_cursor() as cur:
        cur.execute("SELECT * FROM chats WHERE id = ?", (payload.chat_id,))
        chat = cur.fetchone()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat não encontrado")

        # Verificar se o project_id bate (se fornecido)
        if payload.project_id:
            if chat["project_id"] != payload.project_id:
                raise HTTPException(status_code=400, detail="project_id não corresponde ao chat")
        else:
            # Se não foi passado project_id, usar o do chat (se houver)
            if chat["project_id"]:
                payload.project_id = chat["project_id"]

    # 2. Carregar perfil do usuário (para system prompt)
    with db_cursor() as cur:
        cur.execute("SELECT * FROM user_profile WHERE id = 1")
        profile = cur.fetchone()

    # 3. Construir system prompt base
    system_prompt = "Você é o Hermes, um assistente de IA local focado em engenharia e desenvolvimento. " \
                    "Sua missão é ajudar o usuário a construir software, firmware e sistemas. " \
                    "Responda de forma clara, técnica e direta."

    # Adicionar seção derivada do perfil do usuário (nome, apelido, sobre,
    # personalidade, acolhimento/entusiasmo/emojis, filtro de conteúdo) —
    # inclui sempre o piso de segurança fixo, mesmo sem perfil configurado.
    profile_dict = dict(profile) if profile else None
    system_prompt += "\n\n" + build_profile_system_section(profile_dict)

    # 4. Adicionar instruções/persona do projeto (se houver) — 404 se o projeto não existir
    if payload.project_id:
        with db_cursor() as cur:
            cur.execute("SELECT instructions, persona FROM projects WHERE id = ?", (payload.project_id,))
            proj = cur.fetchone()
            if not proj:
                raise HTTPException(status_code=404, detail="Projeto não encontrado")
            if proj["instructions"]:
                system_prompt += f"\n\nInstruções do projeto: {proj['instructions']}"
            if proj["persona"]:
                system_prompt += f"\n\nPersona do projeto: {proj['persona']}"

    # 5. Ajustar tom conforme mode
    if payload.mode == "code":
        system_prompt += "\n\nModo programação: foque em código, estrutura e soluções técnicas. Seja objetivo e evite divagações."
    elif payload.mode == "engineer":
        system_prompt += "\n\nModo engenheiro: explore o problema com raciocínio detalhado, considere alternativas e discuta implicações, usando o modelo local maior quando disponível."

    # 5b. Heurística de escalonamento para o Modo Analista: se o chip "analyst"
    # não estiver ativo mas o perfil pedir alto rigor (personalidade "técnico"
    # ou filtro de conteúdo >= 3), o orquestrador sobe para modo analista
    # internamente. O chip da UI não é alterado — isso é invisível ao usuário.
    effective_mode = payload.mode
    if should_use_analyst_mode(payload.mode, profile_dict):
        effective_mode = "analyst"

    # 6. Buscar histórico de mensagens (até as últimas 10 para contexto)
    with db_cursor() as cur:
        cur.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT 10",
            (payload.chat_id,)
        )
        history = list(cur.fetchall())
        history.reverse()  # ordem cronológica

    # 7. Montar lista de mensagens para o LLM
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    # Adicionar a mensagem atual do usuário (já foi salva, mas vamos adicionar para garantir)
    messages.append({"role": "user", "content": payload.message})

    # 8. Selecionar o agente adequado (classificador híbrido: embeddings + heurística)
    agent_type = select_agent(payload.mode, payload.message)

    return {
        "messages": messages,
        "effective_mode": effective_mode,
        "agent_type": agent_type,
        "project_id": payload.project_id,
    }


def _save_hermes_reply(chat_id: str, reply: str) -> None:
    with db_cursor() as cur:
        mid = new_id()
        ts = now_iso()
        cur.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (mid, chat_id, "hermes", reply, ts)
        )
        cur.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (ts, chat_id))


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    llm: LLMClient = Depends(get_llm_client),
):
    ctx = await _build_chat_context(payload)

    loop = AgentLoop(llm_client=llm)
    result = await loop.run(
        messages=ctx["messages"],
        project_id=ctx["project_id"],
        chat_id=payload.chat_id,
        mode=ctx["effective_mode"],
        agent_type=ctx["agent_type"],
    )

    _save_hermes_reply(payload.chat_id, result)

    return ChatResponse(reply=result)


async def _sse_event_stream(payload: ChatRequest, llm: LLMClient) -> AsyncIterator[str]:
    """Gera os eventos SSE (text/event-stream) para a rota /chat/stream.

    Eventos emitidos:
      event: token    data: {"token": "..."}        -> um fragmento de texto
      event: thinking data: {"token": "..."}        -> um fragmento do
                                                         raciocínio interno
                                                         (só quando
                                                         payload.show_thinking
                                                         é True), nunca
                                                         concatenado à
                                                         resposta final
      event: system   data: {"message": "..."}      -> aviso do sistema (ex:
                                                         recursos sob pressão),
                                                         nunca concatenado à
                                                         resposta do Hermes
      event: error    data: {"error": "..."}        -> erro durante a geração
      event: done     data: {}                        -> fim do stream (sucesso)
    """
    try:
        ctx = await _build_chat_context(payload)
    except HTTPException as e:
        err_payload = json.dumps({"error": e.detail}, ensure_ascii=False)
        yield f"event: error\ndata: {err_payload}\n\n"
        return

    loop = AgentLoop(llm_client=llm)
    full_response = ""

    try:
        async for item in loop.run_stream(
            messages=ctx["messages"],
            project_id=ctx["project_id"],
            chat_id=payload.chat_id,
            mode=ctx["effective_mode"],
            agent_type=ctx["agent_type"],
            show_thinking=payload.show_thinking,
        ):
            event_type = item.get("event", "token")
            data = item.get("data", "")
            if event_type == "system":
                sys_payload = json.dumps({"message": data}, ensure_ascii=False)
                yield f"event: system\ndata: {sys_payload}\n\n"
                continue
            if event_type == "thinking":
                # Narrativa do raciocínio interno: nunca entra em full_response.
                thinking_payload = json.dumps({"token": data}, ensure_ascii=False)
                yield f"event: thinking\ndata: {thinking_payload}\n\n"
                continue
            full_response += data
            token_payload = json.dumps({"token": data}, ensure_ascii=False)
            yield f"event: token\ndata: {token_payload}\n\n"
    except Exception as e:
        err_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {err_payload}\n\n"
        return

    # Salva a resposta completa no banco, igual ao fluxo não-stream
    if full_response:
        _save_hermes_reply(payload.chat_id, full_response)

    yield "event: done\ndata: {}\n\n"


@router.post("/stream")
async def chat_stream_endpoint(
    payload: ChatRequest,
    llm: LLMClient = Depends(get_llm_client),
):
    """Mesmo ChatRequest da rota /chat/, mas devolve a resposta como um
    stream SSE (text/event-stream), token a token, conforme o LLM gera.
    No modo analista o streaming interno é desabilitado (a resposta só
    fica pronta após todas as iterações), mas o endpoint continua
    funcionando: a resposta final é enviada como um único evento "token".
    """
    return StreamingResponse(
        _sse_event_stream(payload, llm),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # evita buffering em proxies tipo nginx
        },
    )