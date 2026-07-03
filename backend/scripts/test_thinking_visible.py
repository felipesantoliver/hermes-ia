# ===================== TESTE MANUAL: PENSAMENTO VISÍVEL (SSE) =====================
# Responsabilidade: chamar POST /chat/stream com show_thinking=true e imprimir
# separadamente os eventos "thinking" (raciocínio interno) e "token"/"data"
# (resposta final), para inspecionar visualmente se o backend está narrando
# as etapas internas corretamente.
#
# Uso:
#   1. Suba o backend (uvicorn app.main:app ou equivalente).
#   2. Crie um chat via POST /chats/ e pegue o chat_id (ou passe um já
#      existente via --chat-id).
#   3. python scripts/test_thinking_visible.py --chat-id <ID> --message "..."

import argparse
import json
import sys

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"


def run(base_url: str, chat_id: str, message: str, mode: str | None):
    payload = {
        "message": message,
        "mode": mode,
        "chat_id": chat_id,
        "show_thinking": True,
    }

    print(f"--> POST {base_url}/chat/stream")
    print(f"--> payload: {json.dumps(payload, ensure_ascii=False)}\n")

    with httpx.Client(timeout=120) as client:
        with client.stream("POST", f"{base_url}/chat/stream", json=payload) as response:
            response.raise_for_status()

            event_type = "message"
            for raw_line in response.iter_lines():
                if raw_line == "":
                    event_type = "message"
                    continue
                if raw_line.startswith("event:"):
                    event_type = raw_line[len("event:"):].strip()
                    continue
                if raw_line.startswith("data:"):
                    data_str = raw_line[len("data:"):].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if event_type == "thinking":
                        print(f"[PENSAMENTO] {data.get('token', '')}")
                    elif event_type == "token":
                        print(f"[RESPOSTA]   {data.get('token', '')}", end="", flush=True)
                    elif event_type == "system":
                        print(f"\n[SISTEMA]    {data.get('message', '')}")
                    elif event_type == "error":
                        print(f"\n[ERRO]       {data.get('error', '')}")
                    elif event_type == "done":
                        print("\n[FIM DO STREAM]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testa o stream de pensamento visível (SSE)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--chat-id", required=True, help="ID de um chat já existente")
    parser.add_argument("--message", default="Explique como funciona o modo analista do Hermes.")
    parser.add_argument("--mode", default=None, choices=[None, "code", "engineer", "analyst"])
    args = parser.parse_args()

    try:
        run(args.base_url, args.chat_id, args.message, args.mode)
    except httpx.HTTPError as e:
        print(f"Erro HTTP: {e}", file=sys.stderr)
        sys.exit(1)