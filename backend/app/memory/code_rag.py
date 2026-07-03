# ===================== RAG PARA CÓDIGO =====================
# Responsabilidade: carregar índice FAISS, buscar trechos de código
# relevantes para uma consulta, usando o mesmo modelo de embeddings
# do roteador de agentes. Geração sob demanda se o índice não existir.

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import faiss
import numpy as np

from ..config import settings
from ..db import PROJECTS_FILES_DIR
from ..orchestrator.router import get_router
from ..tools.indexer import index_project

logger = logging.getLogger(__name__)


def retrieve(project_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Busca os trechos de código mais relevantes para a consulta no índice
    FAISS do projeto. Se o índice não existir, tenta gerá-lo sob demanda
    (chamando index_project) e emite um log.
    Retorna uma lista de dicionários com 'file', 'line', 'code' e 'similarity'.
    """
    index_dir = PROJECTS_FILES_DIR / project_id / "index"
    faiss_path = index_dir / "codebase.faiss"
    metadata_path = index_dir / "metadata.json"

    # Se o índice não existir, tenta gerar sob demanda
    if not faiss_path.exists() or not metadata_path.exists():
        logger.info(f"Índice FAISS não encontrado para projeto {project_id}. Gerando sob demanda...")
        result = index_project(project_id)
        if result["status"] != "ok":
            logger.warning(f"Falha ao gerar índice: {result.get('message')}")
            return []
        # Verifica novamente após geração
        if not faiss_path.exists() or not metadata_path.exists():
            logger.warning("Índice ainda não disponível após geração.")
            return []

    # Garantir que o modelo de embeddings esteja carregado (reutiliza o do router)
    router = get_router()
    if not router._ensure_model():
        logger.warning("Modelo de embeddings indisponível, RAG não pode ser usado.")
        return []

    model = router._model

    # Carregar índice FAISS
    try:
        index = faiss.read_index(str(faiss_path))
    except Exception as e:
        logger.error(f"Erro ao ler índice FAISS: {e}")
        return []

    # Carregar metadados
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler metadados do índice: {e}")
        return []

    chunks = metadata.get("chunks", [])
    if not chunks:
        return []

    # Embedding da consulta
    query_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    query_emb = np.asarray(query_emb, dtype="float32")

    # Busca
    distances, indices = index.search(query_emb, top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        results.append({
            "file": chunk.get("file", ""),
            "line": chunk.get("line", 0),
            "code": chunk.get("code", ""),
            "similarity": float(distances[0][i]),
        })

    return results