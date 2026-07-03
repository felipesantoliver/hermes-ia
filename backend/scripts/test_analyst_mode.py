"""
Teste manual do Modo Analista.

Pré-requisitos:
- Backend rodando (uvicorn main:app), com um servidor llama.cpp compatível
  com a API OpenAI acessível em LLM_BASE_URL (ver backend/app/config.py).
- Banco inicializado (init_db já roda no startup do FastAPI).

Uso:
    python backend/scripts/test_analyst_mode.py
"""
import json
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"

TASK = (
    "Crie uma função Python que calcule o N-ésimo número de Fibonacci de "
    "forma otimizada e prove que ela está correta."
)


def main() -> int:
    with httpx.Client(timeout=600) as client:
        # 1. Criar um chat novo
        chat_res = client.post(f"{API_BASE}/chats/", json={"title": "Teste Modo Analista", "project_id": None})
        chat_res.raise_for_status()
        chat = chat_res.json()
        chat_id = chat["id"]
        print(f"[test] chat_id={chat_id}")

        # 2. Salvar a mensagem do usuário (mesmo padrão usado pelo frontend)
        msg_res = client.post(f"{API_BASE}/chats/{chat_id}/messages", json={"role": "user", "content": TASK})
        msg_res.raise_for_status()

        # 3. Chamar /chat/ com mode="analyst"
        print("[test] enviando requisição em modo analista, pode demorar bastante...")
        chat_payload = {"message": TASK, "mode": "analyst", "project_id": None, "chat_id": chat_id}
        resp = client.post(f"{API_BASE}/chat/", json=chat_payload)
        if resp.status_code != 200:
            print(f"[test] FALHOU: status={resp.status_code} body={resp.text}")
            return 1

        data = resp.json()
        print("\n===== RESPOSTA FINAL =====\n")
        print(data["reply"])

        # 4. Checar o log específico do modo analista
        log_path = Path(__file__).resolve().parent.parent / "data" / "logs" / "_solo_analyst.jsonl"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            events = [json.loads(l).get("event") for l in lines[-50:]]
            print(f"\n[test] últimos eventos logados em {log_path}:")
            print(events)
            expected = {"decomposition", "candidates_generated", "judge", "tool_verification", "final_answer"}
            missing = expected - set(events)
            if missing:
                print(f"[test] AVISO: eventos esperados não encontrados nas últimas entradas: {missing}")
            else:
                print("[test] OK: decomposição, candidatos, juiz, verificação por tool e resposta final presentes no log.")
        else:
            print(f"[test] AVISO: log não encontrado em {log_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())