import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime

from ..llm import LLMClient
from ..tools.registry import get_tool, list_tools
from ..tools.base import ToolResult
from ..config import settings
from ..db import DATA_DIR
from .context_builder import build_memory_context
from ..monitor import get_monitor, HEAVY_TOOL_NAMES
from .analyst import AnalystOrchestrator
from .planner import Planner, Plan, PlanStep

logger = logging.getLogger(__name__)

RESOURCE_PRESSURE_MESSAGE = "Recursos escassos, resposta pode demorar"

DEFAULT_TOOLS = [
    "read_file",
    "run_python",
    "run_shell",
    "codebase_index",
    "firmware_check",
    "bandit_scan",
    "shellcheck_scan",
]

# ===================== PROMPTS ESPECÍFICOS POR AGENTE =====================
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_agent_prompt(agent_type: str) -> str:
    """Carrega o prompt específico do agente, se existir."""
    prompt_path = PROMPTS_DIR / f"{agent_type}_agent.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


class AgentLoop:
    def __init__(
        self,
        llm_client: LLMClient,
        max_iterations: int = 6,
        analyst_max_iterations: int = 12,
        engineer_max_iterations: int = 4
    ):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.analyst_max_iterations = analyst_max_iterations
        self.engineer_max_iterations = engineer_max_iterations
        self.planner = Planner(llm_client)

    # ------------------------------------------------------------------
    # Setup compartilhado: monta system prompt com tools e memória
    # ------------------------------------------------------------------
    def _prepare_conversation(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str],
        chat_id: Optional[str],
        mode: Optional[str],
        enabled_tools: Optional[List[str]] = None,
        agent_type: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        conv = messages.copy()

        sys_msg = next((m for m in conv if m["role"] == "system"), None)

        # Adicionar prompt específico do agente, se disponível
        agent_prompt = _load_agent_prompt(agent_type) if agent_type else ""
        if agent_prompt:
            if sys_msg:
                sys_msg["content"] += "\n\n" + agent_prompt
            else:
                sys_msg = {"role": "system", "content": agent_prompt}
                conv.insert(0, sys_msg)

        # Ferramentas (exceto no modo analyst)
        if mode != "analyst":
            if enabled_tools is None:
                tool_names = [t.name for t in list_tools()]
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

        # Injetar memória (com RAG)
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
    # Execução de tool com verificação de pressão
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_tool_result(
        tool_name: str,
        params: Dict[str, Any],
        enabled_tools: Optional[List[str]] = None
    ) -> ToolResult:
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

    # ------------------------------------------------------------------
    # Execução de um plano (modo não‑streaming)
    # ------------------------------------------------------------------
    def _execute_plan(
        self,
        plan: Plan,
        conv: List[Dict[str, str]],
        project_id: Optional[str],
        chat_id: Optional[str],
        mode: Optional[str],
        enabled_tools: List[str],
        max_iter: int,
        llm_model: str,
    ) -> str:
        """Executa os passos do plano sequencialmente. Retorna a resposta final."""
        final_parts = []

        while not plan.all_done():
            step = plan.get_next_step()
            if step is None:
                # Nenhum passo disponível (talvez todos em espera por dependências não satisfeitas)
                break

            step.status = "in_progress"
            logger.info(f"Executando passo: {step.description}")

            if step.tool:
                # Executa a tool definida no plano
                result = self._resolve_tool_result(step.tool, step.params, enabled_tools)
                if result.success:
                    step.status = "done"
                    step.result = result.data
                    final_parts.append(f"[Passo concluído] {step.description}\nResultado: {result.data}")
                else:
                    step.status = "failed"
                    step.error = result.error
                    # Tenta replanejar
                    logger.warning(f"Passo falhou: {step.error}. Replanejando...")
                    plan = self.planner.replan(
                        plan,
                        plan.current_step_index,
                        step.error,
                        conv[-1]["content"],
                        context="Erro durante execução do plano."
                    )
                    # Reinicia o loop
                    continue
            else:
                # Passo sem tool: chama o LLM para gerar conteúdo
                prompt = f"Execute o seguinte passo do plano: {step.description}\nContexto: {conv[-1]['content']}"
                try:
                    response = self.llm.generate(
                        messages=conv + [{"role": "user", "content": prompt}],
                        max_tokens=1024,
                        temperature=0.3,
                        model=llm_model,
                    )
                    step.status = "done"
                    step.result = response
                    final_parts.append(f"[Passo concluído] {step.description}\n{response}")
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    logger.warning(f"Passo falhou: {e}. Replanejando...")
                    plan = self.planner.replan(
                        plan,
                        plan.current_step_index,
                        str(e),
                        conv[-1]["content"],
                        context="Erro durante execução do passo."
                    )
                    continue

        if not final_parts:
            return "Nenhum passo foi executado com sucesso."

        # Monta a resposta final a partir dos resultados dos passos
        final_response = "\n\n".join(final_parts)
        return final_response

    # ------------------------------------------------------------------
    # Execução de um plano com streaming
    # ------------------------------------------------------------------
    async def _execute_plan_stream(
        self,
        plan: Plan,
        conv: List[Dict[str, str]],
        project_id: Optional[str],
        chat_id: Optional[str],
        mode: Optional[str],
        enabled_tools: List[str],
        max_iter: int,
        llm_model: str,
        show_thinking: bool,
    ) -> AsyncIterator[Dict[str, str]]:
        """Executa o plano emitindo eventos SSE para o frontend."""

        # Emite o plano completo no início
        plan_data = {
            "steps": [
                {
                    "index": i,
                    "description": s.description,
                    "tool": s.tool,
                    "status": s.status,
                }
                for i, s in enumerate(plan.steps)
            ]
        }
        yield {"event": "plan", "data": plan_data}

        while not plan.all_done():
            step = plan.get_next_step()
            if step is None:
                break

            step.status = "in_progress"
            yield {"event": "step_start", "data": {"index": plan.current_step_index, "description": step.description}}

            if show_thinking:
                yield {"event": "thinking", "data": f"Executando passo: {step.description}"}

            if step.tool:
                result = self._resolve_tool_result(step.tool, step.params, enabled_tools)
                if result.success:
                    step.status = "done"
                    step.result = result.data
                    yield {"event": "step_progress", "data": {"index": plan.current_step_index, "status": "done", "output": result.data}}
                    if show_thinking:
                        yield {"event": "thinking", "data": f"Passo concluído: {step.description}"}
                else:
                    step.status = "failed"
                    step.error = result.error
                    yield {"event": "step_failed", "data": {"index": plan.current_step_index, "error": result.error}}
                    # Replaneja
                    plan = self.planner.replan(
                        plan,
                        plan.current_step_index,
                        result.error,
                        conv[-1]["content"],
                        context="Erro durante execução do plano."
                    )
                    # Emite novo plano replanejado
                    new_plan_data = {
                        "steps": [
                            {"index": i, "description": s.description, "tool": s.tool, "status": s.status}
                            for i, s in enumerate(plan.steps)
                        ]
                    }
                    yield {"event": "plan", "data": new_plan_data}
                    continue
            else:
                # Passo sem tool: chama o LLM
                prompt = f"Execute o seguinte passo do plano: {step.description}\nContexto: {conv[-1]['content']}"
                try:
                    # Para streaming, usamos generate_stream para obter tokens
                    full_response = ""
                    for token in self.llm.generate_stream(
                        messages=conv + [{"role": "user", "content": prompt}],
                        max_tokens=1024,
                        temperature=0.3,
                        model=llm_model,
                    ):
                        full_response += token
                        # Emite token como parte do passo
                        yield {"event": "step_progress", "data": {"index": plan.current_step_index, "status": "in_progress", "token": token}}
                    step.status = "done"
                    step.result = full_response
                    yield {"event": "step_progress", "data": {"index": plan.current_step_index, "status": "done", "output": full_response}}
                    if show_thinking:
                        yield {"event": "thinking", "data": f"Passo concluído: {step.description}"}
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    yield {"event": "step_failed", "data": {"index": plan.current_step_index, "error": str(e)}}
                    plan = self.planner.replan(
                        plan,
                        plan.current_step_index,
                        str(e),
                        conv[-1]["content"],
                        context="Erro durante execução do passo."
                    )
                    # Emite novo plano replanejado
                    new_plan_data = {
                        "steps": [
                            {"index": i, "description": s.description, "tool": s.tool, "status": s.status}
                            for i, s in enumerate(plan.steps)
                        ]
                    }
                    yield {"event": "plan", "data": new_plan_data}
                    continue

        # Quando todos os passos estiverem concluídos, monta a resposta final
        final_parts = []
        for s in plan.steps:
            if s.status == "done" and s.result:
                final_parts.append(f"[{s.description}]\n{s.result}")
        if final_parts:
            final_text = "\n\n".join(final_parts)
            yield {"event": "token", "data": final_text}
        else:
            yield {"event": "token", "data": "Nenhum passo foi executado com sucesso."}

    # ------------------------------------------------------------------
    # Método run (não‑streaming)
    # ------------------------------------------------------------------
    async def run(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        mode: Optional[str] = None,
        agent_type: Optional[str] = None,
        web_search: bool = False,
        domain: Optional[str] = None,
    ) -> str:
        enabled_tools = DEFAULT_TOOLS.copy()
        if web_search:
            enabled_tools.append("web_search")
        if domain == "firmware":
            enabled_tools.append("ble_config")
        elif domain == "android":
            enabled_tools.append("gradle_build")
            enabled_tools.append("layout_validator")

        conv = self._prepare_conversation(
            messages, project_id, chat_id, mode, enabled_tools, agent_type=agent_type
        )

        # Modo Analista
        if mode == "analyst":
            analyst = AnalystOrchestrator(
                llm_client=self.llm,
                max_iterations=self.analyst_max_iterations,
                planner=self.planner
            )
            return analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)

        llm_model = "engineer" if mode == "engineer" else "default"
        max_iter = self.engineer_max_iterations if mode == "engineer" else self.max_iterations

        # Planejamento multi‑step para tarefas complexas
        user_message = next((m["content"] for m in reversed(conv) if m["role"] == "user"), "")
        if Planner.is_complex_task(user_message):
            logger.info("Tarefa complexa detectada. Gerando plano...")
            plan = self.planner.generate_plan(user_message, context=f"Projeto: {project_id or 'Nenhum'}")
            if len(plan.steps) > 1:
                # Executa o plano
                return self._execute_plan(plan, conv, project_id, chat_id, mode, enabled_tools, max_iter, llm_model)

        # Loop tradicional (sem plano ou plano de um passo)
        iteration = 0
        while iteration < max_iter:
            iteration += 1
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

            # Tentar interpretar como tool call
            try:
                data = json.loads(response)
                if "tool" in data and "parameters" in data:
                    tool_name = data["tool"]
                    params = data["parameters"]
                    if show_thinking:
                        pass  # (variável não existe neste método não-streaming)
                    result = self._resolve_tool_result(tool_name, params, enabled_tools)
                    conv.append({"role": "assistant", "content": response})
                    conv.append({
                        "role": "user",
                        "content": f"Resultado da ferramenta {tool_name}: {result.data if result.success else f'Erro: {result.error}'}"
                    })
                    continue
            except json.JSONDecodeError:
                self._log_conversation(chat_id, project_id, conv, response)
                return response

        return "Número máximo de iterações excedido. Por favor, refine sua pergunta."

    # ------------------------------------------------------------------
    # Método run_stream
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
        domain: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, str]]:
        enabled_tools = DEFAULT_TOOLS.copy()
        if web_search:
            enabled_tools.append("web_search")
        if domain == "firmware":
            enabled_tools.append("ble_config")
        elif domain == "android":
            enabled_tools.append("gradle_build")
            enabled_tools.append("layout_validator")

        conv = self._prepare_conversation(
            messages, project_id, chat_id, mode, enabled_tools, agent_type=agent_type
        )

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

        pressure_warned = False
        if get_monitor().is_under_pressure():
            pressure_warned = True
            yield {"event": "system", "data": RESOURCE_PRESSURE_MESSAGE}
            if show_thinking:
                yield thought("Recursos (RAM/CPU) sob pressão — tools pesadas podem ser pausadas.")

        # Modo Analista
        if mode == "analyst":
            if show_thinking:
                yield thought("Decompondo o problema em subtarefas…")
                yield thought("Gerando soluções candidatas e aplicando o juiz interno…")
                yield thought("Verificando resultados com as tools disponíveis…")
            analyst = AnalystOrchestrator(
                llm_client=self.llm,
                max_iterations=self.analyst_max_iterations,
                planner=self.planner
            )
            final_text = analyst.run(messages=conv, project_id=project_id, chat_id=chat_id)
            if show_thinking:
                yield thought("Escolhendo a melhor abordagem entre os candidatos avaliados…")
            yield {"event": "token", "data": final_text}
            return

        llm_model = "engineer" if mode == "engineer" else "default"
        max_iter = self.engineer_max_iterations if mode == "engineer" else self.max_iterations

        # Planejamento multi‑step para tarefas complexas (apenas se não for analyst)
        user_message = next((m["content"] for m in reversed(conv) if m["role"] == "user"), "")
        if Planner.is_complex_task(user_message):
            logger.info("Tarefa complexa detectada. Gerando plano com streaming...")
            plan = self.planner.generate_plan(user_message, context=f"Projeto: {project_id or 'Nenhum'}")
            if len(plan.steps) > 1:
                async for event in self._execute_plan_stream(
                    plan, conv, project_id, chat_id, mode, enabled_tools, max_iter, llm_model, show_thinking
                ):
                    yield event
                return

        # Loop tradicional com streaming
        iteration = 0
        while iteration < max_iter:
            iteration += 1

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
            is_tool_call: Optional[bool] = None

            try:
                for token in token_iter:
                    buffer += token
                    if is_tool_call is None:
                        stripped = buffer.lstrip()
                        if stripped:
                            is_tool_call = stripped.startswith("{")
                    if is_tool_call is False:
                        yield {"event": "token", "data": token}
            except Exception as e:
                logger.error(f"Erro durante streaming do LLM: {e}")
                yield {"event": "token", "data": f"\n[Erro durante a geração: {str(e)}]"}
                return

            response = buffer

            if is_tool_call:
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
                    result = self._resolve_tool_result(tool_name, params, enabled_tools)
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
                    continue
                else:
                    self._log_conversation(chat_id, project_id, conv, response)
                    yield {"event": "token", "data": response}
                    return
            else:
                self._log_conversation(chat_id, project_id, conv, response)
                return

        yield {"event": "token", "data": "Número máximo de iterações excedido. Por favor, refine sua pergunta."}

    def _log_conversation(self, chat_id, project_id, messages, final_response):
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
