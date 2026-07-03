#!/usr/bin/env python3
"""
Teste do agente Firmware.
Uso: python scripts/test_firmware_agent.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from app.llm import get_llm_client
from app.orchestrator.router import select_agent
from app.orchestrator.loop import AgentLoop

async def test_firmware():
    client = get_llm_client()
    messages = [
        {"role": "system", "content": "Você é um assistente especializado em firmware."},
        {"role": "user", "content": "Crie um código para ESP32 que configure BLE com um serviço de bateria e uma característica de leitura."}
    ]
    # Forçar domínio firmware
    agent_type = select_agent(mode=None, user_message=messages[-1]["content"], domain="firmware")
    loop = AgentLoop(client)
    result = await loop.run(messages, project_id=None, chat_id="test", mode=None, agent_type=agent_type)
    print("\n===== RESPOSTA DO AGENTE FIRMWARE =====\n")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_firmware())