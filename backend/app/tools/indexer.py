# ===================== INDEXADOR DE CODEBASE (prep RAG V2) =====================
# Responsabilidade: varrer os arquivos de um projeto, extrair unidades de
# código (funções/classes para Python; blocos aproximados por regex para
# outras linguagens), gerar embeddings com o mesmo SentenceTransformer usado
# no router de agentes, e persistir um índice FAISS local em
# backend/data/projects/{id}/index/. A BUSCA sobre esse índice é escopo da
# V2.2 — aqui só disparamos a indexação e reportamos status.

import ast
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..db import PROJECTS_FILES_DIR
from ..config import settings

logger = logging.getLogger(__name__)

# Extensões consideradas código-fonte para fins de indexação.
SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cpp", ".hpp",
    ".java", ".go", ".rs", ".rb", ".php",
}

# Tamanho máximo de arquivo considerado (evita ler binários gigantes por engano)
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024

# Regex genérica de fallback: captura definições de função/método/classe em
# um bom número de linguagens C-like, sem parsing real de AST.
_GENERIC_UNIT_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*"
    r"(?:function\s+\w+|class\s+\w+|def\s+\w+|\w[\w:<>,\s\*&]*\s+\w+\s*\([^;{]*\)\s*\{?)",
    re.MULTILINE,
)

_model_lock = threading.Lock()
_model = None
_model_load_attempted = False


def _ensure_model():
    """Carrega o SentenceTransformer sob demanda (mesmo padrão do router de
    agentes). Retorna o modelo ou None se indisponível."""
    global _model, _model_load_attempted
    if _model is not None:
        return _model
    if _model_load_attempted:
        return None
    with _model_lock:
        if _model is not None:
            return _model
        if _model_load_attempted:
            return None
        _model_load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _model = SentenceTransformer(settings.CODE_EMBEDDING_MODEL_NAME)
            return _model
        except Exception as e:
            logger.warning(f"Não foi possível carregar modelo de embeddings para indexação: {e}")
            return None


def _extract_python_units(source: str, file_rel_path: str) -> List[Dict[str, Any]]:
    units = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return units
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            try:
                snippet = ast.get_source_segment(source, node) or ""
            except Exception:
                snippet = ""
            units.append({
                "file": file_rel_path,
                "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                "name": node.name,
                "line": node.lineno,
                "code": snippet[:4000],  # limite defensivo por unidade
            })
    return units


def _extract_generic_units(source: str, file_rel_path: str) -> List[Dict[str, Any]]:
    units = []
    for match in _GENERIC_UNIT_RE.finditer(source):
        line_no = source.count("\n", 0, match.start()) + 1
        snippet = source[match.start(): match.start() + 800]
        name_guess = match.group(0).strip().split("(")[0].split()[-1] if match.group(0).strip() else "unidade"
        units.append({
            "file": file_rel_path,
            "kind": "unidade",
            "name": name_guess.strip(":{ "),
            "line": line_no,
            "code": snippet,
        })
    return units


def _extract_units(path: Path, file_rel_path: str) -> List[Dict[str, Any]]:
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return []
        source = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if path.suffix == ".py":
        units = _extract_python_units(source, file_rel_path)
        if units:
            return units
        # Fallback se o arquivo Python tiver erro de sintaxe
        return _extract_generic_units(source, file_rel_path)
    return _extract_generic_units(source, file_rel_path)


def index_project(project_id: str) -> Dict[str, Any]:
    """Varre backend/data/projects/{project_id}/files, extrai unidades de
    código, gera embeddings e persiste um índice FAISS em
    backend/data/projects/{project_id}/index/.

    Retorna status: {"status": "ok"|"empty"|"error", "indexed_chunks": int,
    "index_path": str, "embedding_model_available": bool, "message": str}
    """
    project_dir = PROJECTS_FILES_DIR / project_id / "files"
    index_dir = PROJECTS_FILES_DIR / project_id / "index"

    if not project_dir.exists():
        return {
            "status": "error",
            "indexed_chunks": 0,
            "index_path": str(index_dir),
            "embedding_model_available": False,
            "message": f"Diretório do projeto não encontrado: {project_dir}",
        }

    units: List[Dict[str, Any]] = []
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        rel_path = str(path.relative_to(project_dir))
        units.extend(_extract_units(path, rel_path))

    if not units:
        return {
            "status": "empty",
            "indexed_chunks": 0,
            "index_path": str(index_dir),
            "embedding_model_available": _ensure_model() is not None,
            "message": "Nenhuma unidade de código encontrada para indexar (sem arquivos-fonte reconhecidos ou diretório vazio).",
        }

    model = _ensure_model()
    if model is None:
        return {
            "status": "error",
            "indexed_chunks": 0,
            "index_path": str(index_dir),
            "embedding_model_available": False,
            "message": (
                "Modelo de embeddings indisponível (sentence-transformers não "
                "instalado ou download falhou). Indexação adiada."
            ),
        }

    try:
        import faiss  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return {
            "status": "error",
            "indexed_chunks": 0,
            "index_path": str(index_dir),
            "embedding_model_available": True,
            "message": "Dependência 'faiss-cpu' não instalada. Adicione 'faiss-cpu' ao requirements.txt.",
        }

    texts = [f"{u['kind']} {u['name']}\n{u['code']}" for u in units]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    embeddings = np.asarray(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    faiss_index = faiss.IndexFlatIP(dim)  # produto interno == cosseno, pois normalizamos
    faiss_index.add(embeddings)

    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss_index, str(index_dir / "codebase.faiss"))

    metadata = {
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": settings.CODE_EMBEDDING_MODEL_NAME,
        "chunk_count": len(units),
        "chunks": [
            {"file": u["file"], "kind": u["kind"], "name": u["name"], "line": u["line"]}
            for u in units
        ],
    }
    (index_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "status": "ok",
        "indexed_chunks": len(units),
        "index_path": str(index_dir),
        "embedding_model_available": True,
        "message": f"Indexação concluída: {len(units)} unidades de código indexadas.",
    }