# ===================== RAG PARA ARQUIVOS DA GALERIA =====================
# Responsabilidade: indexar documentos (PDF, Markdown, TXT) em índices FAISS
# por projeto (ou global para loose files) e recuperar trechos relevantes.
# Usa PyMuPDF para extração de texto de PDFs.

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import faiss

from ..db import PROJECTS_FILES_DIR, LOOSE_FILES_DIR, db_cursor
from ..config import settings
from ..orchestrator.router import get_router

logger = logging.getLogger(__name__)

# Modelo de embeddings (mesmo do router)
EMBEDDING_MODEL_NAME = settings.CODE_EMBEDDING_MODEL_NAME
# Tamanho do chunk de texto (aproximadamente por parágrafo)
CHUNK_SIZE = 512  # caracteres
# Número máximo de trechos a retornar
TOP_K = 5

# Extensões suportadas
SUPPORTED_EXTS = {".pdf", ".md", ".txt", ".markdown"}


def _get_model():
    """Obtém o modelo de embeddings (reutiliza o do router)."""
    router = get_router()
    if not router._ensure_model():
        logger.warning("Modelo de embeddings indisponível para RAG de arquivos.")
        return None
    return router._model


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrai texto de um PDF usando PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) não instalado. Instale com: pip install PyMuPDF")
        return ""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.warning(f"Erro ao extrair texto de {pdf_path}: {e}")
    return text


def _extract_text_from_markdown_txt(file_path: Path) -> str:
    """Lê arquivo de texto simples (Markdown/TXT)."""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Erro ao ler {file_path}: {e}")
        return ""


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Divide texto em chunks por parágrafos, respeitando o tamanho máximo."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(current) + len(p) + 1 <= chunk_size:
            current += " " + p if current else p
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks


def _get_index_dir(project_id: Optional[str] = None) -> Path:
    """Retorna o diretório onde o índice FAISS para documentos será armazenado."""
    if project_id:
        base = PROJECTS_FILES_DIR / project_id / "doc_index"
    else:
        base = LOOSE_FILES_DIR / "doc_index"
    base.mkdir(parents=True, exist_ok=True)
    return base


