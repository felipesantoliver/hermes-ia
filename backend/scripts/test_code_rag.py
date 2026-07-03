#!/usr/bin/env python3
"""
Teste manual do RAG para código.

Pré-requisitos:
- Backend rodando (ou apenas as dependências instaladas).
- sentence-transformers instalado.
- O projeto de teste deve ser criado no banco.

Uso:
    python scripts/test_code_rag.py
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db, db_cursor, new_id, now_iso
from app.tools.indexer import index_project
from app.memory.code_rag import retrieve
from app.orchestrator.router import get_router

# Garantir que o modelo de embeddings seja carregado
get_router()._ensure_model()

# Criar um diretório temporário para arquivos de teste
temp_dir = tempfile.mkdtemp(prefix="hermes_test_")
project_id = new_id()

try:
    # 1. Criar um projeto no banco
    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO projects (id, name, description, memory_scope, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, "Teste RAG", "Projeto para teste de RAG", "isolated", ts, ts)
        )

    # 2. Criar diretório de arquivos do projeto
    project_files_dir = Path("backend/data/projects") / project_id / "files"
    project_files_dir.mkdir(parents=True, exist_ok=True)

    # 3. Escrever alguns arquivos Python de exemplo
    code_samples = {
        "math_utils.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Divisão por zero")
    return a / b
""",
        "string_utils.py": """
def capitalize_words(text):
    return ' '.join(word.capitalize() for word in text.split())

def reverse_string(text):
    return text[::-1]

def count_vowels(text):
    return sum(1 for ch in text.lower() if ch in 'aeiou')
""",
        "data_utils.py": """
import json

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
""",
    }

    for filename, content in code_samples.items():
        filepath = project_files_dir / filename
        filepath.write_text(content, encoding="utf-8")

    # 4. Indexar o projeto
    print("Indexando projeto...")
    result = index_project(project_id)
    print(f"Indexação: {result}")

    # 5. Fazer consultas RAG
    queries = [
        "Como dividir dois números?",
        "Função para inverter string",
        "Carregar JSON de arquivo",
        "Contar vogais",
    ]

    for query in queries:
        print(f"\nConsulta: '{query}'")
        results = retrieve(project_id, query, top_k=2)
        if results:
            for r in results:
                print(f"  - {r['file']}:{r['line']} (similaridade: {r['similarity']:.3f})")
                print(f"    {r['code'][:100]}...")
        else:
            print("  Nenhum resultado encontrado.")

    print("\nTeste concluído.")

finally:
    # Limpeza
    shutil.rmtree(temp_dir, ignore_errors=True)
    # Opcional: remover projeto do banco e arquivos
    with db_cursor() as cur:
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    import shutil
    project_data_dir = Path("backend/data/projects") / project_id
    if project_data_dir.exists():
        shutil.rmtree(project_data_dir, ignore_errors=True)