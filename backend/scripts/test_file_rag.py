# ===================== TESTE DO RAG DE ARQUIVOS =====================
# Executar com: python -m pytest scripts/test_file_rag.py -v

import pytest
from pathlib import Path
import shutil
from app.memory.file_rag import (
    index_document,
    search_documents,
    delete_document_index,
    index_project_documents,
    _chunk_text,
    _extract_text_from_pdf,
)
from app.db import db_cursor, new_id, now_iso, PROJECTS_FILES_DIR, LOOSE_FILES_DIR


@pytest.fixture
def test_pdf_path(tmp_path):
    # Cria um PDF de teste (simples, usando PyMuPDF)
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF não instalado")
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Este é um documento de teste para RAG.")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def test_txt_path(tmp_path):
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("Linha 1: Conteúdo de exemplo.\nLinha 2: Mais texto para indexação.", encoding="utf-8")
    return txt_path


def test_chunk_text():
    text = "Parágrafo 1. " * 100
    chunks = _chunk_text(text, chunk_size=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_index_and_search(tmp_path, test_txt_path):
    # Simular um projeto
    project_id = "test_proj"
    proj_dir = PROJECTS_FILES_DIR / project_id / "files"
    proj_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(test_txt_path, proj_dir / "test.txt")

    # Registrar o arquivo no banco (simulação)
    file_id = new_id()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO project_files (id, project_id, filename, file_type, stored_path, size_bytes, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, project_id, "test.txt", "txt", str(proj_dir / "test.txt"), 50, now_iso())
        )

    # Indexar
    result = index_project_documents(project_id)
    assert result["status"] == "ok"
    assert result["indexed_count"] > 0

    # Buscar
    results = search_documents("exemplo", project_id=project_id, top_k=3)
    assert len(results) > 0
    assert "exemplo" in results[0]["chunk_text"].lower()

    # Limpeza
    delete_document_index(file_id, project_id)
    shutil.rmtree(PROJECTS_FILES_DIR / project_id, ignore_errors=True)


def test_loose_file_index_and_search(tmp_path, test_txt_path):
    file_id = new_id()
    stored_path = LOOSE_FILES_DIR / f"{file_id}.txt"
    shutil.copy(test_txt_path, stored_path)

    result = index_document(file_id, stored_path, project_id=None)
    assert result["status"] == "ok"
    assert result["indexed_chunks"] > 0

    results = search_documents("exemplo", include_loose=True, top_k=3)
    assert len(results) > 0
    assert results[0]["file_id"] == file_id

    # Limpeza
    delete_document_index(file_id, None)
    assert not (LOOSE_FILES_DIR / "doc_index" / "doc_metadata.json").exists()
    stored_path.unlink()