def index_document(file_id: str, file_path: Path, project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Indexa um único documento (extrai texto, gera chunks, embeddings, e adiciona ao índice FAISS).
    Retorna status e número de chunks indexados.
    """
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        return {"status": "skipped", "reason": f"Extensão {ext} não suportada"}

    # Extrair texto
    if ext == ".pdf":
        text = _extract_text_from_pdf(file_path)
    else:
        text = _extract_text_from_markdown_txt(file_path)

    if not text:
        return {"status": "error", "reason": "Nenhum texto extraído"}

    chunks = _chunk_text(text)
    if not chunks:
        return {"status": "error", "reason": "Nenhum chunk gerado"}

    model = _get_model()
    if model is None:
        return {"status": "error", "reason": "Modelo de embeddings indisponível"}

    # Gerar embeddings
    try:
        embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
    except Exception as e:
        logger.error(f"Erro ao gerar embeddings: {e}")
        return {"status": "error", "reason": str(e)}

    embeddings = np.asarray(embeddings, dtype="float32")

    # Carregar ou criar índice FAISS
    index_dir = _get_index_dir(project_id)
    faiss_path = index_dir / "doc_index.faiss"
    metadata_path = index_dir / "doc_metadata.json"

    # Carregar índice existente
    if faiss_path.exists():
        try:
            index = faiss.read_index(str(faiss_path))
        except Exception as e:
            logger.warning(f"Erro ao ler índice existente, recriando: {e}")
            index = faiss.IndexFlatIP(embeddings.shape[1])
    else:
        index = faiss.IndexFlatIP(embeddings.shape[1])

    # Adicionar novos embeddings
    index.add(embeddings)

    # Atualizar metadados
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            metadata = {"chunks": []}
    else:
        metadata = {"chunks": []}

    new_chunks = [
        {
            "file_id": file_id,
            "file_path": str(file_path),
            "chunk_text": chunk,
            "project_id": project_id,
        }
        for chunk in chunks
    ]
    metadata["chunks"].extend(new_chunks)

    # Escrever índice e metadados
    faiss.write_index(index, str(faiss_path))
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "indexed_chunks": len(chunks)}


def index_project_documents(project_id: str) -> Dict[str, Any]:
    """Indexa todos os documentos (PDF, MD, TXT) do projeto."""
    project_files_dir = PROJECTS_FILES_DIR / project_id / "files"
    if not project_files_dir.exists():
        return {"status": "error", "reason": "Diretório do projeto não encontrado"}

    # Buscar todos os arquivos de documentos no diretório do projeto
    doc_files = []
    for ext in SUPPORTED_EXTS:
        doc_files.extend(project_files_dir.rglob(f"*{ext}"))

    if not doc_files:
        return {"status": "ok", "indexed_count": 0, "message": "Nenhum documento encontrado"}

    # Para cada arquivo, indexar
    indexed_total = 0
    for file_path in doc_files:
        # Obter file_id a partir do banco (associar ao projeto)
        with db_cursor() as cur:
            cur.execute(
                "SELECT id FROM project_files WHERE project_id = ? AND stored_path = ?",
                (project_id, str(file_path))
            )
            row = cur.fetchone()
            if not row:
                # Se não estiver no banco, pular (não deveria acontecer)
                continue
            file_id = row["id"]
            result = index_document(file_id, file_path, project_id)
            if result.get("status") == "ok":
                indexed_total += result.get("indexed_chunks", 0)

    return {"status": "ok", "indexed_count": indexed_total, "message": f"Indexados {indexed_total} chunks"}


def index_loose_file(file_id: str, file_path: Path) -> Dict[str, Any]:
    """Indexa um arquivo solto (loose file) – sem projeto."""
    return index_document(file_id, file_path, project_id=None)


def search_documents(
    query: str,
    project_id: Optional[str] = None,
    top_k: int = TOP_K,
    include_loose: bool = True
) -> List[Dict[str, Any]]:
    """
    Busca trechos de documentos relevantes para a query usando o índice FAISS.
    Se project_id for fornecido, busca apenas no índice daquele projeto.
    Se include_loose for True, também busca no índice global de loose files.
    Retorna lista de trechos com metadados.
    """
    model = _get_model()
    if model is None:
        return []

    query_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    query_emb = np.asarray(query_emb, dtype="float32")

    results = []
    index_dirs = []
    if project_id:
        index_dirs.append(_get_index_dir(project_id))
    if include_loose:
        index_dirs.append(_get_index_dir(None))  # global

    for idx_dir in index_dirs:
        faiss_path = idx_dir / "doc_index.faiss"
        metadata_path = idx_dir / "doc_metadata.json"
        if not faiss_path.exists() or not metadata_path.exists():
            continue

        try:
            index = faiss.read_index(str(faiss_path))
        except Exception as e:
            logger.warning(f"Erro ao ler índice {faiss_path}: {e}")
            continue

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler metadados {metadata_path}: {e}")
            continue

        chunks = metadata.get("chunks", [])
        if not chunks:
            continue

        # Buscar os top_k mais similares
        distances, indices = index.search(query_emb, min(top_k, len(chunks)))
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(chunks):
                continue
            chunk = chunks[idx]
            results.append({
                "file_id": chunk.get("file_id"),
                "file_path": chunk.get("file_path"),
                "chunk_text": chunk.get("chunk_text", ""),
                "similarity": float(distances[0][i]),
                "project_id": chunk.get("project_id"),
            })

    # Ordenar por similaridade (já estão ordenados, mas vamos garantir)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    # Retornar apenas os top_k únicos (por similaridade)
    return results[:top_k]


def delete_document_index(file_id: str, project_id: Optional[str] = None):
    """Remove um documento do índice (quando o arquivo é deletado)."""
    # Como o índice FAISS não suporta remoção direta, recriamos o índice
    # a partir dos metadados, filtrando o file_id.
    index_dir = _get_index_dir(project_id)
    metadata_path = index_dir / "doc_metadata.json"
    if not metadata_path.exists():
        return

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        return

    original_chunks = metadata.get("chunks", [])
    filtered_chunks = [c for c in original_chunks if c.get("file_id") != file_id]

    if len(filtered_chunks) == len(original_chunks):
        return  # Nenhuma mudança

    # Se não houver chunks, remover os arquivos de índice
    if not filtered_chunks:
        faiss_path = index_dir / "doc_index.faiss"
        if faiss_path.exists():
            faiss_path.unlink()
        metadata_path.unlink()
        return

    # Reconstruir índice com os chunks restantes
    model = _get_model()
    if model is None:
        return

    texts = [c["chunk_text"] for c in filtered_chunks]
    try:
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    except Exception as e:
        logger.error(f"Erro ao regenerar embeddings: {e}")
        return

    embeddings = np.asarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    metadata["chunks"] = filtered_chunks
    faiss_path = index_dir / "doc_index.faiss"
    faiss.write_index(index, str(faiss_path))
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)