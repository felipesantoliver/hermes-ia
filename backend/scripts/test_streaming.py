"""
Script de teste manual para o endpoint SSE POST /chat/stream.

Uso:
    python scripts/test_streaming.py "sua mensagem aqui" [--mode code|think|analyst]

Pré-requisitos:
  - Backend rodando (uvicorn main:app --reload) em http://localhost:8000
  - Servidor llama-server (ou compatível) no ar em LLM_BASE_URL (ver config.py)

O script:
  1. Cria um chat novo via POST /chats/.
  2. Conecta em POST /chat/stream com esse chat_id.
  3. Imprime cada token assim que chega, em tempo real (sem esperar
     a resposta completa), e ao final mostra um resumo.
"""

import argparse
import json
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"


def create_chat(client: httpx.Client, base_url: str, title: str = "Teste de streaming") -> str:
    resp = client.post(f"{base_url}/chats/", json={"title": title, "project_id": None})
    resp.raise_for_status()
    return resp.json()["id"]


def stream_chat(client: httpx.Client, base_url: str, chat_id: str, message: str, mode: str | None):
    payload = {
        "message": message,
        "mode": mode,
        "project_id": None,
        "chat_id": chat_id,
    }

    print(f"→ Conectando em {base_url}/chat/stream ...\n")
    start = time.monotonic()
    token_count = 0
    full_text = ""

    with client.stream("POST", f"{base_url}/chat/stream", json=payload, timeout=None) as response:
        response.raise_for_status()

        event_type = "message"
        data_lines: list[str] = []

        for raw_line in response.iter_lines():
            line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")

            if line == "":
                # Linha em branco = fim de um evento SSE
                if data_lines:
                    data_str = "".join(data_lines)
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {}

                    if event_type == "token":
                        token = data.get("token", "")
                        print(token, end="", flush=True)
                        full_text += token
                        token_count += 1
                    elif event_type == "error":
                        print(f"\n\n[ERRO] {data.get('error')}", file=sys.stderr)
                    elif event_type == "done":
                        pass

                event_type = "message"
                data_lines = []
                continue

            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())

    elapsed = time.monotonic() - start
    print("\n\n---")
    print(f"Tokens/fragmentos recebidos: {token_count}")
    print(f"Tempo total: {elapsed:.2f}s")
    print(f"Tamanho da resposta final: {len(full_text)} caracteres")


def main():
    parser = argparse.ArgumentParser(description="Testa o endpoint SSE /chat/stream do Hermes AI")
    parser.add_argument("message", help="Mensagem a enviar para o Hermes")
    parser.add_argument("--mode", choices=["code", "think", "analyst"], default=None, help="Modo do chip ativo")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="URL base do backend")
    args = parser.parse_args()

    with httpx.Client() as client:
        chat_id = create_chat(client, args.base_url)
        print(f"Chat criado: {chat_id}\n")
        stream_chat(client, args.base_url, chat_id, args.message, args.mode)


if __name__ == "__main__":
    main()