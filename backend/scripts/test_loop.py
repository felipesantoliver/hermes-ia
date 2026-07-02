import asyncio
from app.llm import get_llm_client
from app.orchestrator.loop import AgentLoop

async def test_loop():
    client = get_llm_client()
    loop = AgentLoop(client)
    messages = [
        {"role": "system", "content": "Você é um assistente. Use ferramentas se necessário."},
        {"role": "user", "content": "Leia o arquivo 'README.md' do projeto e me diga qual o nome do autor."}
    ]
    # Para teste, precisaríamos ter um projeto com arquivo README.md.
    # Apenas simular que o arquivo existe.
    # Vamos mockar a tool de leitura de arquivo? Melhor criar um projeto de teste.
    # Por simplicidade, apenas verificamos se o loop não quebra.
    result = await loop.run(messages, project_id="teste", chat_id="teste")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_loop())