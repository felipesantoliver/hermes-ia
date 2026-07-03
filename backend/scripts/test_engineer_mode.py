#!/usr/bin/env python3
"""
Teste do modo engenheiro.
Uso: python scripts/test_engineer_mode.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.llm import get_llm_client

def main():
    client = get_llm_client()
    if not client.has_engineer():
        print("Modo engenheiro não configurado.")
        return 1
    messages = [{"role": "user", "content": "Diga 'Olá, mundo!'"}]
    try:
        reply = client.generate(messages, max_tokens=20, model="engineer")
        print("Resposta do modelo engenheiro:", reply)
        return 0
    except Exception as e:
        print("Erro:", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())