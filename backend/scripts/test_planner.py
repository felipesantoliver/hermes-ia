#!/usr/bin/env python3
"""
Teste manual do planejador multi‑step (V2.2).

Uso:
    python scripts/test_planner.py "mensagem de teste"

Pré-requisitos:
    - Backend rodando (ou apenas as dependências instaladas)
    - LLM configurado (llama.cpp ou similar)

O script gera um plano para a mensagem fornecida e imprime os passos.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import get_llm_client
from app.orchestrator.planner import Planner


def main():
    if len(sys.argv) < 2:
        print("Uso: python test_planner.py 'mensagem'")
        sys.exit(1)

    user_message = " ".join(sys.argv[1:])
    print(f"Tarefa: {user_message}\n")

    client = get_llm_client()
    planner = Planner(client)

    print("Gerando plano...")
    plan = planner.generate_plan(user_message)

    print(f"Plano gerado com {len(plan.steps)} passo(s):")
    for i, step in enumerate(plan.steps):
        deps = step.depends_on
        dep_str = f" (depende de {deps})" if deps else ""
        tool_str = f" [tool: {step.tool}]" if step.tool else ""
        print(f"{i+1}. {step.description}{tool_str}{dep_str}")

    # Teste de replanejamento (simulado)
    if len(plan.steps) > 1:
        print("\nSimulando falha no passo 0...")
        failed_idx = 0
        error = "Falha simulada: arquivo não encontrado"
        new_plan = planner.replan(plan, failed_idx, error, user_message)
        print(f"Novo plano após replanejamento: {len(new_plan.steps)} passo(s)")
        for i, step in enumerate(new_plan.steps):
            print(f"{i+1}. {step.description}")

    print("\nTeste concluído.")


if __name__ == "__main__":
    main()