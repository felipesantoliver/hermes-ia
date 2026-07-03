# ===================== PLANEJADOR MULTI-STEP =====================
# Responsabilidade: gerar e gerenciar planos de ação para tarefas complexas.
# Usa o LLM para decompor a tarefa em passos sequenciais com dependências.
# Suporta replanejamento em caso de falha.

import json
import logging
import re
from typing import List, Dict, Any, Optional

from ..llm import LLMClient

logger = logging.getLogger(__name__)


class PlanStep:
    def __init__(
        self,
        description: str,
        tool: Optional[str] = None,
        params: Optional[Dict] = None,
        depends_on: Optional[List[int]] = None
    ):
        self.description = description
        self.tool = tool
        self.params = params or {}
        self.depends_on = depends_on or []
        self.status = "pending"  # pending, in_progress, done, failed
        self.result = None
        self.error = None

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "depends_on": self.depends_on,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


class Plan:
    def __init__(self, steps: List[PlanStep]):
        self.steps = steps
        self.current_step_index = 0

    def get_next_step(self) -> Optional[PlanStep]:
        """Retorna o próximo passo a ser executado (primeiro com status pending e dependências satisfeitas)."""
        for i, step in enumerate(self.steps):
            if step.status == "pending":
                # Verifica dependências
                deps_ok = all(self.steps[d].status == "done" for d in step.depends_on if d < i)
                if deps_ok:
                    self.current_step_index = i
                    return step
        return None

    def all_done(self) -> bool:
        return all(s.status == "done" for s in self.steps)

    def mark_step_done(self, step_index: int, result: Any):
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = "done"
            self.steps[step_index].result = result

    def mark_step_failed(self, step_index: int, error: str):
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = "failed"
            self.steps[step_index].error = error

    def to_json(self) -> Dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
        }


class Planner:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_plan(self, user_message: str, context: str = "") -> Plan:
        """
        Gera um plano de ação para a tarefa do usuário.
        Retorna um objeto Plan.
        """
        prompt = f"""
Você é um assistente de planejamento. Para a seguinte tarefa, crie um plano de ação detalhado em passos.
Cada passo deve ter uma descrição clara, a ferramenta a ser usada (se houver) e as dependências entre passos (índices baseados em 0).
Responda APENAS com um JSON contendo uma lista de passos no seguinte formato:
[
  {{
    "description": "Descrição do passo",
    "tool": "nome_da_ferramenta" (opcional, pode ser null),
    "params": {{ "param1": "valor1" }} (opcional),
    "depends_on": [0, 1] (opcional, lista de índices de passos que devem ser concluídos antes)
  }}
]

Tarefa: {user_message}

Contexto adicional: {context if context else "Nenhum"}

Se a tarefa for simples e não exigir múltiplos passos, retorne um único passo sem ferramenta.
"""
        try:
            response = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.2
            )
            json_str = self._extract_json(response)
            if not json_str:
                logger.warning("Falha ao extrair JSON do plano. Usando fallback.")
                return self._fallback_plan(user_message)
            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]
            steps = []
            for item in data:
                description = item.get("description", "Passo")
                tool = item.get("tool")
                params = item.get("params", {})
                depends_on = item.get("depends_on", [])
                steps.append(PlanStep(description, tool, params, depends_on))
            if not steps:
                return self._fallback_plan(user_message)
            return Plan(steps)
        except Exception as e:
            logger.error(f"Erro ao gerar plano: {e}")
            return self._fallback_plan(user_message)

    def _extract_json(self, text: str) -> Optional[str]:
        """Tenta extrair um objeto/array JSON da resposta do LLM."""
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _fallback_plan(self, user_message: str) -> Plan:
        """Plano de fallback: único passo sem ferramenta."""
        step = PlanStep(f"Responder à tarefa: {user_message}", tool=None, params={})
        return Plan([step])

    def replan(
        self,
        plan: Plan,
        failed_step_index: int,
        error: str,
        user_message: str,
        context: str = ""
    ) -> Plan:
        """
        Replaneja os passos restantes a partir do passo que falhou.
        """
        done_steps = [s.to_dict() for s in plan.steps[:failed_step_index] if s.status == "done"]
        remaining_descriptions = [s.description for s in plan.steps[failed_step_index:] if s.status != "done"]
        prompt = f"""
O plano original para a tarefa "{user_message}" falhou no passo "{plan.steps[failed_step_index].description}" com o erro: {error}.
Passos já concluídos: {json.dumps(done_steps)}
Passos restantes a serem replanejados: {remaining_descriptions}

Gere um novo plano para os passos restantes, ajustando para corrigir o erro. Responda APENAS com JSON no mesmo formato que antes.
"""
        try:
            response = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.2
            )
            json_str = self._extract_json(response)
            if not json_str:
                return self._fallback_plan(user_message)
            data = json.loads(json_str)
            if not isinstance(data, list):
                data = [data]
            new_steps = []
            for item in data:
                description = item.get("description", "Passo")
                tool = item.get("tool")
                params = item.get("params", {})
                depends_on = item.get("depends_on", [])
                new_steps.append(PlanStep(description, tool, params, depends_on))
            if not new_steps:
                return self._fallback_plan(user_message)

            # Mantém passos já concluídos + novos passos
            final_steps = plan.steps[:failed_step_index] + new_steps
            # Reindexa dependências (simplificado: assume que dependências são relativas ao novo array)
            for idx, step in enumerate(final_steps):
                if idx >= failed_step_index:
                    new_deps = []
                    for d in step.depends_on:
                        if d < failed_step_index:
                            new_deps.append(d)
                        # Ignora dependências para passos removidos
                    step.depends_on = new_deps
            return Plan(final_steps)
        except Exception as e:
            logger.error(f"Erro ao replanejar: {e}")
            return self._fallback_plan(user_message)

    @staticmethod
    def is_complex_task(user_message: str) -> bool:
        """Heurística para detectar se a tarefa é complexa e merece planejamento."""
        if len(user_message.split()) > 50:
            return True
        keywords = ["planejar", "arquitetura", "sistema", "múltiplos", "passos", "implementar", "criar", "construir"]
        lower = user_message.lower()
        return any(kw in lower for kw in keywords)