import asyncio
from app.llm import get_llm_client

def test_llm():
    client = get_llm_client()
    messages = [{"role": "user", "content": "Diga 'Olá, Hermes!'"}]
    try:
        reply = client.generate(messages, max_tokens=20)
        print("Resposta:", reply)
    except Exception as e:
        print("Erro:", e)

if __name__ == "__main__":
    test_llm()