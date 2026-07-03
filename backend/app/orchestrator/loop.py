import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
from ..llm import LLMClient
from ..tools.registry import get_tool, list_tools, to_llm_schema
from ..tools.base import ToolResult
from ..config import settings
from ..db import DATA_DIR
from ..memory.context_builder import build_memory_context
from .analyst import AnalystOrchestrator

logger = logging.getLogger(__name__)

class AgentLoop:
    def __init__(self, llm_client: LLMClient, max_iterations: int = 6, analyst_max_iterations: int = 12):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.analyst_max_iterations = analyst_max_iterations

    # ------------------------------------------------------------------
    # Setup compartilhado entre run() e run_stream(): monta o system prompt
    # com instruções de tools e injeta a memória. Retorna a lista de
    # mensagens pronta e a referência à mensagem de sistema (para o modo
    # analista poder ler o conteúdo base).
    # ------------------------------------------------------------------
    def _prepare_conversation(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str],
        chat_id: Optional[str],
        mode: Optional[str],
    ) -> List[Dict[str, str]]:
        conv = messages.copy()

        # Inserir/atualizar system prompt com informações sobre tools.
        # Pulamos isso em modo analista: o AnalystOrchestrator usa seu próprio
        # protocolo (analyst_system.txt + blocos de código para verificação),
        # e misturar as duas instruções JSON confunde o modelo local.
        sys_msg = next((m for m in conv if m["role"] == "system"), None)
        if mode != "analyst":
            if sys_msg:
                sys_msg["content"] += "\n\nVocê tem acesso às seguintes ferramentas. Se precisar executar uma ação, responda com um JSON contendo o nome da tool e seus parâmetros. Caso contrário, responda normalmente."
            else:
                sys_msg = {"role": "system", "content": "Você tem acesso a ferramentas. Responda com JSON para usá-las ou texto normal para responder."}
                conv.insert(0, sys_msg)
        elif not sys_msg:
            sys_msg = {"role": "system", "content": ""}
            conv.insert(0, sys_msg)

        # Injetar memória (arquitetural > conversacional > código), respeitando
        # memory_scope do projeto e o disjuntor use_saved_memory do perfil.
        try:
            memory_block = build_memory_context(project_id=project_id, chat_id=chat_id)
        except Exception as e:
            logger.warning(f"Falha ao montar contexto de memória: {e}")
            memory_block = ""
        if memory_block:
            sys_msg["content"] += "\n\n" + memory_block

        return conv

    async def run(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        mode: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> str:
        """
        Executa o loop do agente (modo não-streaming):
        1. Envia mensagens para o LLM, incluindo a descrição das tools disponíveis.
        2. Se o LLM pedir uma tool, executa e adiciona o resultado ao histórico.
        3. Repete até resposta final ou limite de iterações.
        """
        conv = self._prepare_conversation(messages, project_id, chat_id, mode)

        # Modo Analista: processo rigoroso de decomposição, múltiplos
        # candidatos, juiz, verificação por tools e checklists de domínio.
        # Troca latência por qualidade, sem depender de um modelo maior.
        if mode == "analyst":
            analyst = AnalystOrchestrator(llm_client=self.llm, max_iterations=self.analyst_max_iterations)
            return analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)

        # Loop principal
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            # Chamar LLM
            try:
                response = self.llm.generate(
                    messages=conv,
                    max_tokens=1024,
                    temperature=0.3,
                    # Passar tools se o servidor suportar function calling
                    # Por enquanto, vamos instruir o LLM a retornar JSON
                )
            except Exception as e:
                logger.error(f"Erro no LLM: {e}")
                return f"Erro interno: {str(e)}"

            # Tentar interpretar como JSON (tool call)
            try:
                data = json.loads(response)
                if "tool" in data and "parameters" in data:
                    tool_name = data["tool"]
                    params = data["parameters"]
                    tool = get_tool(tool_name)
                    if tool:
                        result: ToolResult = tool.run(**params)
                        # Adicionar resultado ao histórico
                        conv.append({"role": "assistant", "content": response})
                        conv.append({
                            "role": "user",
                            "content": f"Resultado da ferramenta {tool_name}: {result.data if result.success else f'Erro: {result.error}'}"
                        })
                        continue  # volta ao início do loop para nova iteração
                    else:
                        # Ferramenta não encontrada
                        conv.append({"role": "assistant", "content": response})
                        conv.append({"role": "user", "content": f"Ferramenta '{tool_name}' não encontrada."})
                        continue
            except json.JSONDecodeError:
                # Não é JSON, resposta final
                # Registrar log
                self._log_conversation(chat_id, project_id, conv, response)
                return response

        # Se chegou aqui, excedeu iterações
        return "Número máximo de iterações excedido. Por favor, refine sua pergunta."

    # ------------------------------------------------------------------
    # Versão streaming: mesmo protocolo/loop de tools, mas a última
    # iteração (a que não é uma tool call) tem seus tokens emitidos em
    # tempo real, conforme chegam do servidor LLM.
    #
    # Como o protocolo de tool call é "responda com um JSON", não dá para
    # saber de antemão se uma iteração vai virar tool call ou resposta
    # final. Estratégia: consumimos os primeiros caracteres do stream; se,
    # ignorando espaços em branco, a resposta começa com '{', tratamos como
    # possível tool call e NÃO emitimos nada ao usuário até o fim dessa
    # iteração (ela é resolvida internamente, como no modo não-streaming).
    # Caso contrário, é uma resposta final e cada token é repassado assim
    # que chega.
    # ------------------------------------------------------------------
    async def run_stream(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        mode: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> AsyncIterator[str]:
        conv = self._prepare_conversation(messages, project_id, chat_id, mode)

        # Modo Analista: o processo de decomposição/múltiplos candidatos/juiz
        # roda por dentro de várias iterações e só produz o texto final ao
        # fim de tudo, então streaming token a token não se aplica. Mantemos
        # a rota /chat/stream funcional mesmo assim, emitindo a resposta
        # final como um único evento.
        if mode == "analyst":
            analyst = AnalystOrchestrator(llm_client=self.llm, max_iterations=self.analyst_max_iterations)
            final_text = analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)
            yield final_text
            return

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            try:
                token_iter = self.llm.generate_stream(
                    messages=conv,
                    max_tokens=1024,
                    temperature=0.3,
                )
            except Exception as e:
                logger.error(f"Erro no LLM (stream): {e}")
                yield f"Erro interno: {str(e)}"
                return

            buffer = ""
            is_tool_call: Optional[bool] = None  # None = ainda indeterminado

            try:
                for token in token_iter:
                    buffer += token
                    if is_tool_call is None:
                        stripped = buffer.lstrip()
                        if stripped:
                            is_tool_call = stripped.startswith("{")
                    if is_tool_call is False:
                        # Resposta final sendo construída: repassa em tempo real
                        yield token
            except Exception as e:
                logger.error(f"Erro durante streaming do LLM: {e}")
                yield f"\n[Erro durante a geração: {str(e)}]"
                return

            response = buffer

            if is_tool_call:
                # Tenta interpretar como tool call. Se não for JSON válido,
                # cai para resposta final (não foi emitida ainda, então
                # emitimos de uma vez).
                try:
                    data = json.loads(response)
                except json.JSONDecodeError:
                    self._log_conversation(chat_id, project_id, conv, response)
                    yield response
                    return

                if "tool" in data and "parameters" in data:
                    tool_name = data["tool"]
                    params = data["parameters"]
                    tool = get_tool(tool_name)
                    if tool:
                        result: ToolResult = tool.run(**params)
                        conv.append({"role": "assistant", "content": response})
                        conv.append({
                            "role": "user",
                            "content": f"Resultado da ferramenta {tool_name}: {result.data if result.success else f'Erro: {result.error}'}"
                        })
                        continue  # próxima iteração do loop
                    else:
                        conv.append({"role": "assistant", "content": response})
                        conv.append({"role": "user", "content": f"Ferramenta '{tool_name}' não encontrada."})
                        continue
                else:
                    # Era um JSON, mas não no formato de tool call esperado;
                    # trata como resposta final (ainda não emitida).
                    self._log_conversation(chat_id, project_id, conv, response)
                    yield response
                    return
            else:
                # Resposta final: já foi transmitida token a token acima.
                self._log_conversation(chat_id, project_id, conv, response)
                return

        yield "Número máximo de iterações excedido. Por favor, refine sua pergunta."

    def _log_conversation(self, chat_id, project_id, messages, final_response):
        """Salva log em JSON lines."""
        log_dir = Path(DATA_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        if project_id:
            log_file = log_dir / f"{project_id}.jsonl"
        else:
            log_file = log_dir / "_solo.jsonl"

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "chat_id": chat_id,
            "project_id": project_id,
            "messages": messages,
            "final_response": final_response
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")