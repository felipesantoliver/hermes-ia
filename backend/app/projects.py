import os
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field

from .db import db_cursor, new_id, now_iso, PROJECTS_FILES_DIR
from .memory import store as memory_store
from .orchestrator.context_builder import build_memory_context

router = APIRouter(prefix="/projects", tags=["projects"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
VALID_MEMORY_SCOPES = {"isolated", "isolated_read_external", "none"}


# ---------- Schemas ----------

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    instructions: Optional[str] = None
    persona: Optional[str] = None
    memory_scope: Optional[str] = "isolated"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    persona: Optional[str] = None
    memory_scope: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    instructions: Optional[str]
    persona: Optional[str]
    memory_scope: str
    created_at: str
    updated_at: str


class ProjectFileOut(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    size_bytes: int
    uploaded_at: str


class ChatOut(BaseModel):
    id: str
    title: str
    project_id: Optional[str]
    pinned: bool
    archived: bool
    created_at: str
    updated_at: str


# ---------- Helpers ----------

def _row_to_project(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "instructions": row["instructions"],
        "persona": row["persona"],
        "memory_scope": row["memory_scope"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_chat(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "project_id": row["project_id"],
        "pinned": bool(row["pinned"]),
        "archived": bool(row["archived"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_project_or_404(cur, project_id: str):
    cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return row


# ---------- Routes ----------

@router.get("/", response_model=List[ProjectOut])
def list_projects():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        return [_row_to_project(r) for r in cur.fetchall()]


@router.post("/", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate):
    scope = payload.memory_scope or "isolated"
    if scope not in VALID_MEMORY_SCOPES:
        raise HTTPException(status_code=422, detail=f"memory_scope inválido: {scope}")
    pid = new_id()
    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO projects (id, name, description, instructions, persona, memory_scope, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, payload.name, payload.description, payload.instructions, payload.persona, scope, ts, ts),
        )
        cur.execute("SELECT * FROM projects WHERE id = ?", (pid,))
        return _row_to_project(cur.fetchone())


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)

        fields = payload.dict(exclude_unset=True)
        if "memory_scope" in fields and fields["memory_scope"] not in VALID_MEMORY_SCOPES:
            raise HTTPException(status_code=422, detail=f"memory_scope inválido: {fields['memory_scope']}")
        if not fields:
            cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            return _row_to_project(cur.fetchone())

        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [now_iso(), project_id]
        cur.execute(f"UPDATE projects SET {set_clause}, updated_at = ? WHERE id = ?", values)
        cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return _row_to_project(cur.fetchone())


@router.delete("/", status_code=204)
def delete_all_projects(scope: str = Query(...)):
    if scope != "all":
        raise HTTPException(status_code=422, detail="Use ?scope=all para apagar todos os projetos")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM projects")
        ids = [r["id"] for r in cur.fetchall()]
        cur.execute("DELETE FROM projects")
    for pid in ids:
        folder = PROJECTS_FILES_DIR / pid
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    return None


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    folder = PROJECTS_FILES_DIR / project_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    return None


@router.post("/{project_id}/files", response_model=ProjectFileOut, status_code=201)
async def upload_project_file(project_id: str, file: UploadFile = File(...)):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Extensão '{ext}' não permitida. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Arquivo excede o tamanho máximo de 20MB")

    fid = new_id()
    folder = PROJECTS_FILES_DIR / project_id / "files"
    folder.mkdir(parents=True, exist_ok=True)
    stored_path = folder / f"{fid}{ext}"
    with open(stored_path, "wb") as f:
        f.write(contents)

    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO project_files (id, project_id, filename, file_type, stored_path, size_bytes, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (fid, project_id, file.filename, ext.lstrip("."), str(stored_path), len(contents), ts),
        )
        cur.execute("SELECT * FROM project_files WHERE id = ?", (fid,))
        row = cur.fetchone()
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "size_bytes": row["size_bytes"],
            "uploaded_at": row["uploaded_at"],
        }


@router.get("/{project_id}/files", response_model=List[ProjectFileOut])
def list_project_files(project_id: str):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)
        cur.execute("SELECT * FROM project_files WHERE project_id = ? ORDER BY uploaded_at DESC", (project_id,))
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "size_bytes": r["size_bytes"],
                "uploaded_at": r["uploaded_at"],
            }
            for r in cur.fetchall()
        ]


@router.delete("/{project_id}/files/{file_id}", status_code=204)
def delete_project_file(project_id: str, file_id: str):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)
        cur.execute("SELECT * FROM project_files WHERE id = ? AND project_id = ?", (file_id, project_id))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        cur.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
    path = Path(row["stored_path"])
    if path.exists():
        path.unlink()
    return None


@router.get("/{project_id}/chats", response_model=List[ChatOut])
def list_project_chats(project_id: str):
    with db_cursor() as cur:
        _get_project_or_404(cur, project_id)
        cur.execute(
            "SELECT * FROM chats WHERE project_id = ? ORDER BY pinned DESC, updated_at DESC",
            (project_id,),
        )
        return [_row_to_chat(r) for r in cur.fetchall()]

@router.get("/{project_id}/memory")
def debug_project_memory(project_id: str):
    """
    Rota de debug: mostra a memória crua das 3 camadas para o projeto
    (sem aplicar orçamento de tokens) e o bloco final que seria
    efetivamente injetado no system prompt, já respeitando memory_scope
    e o disjuntor use_saved_memory.
    """
    with db_cursor() as cur:
        proj = _get_project_or_404(cur, project_id)

    scope = proj["memory_scope"]
    include_external = scope == "isolated_read_external"

    raw = {
        "memory_scope": scope,
        "use_saved_memory": memory_store.get_use_saved_memory(),
        "architectural_memory": memory_store.list_architectural(project_id, include_external=include_external),
        "conversation_memory": memory_store.list_conversation_memory(project_id, include_external=include_external),
        "code_memory": memory_store.list_code_memory(project_id, include_external=include_external),
    }
    raw["resolved_context"] = build_memory_context(project_id=project_id, chat_id=None)
    return raw
