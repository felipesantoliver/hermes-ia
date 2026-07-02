import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..llm import LLMClient
from ..tools.registry import get_tool, list_tools, to_llm_schema
from ..tools.base import ToolResult
from ..config import settings
from ..db import DATA_DIR
from ..memory.context_builder import build_memory_context

logger = logging.getLogger(__name__)

class AgentLoop:
    def __init__(self, llm_client: LLMClient, max_iterations: int = 6):
        self.llm = llm_client
        self.max_iterations = max_iterations

    async def run(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        mode: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> str:
        """
        Executa o loop do agente:
        1. Envia mensagens para o LLM, incluindo a descrição das tools disponíveis.
        2. Se o LLM pedir uma tool, executa e adiciona o resultado ao histórico.
        3. Repete até resposta final ou limite de iterações.
        """
        # Preparar sistema com tools
        tools = list_tools()
        tool_schemas = to_llm_schema(tools)
        # Adicionar mensagem do sistema com instruções sobre uso de tools (se houver)
        # Vamos modificar a lista de mensagens: a última mensagem do usuário será a pergunta atual.
        # Precisamos adicionar um system prompt especial para uso de tools.
        # Como já temos um system prompt, vamos adicionar instruções para usar tools.

        # Clonar mensagens para não modificar a original
        conv = messages.copy()

        # Inserir/atualizar system prompt com informações sobre tools
        sys_msg = next((m for m in conv if m["role"] == "system"), None)
        if sys_msg:
            sys_msg["content"] += "\n\nVocê tem acesso às seguintes ferramentas. Se precisar executar uma ação, responda com um JSON contendo o nome da tool e seus parâmetros. Caso contrário, responda normalmente."
        else:
            sys_msg = {"role": "system", "content": "Você tem acesso a ferramentas. Responda com JSON para usá-las ou texto normal para responder."}
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