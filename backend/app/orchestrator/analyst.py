import json
import logging
import random
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ..tools.registry import get_tool
from ..tools.base import ToolResult
from ..monitor import get_monitor, HEAVY_TOOL_NAMES
from ..db import DATA_DIR
from .planner import Plan, PlanStep

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CHECKLISTS_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "checklists"

ANALYST_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "analyst_system.txt"

MAX_SUBTASKS = 4
MAX_TOOL_RETRIES = 2

CODE_FENCE_RE = re.compile(r"```(python|py|bash|sh|shell)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _load_analyst_system_prompt() -> str:
    try:
        return ANALYST_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("analyst_system.txt não encontrado, usando fallback mínimo.")
        return (
            "ANALYST MODE: decompose the task, generate multiple candidates, "
            "critique, judge, verify with tools and refine before answering."
        )


def _load_checklists() -> List[Dict[str, Any]]:
    checklists = []
    if not CHECKLISTS_DIR.exists():
        return checklists
    for path in sorted(CHECKLISTS_DIR.glob("*.json")):
        try:
            checklists.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"Falha ao carregar checklist {path}: {e}")
    return checklists


def _select_checklists(task_text: str, checklists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = task_text.lower()
    selected = [c for c in checklists if any(kw in text for kw in c.get("applies_when", []))]
    return selected


def _extract_code_block(text: str) -> Optional[Dict[str, str]]:
    match = CODE_FENCE_RE.search(text)
    if not match:
        return None
    lang = (match.group(1) or "").lower()
    code = match.group(2)
    return {"lang": lang, "code": code}


def should_use_analyst_mode(mode: Optional[str], profile: Optional[Dict[str, Any]]) -> bool:
    if mode == "analyst":
        return True
    if not profile:
        return False
    if profile.get("personality") == "tecnico":
        return True
    filter_level = profile.get("content_filter_level")
    if isinstance(filter_level, int) and filter_level >= 3:
        return True
    return False


class AnalystOrchestrator:
    def __init__(
        self,
        llm_client,
        max_iterations: int = 12,
        engineer_client=None,
        planner=None
    ):
        self.llm = llm_client
        self.engineer_client = engineer_client
        self.max_iterations = max_iterations
        self._iterations_used = 0
        self._log_entries: List[Dict[str, Any]] = []
        self.planner = planner  # Planejador multi‑step, opcional

    # ------------------------------------------------------------------
    # Entrada principal
    # ------------------------------------------------------------------
    def run(
        self,
        messages: List[Dict[str, str]],
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        plan: Optional[Plan] = None,
    ) -> str:
        conv = messages.copy()
        base_system = next((m for m in conv if m["role"] == "system"), None)
        base_system_content = base_system["content"] if base_system else ""

        analyst_prompt = _load_analyst_system_prompt()
        combined_system = analyst_prompt + "\n\n---\n\n" + base_system_content
        analyst_conv = [{"role": "system", "content": combined_system}] + [
            m for m in conv if m["role"] != "system"
        ]

        user_task = next((m["content"] for m in reversed(analyst_conv) if m["role"] == "user"), "")

        self._log("start", {"project_id": project_id, "chat_id": chat_id, "task": user_task})

        # Se um plano foi fornecido (pelo planejador multi‑step), usamos seus passos como subtarefas
        if plan is not None and len(plan.steps) > 1:
            subtasks = [step.description for step in plan.steps if step.status != "done"]
            logger.info(f"Usando plano com {len(subtasks)} subtarefas para o modo analista.")
        else:
            subtasks = self._decompose(analyst_conv, user_task)

        checklists_all = _load_checklists()
        applicable_checklists = _select_checklists(user_task, checklists_all)

        subtask_results: List[Dict[str, str]] = []
        for subtask in subtasks:
            if self._iterations_used >= self.max_iterations:
                self._log("budget_exhausted", {"remaining_subtasks": subtask})
                break
            result = self._solve_subtask(analyst_conv, subtask)
            subtask_results.append({"subtask": subtask, "solution": result["solution"], "evidence": result["evidence"]})

        final_text = self._integrate(analyst_conv, user_task, subtask_results, applicable_checklists)

        self._write_log(project_id, chat_id)
        return final_text

    # ------------------------------------------------------------------
    # Passo a) Decomposição (usada apenas se não houver plano)
    # ------------------------------------------------------------------
    def _decompose(self, conv: List[Dict[str, str]], user_task: str) -> List[str]:
        prompt = (
            "Decomponha a tarefa do usuário acima em uma lista de subtarefas "
            "independentes, ordenadas por dependência. Responda APENAS com um "
            "array JSON de strings, sem nenhum texto antes ou depois. Se a "
            f"tarefa já for atômica, retorne um array com um único item. Máximo de {MAX_SUBTASKS} itens."
        )
        call_messages = conv + [{"role": "user", "content": prompt}]
        raw = self._call_llm(call_messages, temperature=0.3, max_tokens=512)
        subtasks = self._parse_json_list(raw)
        if not subtasks:
            subtasks = [user_task]
        subtasks = subtasks[:MAX_SUBTASKS]
        self._log("decomposition", {"subtasks": subtasks, "raw": raw})
        return subtasks

    @staticmethod
    def _parse_json_list(raw: str) -> List[str]:
        text = raw.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        candidate = match.group(0) if match else text
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except json.JSONDecodeError:
            pass
        lines = [l.strip("-*• ").strip() for l in text.splitlines() if l.strip()]
        return lines[:MAX_SUBTASKS] if lines else []

    # ------------------------------------------------------------------
    # Passo b) Loop por subtarefa
    # ------------------------------------------------------------------
    def _solve_subtask(self, conv: List[Dict[str, str]], subtask: str) -> Dict[str, str]:
        candidates = self._generate_candidates(conv, subtask)
        critiques = [self._self_critique(conv, subtask, c) for c in candidates]
        chosen_idx, justification = self._judge(conv, subtask, candidates, critiques)
        chosen = candidates[chosen_idx]

        verified, evidence = self._verify_with_tools(subtask, chosen, conv)
        refined = self._refine(conv, subtask, verified, evidence)
        refined_verified, refined_evidence = self._verify_with_tools(subtask, refined, conv)

        evidence_all = evidence + refined_evidence
        self._log("subtask_done", {
            "subtask": subtask,
            "judge_choice": chosen_idx,
            "justification": justification,
            "final_solution": refined_verified,
        })
        return {"solution": refined_verified, "evidence": "\n".join(evidence_all)}

    def _generate_candidates(self, conv: List[Dict[str, str]], subtask: str) -> List[str]:
        candidates = []
        llm = self.engineer_client if self.engineer_client else self.llm
        for i in range(3):
            prompt = (
                f"Subtarefa: {subtask}\n\n"
                f"Gere a candidata de solução número {i + 1} de 3, distinta das demais "
                "em abordagem (não apenas reescrita). Responda apenas com a solução."
            )
            call_messages = conv + [{"role": "user", "content": prompt}]
            seed = random.randint(1, 2_147_483_647)
            text = self._call_llm(call_messages, temperature=0.8, max_tokens=800, seed=seed, _llm=llm)
            candidates.append(text)
        self._log("candidates_generated", {"subtask": subtask, "count": len(candidates)})
        return candidates

    def _self_critique(self, conv: List[Dict[str, str]], subtask: str, candidate: str) -> str:
        prompt = (
            f"Subtarefa: {subtask}\n\nCandidata:\n{candidate}\n\n"
            "Aponte objetivamente pelo menos 2 fraquezas ou riscos concretos "
            "dessa solução (correção, segurança, performance, casos de borda)."
        )
        call_messages = conv + [{"role": "user", "content": prompt}]
        return self._call_llm(call_messages, temperature=0.4, max_tokens=400)

    def _judge(
        self, conv: List[Dict[str, str]], subtask: str, candidates: List[str], critiques: List[str]
    ) -> Tuple[int, str]:
        listing = "\n\n".join(
            f"Candidata {i + 1}:\n{c}\n\nCríticas à candidata {i + 1}:\n{critiques[i]}"
            for i, c in enumerate(candidates)
        )
        prompt = (
            f"Subtarefa: {subtask}\n\n{listing}\n\n"
            "Atue como juiz imparcial. Compare as três candidatas e suas críticas, "
            "e escolha a melhor. Responda APENAS com um JSON no formato "
            '{"choice": <1, 2 ou 3>, "justification": "..."}.'
        )
        call_messages = conv + [{"role": "user", "content": prompt}]
        llm = self.engineer_client if self.engineer_client else self.llm
        raw = self._call_llm(call_messages, temperature=0.2, max_tokens=400, _llm=llm)
        idx, justification = 0, raw
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                choice = int(data.get("choice", 1))
                idx = min(max(choice - 1, 0), len(candidates) - 1)
                justification = str(data.get("justification", raw))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        self._log("judge", {"subtask": subtask, "choice_index": idx, "justification": justification})
        return idx, justification

    def _verify_with_tools(
        self, subtask: str, candidate: str, conv: List[Dict[str, str]]
    ) -> Tuple[str, List[str]]:
        evidence: List[str] = []
        block = _extract_code_block(candidate)
        if not block:
            evidence.append("Nenhum artefato executável detectado; verificação por tool não se aplica.")
            return candidate, evidence

        current_code = block["code"]
        current_full_text = candidate
        lang = block["lang"]
        tool_name = "run_python" if lang in ("python", "py", "") else "run_shell"

        attempt = 0
        while attempt <= MAX_TOOL_RETRIES:
            self._iterations_used += 1
            tool = get_tool(tool_name)
            if not tool:
                evidence.append(f"Tool '{tool_name}' indisponível; verificação pulada.")
                break
            if tool_name in HEAVY_TOOL_NAMES and get_monitor().is_under_pressure():
                result = ToolResult(
                    success=False,
                    error=(
                        f"Tool '{tool_name}' pausada temporariamente: recursos do sistema "
                        "(RAM/CPU) estão sob pressão. Tente novamente em instantes."
                    ),
                )
            elif tool_name == "run_python":
                result = tool.run(code=current_code)
            else:
                result = tool.run(command=current_code)

            evidence.append(
                f"[tool={tool_name} tentativa={attempt + 1}] sucesso={result.success} "
                f"saída/erro={(result.data if result.success else result.error)!r}"
            )
            self._log("tool_verification", {
                "subtask": subtask, "tool": tool_name, "attempt": attempt + 1,
                "success": result.success, "output": result.data, "error": result.error,
            })

            if result.success:
                static_evidence = self._run_static_security_scan(subtask, current_code, lang)
                evidence.extend(static_evidence)
                return current_full_text, evidence

            attempt += 1
            if attempt > MAX_TOOL_RETRIES:
                break
            fix_prompt = (
                f"Subtarefa: {subtask}\n\nA solução a seguir falhou na execução real:\n\n"
                f"{current_full_text}\n\nErro reportado pela ferramenta:\n{result.error}\n\n"
                "Gere uma nova versão corrigida, mantendo o mesmo formato (bloco de código)."
            )
            call_messages = conv + [{"role": "user", "content": fix_prompt}]
            current_full_text = self._call_llm(call_messages, temperature=0.5, max_tokens=800)
            new_block = _extract_code_block(current_full_text)
            current_code = new_block["code"] if new_block else current_code

        evidence.append("Falha persistente após tentativas de correção; solução entregue com ressalva.")
        return current_full_text, evidence

    def _run_static_security_scan(self, subtask: str, code: str, lang: str) -> List[str]:
        evidence: List[str] = []
        tool_name = "bandit_scan" if lang in ("python", "py", "") else "shellcheck_scan"
        tool = get_tool(tool_name)
        if not tool:
            evidence.append(f"[segurança] Tool '{tool_name}' indisponível; verificação estática pulada.")
            return evidence

        try:
            if get_monitor().is_under_pressure():
                evidence.append(
                    f"[segurança={tool_name}] pulado: recursos do sistema (RAM/CPU) sob pressão."
                )
                return evidence
            if tool_name == "bandit_scan":
                result = tool.run(code=code)
            else:
                result = tool.run(script=code)
        except Exception as e:
            evidence.append(f"[segurança={tool_name}] erro inesperado ao rodar: {e}")
            return evidence

        if not result.success:
            evidence.append(f"[segurança={tool_name}] não executado: {result.error}")
            return evidence

        issue_count = result.data.get("issue_count", 0) if isinstance(result.data, dict) else 0
        evidence.append(f"[segurança={tool_name}] {issue_count} issue(s) encontrada(s): {result.data}")
        self._log("static_security_scan", {
            "subtask": subtask, "tool": tool_name, "issue_count": issue_count, "data": result.data,
        })
        return evidence

    def _refine(self, conv: List[Dict[str, str]], subtask: str, candidate: str, evidence: List[str]) -> str:
        prompt = (
            f"Subtarefa: {subtask}\n\nSolução verificada:\n{candidate}\n\n"
            f"Evidências de verificação:\n{chr(10).join(evidence)}\n\n"
            "Faça um polimento final (clareza, consistência, estilo) sem alterar o "
            "comportamento verificado. Se não houver nada a melhorar, repita a solução como está."
        )
        call_messages = conv + [{"role": "user", "content": prompt}]
        return self._call_llm(call_messages, temperature=0.3, max_tokens=800)

    # ------------------------------------------------------------------
    # Passo c) Integração global
    # ------------------------------------------------------------------
    def _integrate(
        self,
        conv: List[Dict[str, str]],
        user_task: str,
        subtask_results: List[Dict[str, str]],
        checklists: List[Dict[str, Any]],
    ) -> str:
        solutions_block = "\n\n".join(
            f"Subtarefa: {r['subtask']}\nSolução: {r['solution']}" for r in subtask_results
        )

        debate_prompt = (
            f"Tarefa original: {user_task}\n\nSoluções das subtarefas:\n{solutions_block}\n\n"
            "Verifique inconsistências entre as soluções. Depois, simule um debate curto "
            "(dois parágrafos) entre um 'Arquiteto' (prioriza correção e robustez) e um "
            "'Revisor' (prioriza simplicidade e manutenibilidade), resolvendo qualquer conflito. "
            "Este texto é apenas para seu raciocínio interno."
        )
        debate = self._call_llm(conv + [{"role": "user", "content": debate_prompt}], temperature=0.4, max_tokens=500)
        self._log("internal_debate", {"debate": debate})

        checklist_confirmations = self._apply_checklists(conv, user_task, solutions_block, checklists)

        final_prompt = (
            f"Tarefa original: {user_task}\n\nSoluções integradas:\n{solutions_block}\n\n"
            f"Resultado do debate interno (não repita literalmente, use apenas para decidir):\n{debate}\n\n"
            f"Checklists de domínio confirmados:\n{checklist_confirmations}\n\n"
            "Monte a RESPOSTA FINAL para o usuário, em português, contendo: (1) um resumo "
            "curto do processo e das decisões, (2) a solução final consolidada, e (3) um "
            "bloco de evidências (o que foi executado/testado e quais itens de checklist "
            "foram confirmados). Não exponha o debate interno literalmente."
        )
        final_text = self._call_llm(conv + [{"role": "user", "content": final_prompt}], temperature=0.3, max_tokens=1200)
        self._log("final_answer", {"final_text": final_text})
        return final_text

    def _apply_checklists(
        self, conv: List[Dict[str, str]], user_task: str, solutions_block: str, checklists: List[Dict[str, Any]]
    ) -> str:
        if not checklists:
            return "Nenhum checklist de domínio aplicável a esta tarefa."

        confirmations = []
        for checklist in checklists:
            items = checklist.get("items", [])
            prompt = (
                f"Tarefa: {user_task}\n\nSoluções:\n{solutions_block}\n\n"
                f"Checklist de {checklist.get('label', checklist.get('domain'))}:\n"
                + "\n".join(f"- {it}" for it in items)
                + "\n\nPara cada item, confirme explicitamente se foi atendido (sim/não) e, "
                "se não, o que falta. Responda em lista curta."
            )
            result = self._call_llm(conv + [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=500)
            confirmations.append(f"[{checklist.get('label', checklist.get('domain'))}]\n{result}")
            self._log("checklist_applied", {"domain": checklist.get("domain"), "result": result})

        return "\n\n".join(confirmations)

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------
    def _call_llm(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, _llm=None, **kwargs) -> str:
        self._iterations_used += 1
        llm = _llm if _llm else self.llm
        try:
            return llm.generate(messages=messages, max_tokens=max_tokens, temperature=temperature, **kwargs)
        except Exception as e:
            logger.error(f"Erro no LLM (modo analista): {e}")
            return f"[erro ao chamar o modelo: {e}]"

    def _log(self, event: str, data: Dict[str, Any]) -> None:
        self._log_entries.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "iterations_used": self._iterations_used,
            **data,
        })

    def _write_log(self, project_id: Optional[str], chat_id: Optional[str]) -> None:
        log_dir = Path(DATA_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        key = project_id or "_solo"
        log_file = log_dir / f"{key}_analyst.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            for entry in self._log_entries:
                entry_with_ctx = {"project_id": project_id, "chat_id": chat_id, **entry}
                f.write(json.dumps(entry_with_ctx, ensure_ascii=False) + "\n")