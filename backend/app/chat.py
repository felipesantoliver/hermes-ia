# ===================== ROTAS DE CHAT =====================
# Responsabilidade: receber mensagens do frontend, orquestrar o agente,
# salvar mensagens e devolver a resposta.

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from .db import db_cursor, now_iso, new_id
from .orchestrator.loop import AgentLoop
from .orchestrator.router import select_agent
from .llm import LLMClient, get_llm_client
from .profile_prompt import build_profile_system_section

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: Optional[str] = None          # "code" ou "think"
    project_id: Optional[str] = None
    chat_id: str                        # obrigatório, pois já criamos antes


class ChatResponse(BaseModel):
    reply: str


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    llm: LLMClient = Depends(get_llm_client),
):
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

    # 4. Adicionar instruções/persona do projeto (se houver)
    if payload.project_id:
        with db_cursor() as cur:
            cur.execute("SELECT instructions, persona FROM projects WHERE id = ?", (payload.project_id,))
            proj = cur.fetchone()
            if proj:
                if proj["instructions"]:
                    system_prompt += f"\n\nInstruções do projeto: {proj['instructions']}"
                if proj["persona"]:
                    system_prompt += f"\n\nPersona do projeto: {proj['persona']}"

    # 5. Ajustar tom conforme mode
    if payload.mode == "code":
        system_prompt += "\n\nModo programação: foque em código, estrutura e soluções técnicas. Seja objetivo e evite divagações."
    elif payload.mode == "think":
        system_prompt += "\n\nModo pensador: explore o problema com raciocínio detalhado, considere alternativas e discuta implicações."

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

    # 8. Chamar o agente (orquestrador) usando o router para selecionar o agente adequado
    agent_type = select_agent(payload.mode, payload.message)
    # Criar o loop e executar
    loop = AgentLoop(llm_client=llm)
    result = await loop.run(
        messages=messages,
        project_id=payload.project_id,
        chat_id=payload.chat_id,
        mode=payload.mode,
        agent_type=agent_type,  # opcional, se o loop precisar
    )

    # 9. Salvar a resposta do Hermes no banco
    with db_cursor() as cur:
        mid = new_id()
        ts = now_iso()
        cur.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (mid, payload.chat_id, "hermes", result, ts)
        )
        cur.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (ts, payload.chat_id))

    return ChatResponse(reply=result)