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
from ..monitor import get_monitor, HEAVY_TOOL_NAMES
from .analyst import AnalystOrchestrator

logger = logging.getLogger(__name__)

RESOURCE_PRESSURE_MESSAGE = "Recursos escassos, resposta pode demorar"

# Nomes de todas as tools disponíveis, exceto web_search (que é condicional)
DEFAULT_TOOLS = [
    "read_file",
    "run_python",
    "run_shell",
    "codebase_index",
    "firmware_check",
    "bandit_scan",
    "shellcheck_scan",
]


class AgentLoop:
    def __init__(self, llm_client: LLMClient, max_iterations: int = 6, analyst_max_iterations: int = 12, engineer_max_iterations: int = 4):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.analyst_max_iterations = analyst_max_iterations
        self.engineer_max_iterations = engineer_max_iterations

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
        enabled_tools: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        conv = messages.copy()

        # Inserir/atualizar system prompt com informações sobre tools.
        # Pulamos isso em modo analista: o AnalystOrchestrator usa seu próprio
        # protocolo (analyst_system.txt + blocos de código para verificação),
        # e misturar as duas instruções JSON confunde o modelo local.
        sys_msg = next((m for m in conv if m["role"] == "system"), None)
        if mode != "analyst":
            # Determinar quais tools serão listadas
            if enabled_tools is None:
                tool_names = [t.name for t in list_tools()]  # todas
            else:
                tool_names = [t for t in enabled_tools if t in [t.name for t in list_tools()]]

            tools = [get_tool(name) for name in tool_names if get_tool(name)]
            if tools:
                tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in tools])
                tool_instruction = (
                    "Você tem acesso às seguintes ferramentas. Se precisar executar uma ação, "
                    "responda com um JSON contendo o nome da tool e seus parâmetros. Caso contrário, "
                    "responda normalmente.\n\nFerramentas disponíveis:\n" + tools_desc
                )
            else:
                tool_instruction = "Você não tem ferramentas disponíveis para esta conversa."

            if sys_msg:
                sys_msg["content"] += "\n\n" + tool_instruction
            else:
                sys_msg = {"role": "system", "content": tool_instruction}
                conv.insert(0, sys_msg)
        elif not sys_msg:
            sys_msg = {"role": "system", "content": ""}
            conv.insert(0, sys_msg)

        # Injetar memória (arquitetural > conversacional > código), respeitando
        # memory_scope do projeto e o disjuntor use_saved_memory do perfil.
        # Passamos a mensagem do usuário para ativar RAG, se for o caso.
        user_message = next((m["content"] for m in reversed(conv) if m["role"] == "user"), None)
        try:
            memory_block = build_memory_context(
                project_id=project_id,
                chat_id=chat_id,
                user_message=user_message,
            )
        except Exception as e:
            logger.warning(f"Falha ao montar contexto de memória: {e}")
            memory_block = ""
        if memory_block:
            sys_msg["content"] += "\n\n" + memory_block

        return conv

    # ------------------------------------------------------------------
    # Monitoramento de recursos: decide se uma tool pesada deve ser pausada.
    # Compartilhado entre run() e run_stream().
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_tool_result(tool_name: str, params: Dict[str, Any], enabled_tools: Optional[List[str]] = None) -> ToolResult:
        """Executa a tool normalmente, a menos que seja uma tool pesada e o
        monitor de recursos esteja sinalizando pressão — nesse caso, a
        execução é pausada e o LLM recebe um erro claro em vez do resultado,
        podendo decidir como prosseguir (ex: tentar de novo mais tarde,
        avisar o usuário). Também verifica se a tool está habilitada."""
        if enabled_tools is not None and tool_name not in enabled_tools:
            return ToolResult(
                success=False,
                error=f"Ferramenta '{tool_name}' não está habilitada para esta conversa.",
            )
        if tool_name in HEAVY_TOOL_NAMES and get_monitor().is_under_pressure():
            return ToolResult(
                success=False,
                error=(
                    f"Tool '{tool_name}' pausada temporariamente: recursos do sistema "
                    "(RAM/CPU) estão sob pressão. Tente novamente em instantes."
                ),
            )
        tool = get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Ferramenta '{tool_name}' não encontrada.")
        return tool.run(**params)

    async def run(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        mode: Optional[str] = None,
        agent_type: Optional[str] = None,
        web_search: bool = False,
    ) -> str:
        """
        Executa o loop do agente (modo não-streaming):
        1. Envia mensagens para o LLM, incluindo a descrição das tools disponíveis.
        2. Se o LLM pedir uma tool, executa e adiciona o resultado ao histórico.
        3. Repete até resposta final ou limite de iterações.
        """
        # Definir quais tools estão habilitadas
        enabled_tools = DEFAULT_TOOLS.copy()
        if web_search:
            enabled_tools.append("web_search")

        conv = self._prepare_conversation(messages, project_id, chat_id, mode, enabled_tools)

        # Modo Analista: processo rigoroso de decomposição, múltiplos
        # candidatos, juiz, verificação por tools e checklists de domínio.
        # Troca latência por qualidade, sem depender de um modelo maior.
        if mode == "analyst":
            analyst = AnalystOrchestrator(llm_client=self.llm, max_iterations=self.analyst_max_iterations)
            return analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)

        # Modo engenheiro: usa o modelo local maior (opcional), se
        # configurado; caso contrário, o LLMClient já faz fallback para o
        # modelo padrão internamente (ver LLMClient._resolve_model).
        llm_model = "engineer" if mode == "engineer" else "default"
        max_iter = self.engineer_max_iterations if mode == "engineer" else self.max_iterations

        # Loop principal
        iteration = 0
        while iteration < max_iter:
            iteration += 1
            # Chamar LLM
            try:
                response = self.llm.generate(
                    messages=conv,
                    max_tokens=1024,
                    temperature=0.3,
                    model=llm_model,
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
                    result: ToolResult = self._resolve_tool_result(tool_name, params, enabled_tools)
                    # Adicionar resultado ao histórico
                    conv.append({"role": "assistant", "content": response})
                    conv.append({
                        "role": "user",
                        "content": f"Resultado da ferramenta {tool_name}: {result.data if result.success else f'Erro: {result.error}'}"
                    })
                    continue  # volta ao início do loop para nova iteração
            except json.JSONDecodeError:
                # Não é JSON, resposta final
                self._log_conversation(chat_id, project_id, conv, response)
                return response

        # Se chegou aqui, excedeu iterações
        return "Número máximo de iterações excedido. Por favor, refine sua pergunta."

    # ------------------------------------------------------------------
    # Versão streaming: mesmo protocolo/loop de tools, mas a última
    # iteração (a que não é uma tool call) tem seus tokens emitidos em
    # tempo real, conforme chegam do servidor LLM.
    #
    # Formato de saída: cada item gerado é um dict {"event": ..., "data": ...}
    # - {"event": "token", "data": "<fragmento de texto>"}: fragmento da
    #   resposta final, para acumular e exibir incrementalmente.
    # - {"event": "system", "data": "<mensagem>"}: aviso do sistema (ex:
    #   recursos sob pressão), a ser exibido separadamente (ex: notificação
    #   nativa no navegador), NUNCA concatenado à resposta do Hermes.
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
        show_thinking: bool = False,
        web_search: bool = False,
    ) -> AsyncIterator[Dict[str, str]]:
        """Além dos eventos "token"/"system" já existentes, quando
        show_thinking=True este gerador também emite eventos
        {"event": "thinking", "data": "<narrativa em linguagem natural>"}
        para cada etapa interna relevante (decomposição, tool calls,
        seleção de agente, etc.), narrando em tempo real o que hoje só ia
        para os logs JSON. É só narrativa — nunca é concatenada à resposta
        final do Hermes.
        """
        # Definir quais tools estão habilitadas
        enabled_tools = DEFAULT_TOOLS.copy()
        if web_search:
            enabled_tools.append("web_search")

        conv = self._prepare_conversation(messages, project_id, chat_id, mode, enabled_tools)

        def thought(text: str):
            return {"event": "thinking", "data": text}

        if show_thinking:
            if mode == "engineer":
                yield thought("Usando o modo engenheiro (modelo local maior)…")
            elif mode == "analyst":
                yield thought("Ativando o modo analista: decomposição, múltiplos candidatos e verificação rigorosa…")
            elif mode:
                yield thought(f"Selecionando o agente adequado para o modo \"{mode}\"…")
            else:
                yield thought("Selecionando o agente adequado para a mensagem…")

        # Aviso único de recursos sob pressão por chamada (evita repetir o
        # aviso a cada iteração do loop caso a pressão persista).
        pressure_warned = False
        if get_monitor().is_under_pressure():
            pressure_warned = True
            yield {"event": "system", "data": RESOURCE_PRESSURE_MESSAGE}
            if show_thinking:
                yield thought("Recursos (RAM/CPU) sob pressão — tools pesadas podem ser pausadas.")

        # Modo Analista: o processo de decomposição/múltiplos candidatos/juiz
        # roda por dentro de várias iterações e só produz o texto final ao
        # fim de tudo, então streaming token a token não se aplica. Mantemos
        # a rota /chat/stream funcional mesmo assim, emitindo a resposta
        # final como um único evento.
        if mode == "analyst":
            if show_thinking:
                yield thought("Decompondo o problema em subtarefas…")
                yield thought("Gerando soluções candidatas e aplicando o juiz interno…")
                yield thought("Verificando resultados com as tools disponíveis…")
            analyst = AnalystOrchestrator(llm_client=self.llm, max_iterations=self.analyst_max_iterations)
            final_text = analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)
            if show_thinking:
                yield thought("Escolhendo a melhor abordagem entre os candidatos avaliados…")
            yield {"event": "token", "data": final_text}
            return

        # Modo engenheiro: usa o modelo local maior (opcional), se
        # configurado; caso contrário, o LLMClient já faz fallback para o
        # modelo padrão internamente (ver LLMClient._resolve_model).
        llm_model = "engineer" if mode == "engineer" else "default"
        max_iter = self.engineer_max_iterations if mode == "engineer" else self.max_iterations

        iteration = 0
        while iteration < max_iter:
            iteration += 1

            # Se a pressão surgiu no meio do loop (ainda não avisada), avisa agora.
            if not pressure_warned and get_monitor().is_under_pressure():
                pressure_warned = True
                yield {"event": "system", "data": RESOURCE_PRESSURE_MESSAGE}
                if show_thinking:
                    yield thought("Recursos (RAM/CPU) sob pressão — tools pesadas podem ser pausadas.")

            if show_thinking and iteration > 1:
                yield thought(f"Iniciando iteração {iteration} do raciocínio…")

            try:
                token_iter = self.llm.generate_stream(
                    messages=conv,
                    max_tokens=1024,
                    temperature=0.3,
                    model=llm_model,
                )
            except Exception as e:
                logger.error(f"Erro no LLM (stream): {e}")
                yield {"event": "token", "data": f"Erro interno: {str(e)}"}
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
                        yield {"event": "token", "data": token}
            except Exception as e:
                logger.error(f"Erro durante streaming do LLM: {e}")
                yield {"event": "token", "data": f"\n[Erro durante a geração: {str(e)}]"}
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
                    yield {"event": "token", "data": response}
                    return

                if "tool" in data and "parameters" in data:
                    tool_name = data["tool"]
                    params = data["parameters"]
                    if show_thinking:
                        yield thought(f"Executando a ferramenta \"{tool_name}\"…")
                    result: ToolResult = self._resolve_tool_result(tool_name, params, enabled_tools)
                    if show_thinking:
                        yield thought(
                            f"Resultado de \"{tool_name}\": sucesso." if result.success
                            else f"Resultado de \"{tool_name}\": falhou ({result.error})."
                        )
                    conv.append({"role": "assistant", "content": response})
                    conv.append({
                        "role": "user",
                        "content": f"Resultado da ferramenta {tool_name}: {result.data if result.success else f'Erro: {result.error}'}"
                    })
                    continue  # próxima iteração do loop
                else:
                    # Era um JSON, mas não no formato de tool call esperado;
                    # trata como resposta final (ainda não emitida).
                    self._log_conversation(chat_id, project_id, conv, response)
                    yield {"event": "token", "data": response}
                    return
            else:
                # Resposta final: já foi transmitida token a token acima.
                self._log_conversation(chat_id, project_id, conv, response)
                return

        yield {"event": "token", "data": "Número máximo de iterações excedido. Por favor, refine sua pergunta."}

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