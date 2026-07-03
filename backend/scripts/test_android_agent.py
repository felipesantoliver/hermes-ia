#!/usr/bin/env python3
"""
Teste do agente Android.
Uso: python scripts/test_android_agent.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from app.llm import get_llm_client
from app.orchestrator.router import select_agent
from app.orchestrator.loop import AgentLoop

async def test_android():
    client = get_llm_client()
    messages = [
        {"role": "system", "content": "Você é um assistente especializado em Android."},
        {"role": "user", "content": "Crie uma tela de login em Kotlin com validação de campos e um botão de login."}
    ]
    agent_type = select_agent(mode=None, user_message=messages[-1]["content"], domain="android")
    loop = AgentLoop(client)
    result = await loop.run(messages, project_id=None, chat_id="test", mode=None, agent_type=agent_type)
    print("\n===== RESPOSTA DO AGENTE ANDROID =====\n")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_android())