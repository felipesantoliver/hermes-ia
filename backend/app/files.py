from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .db import db_cursor, new_id, now_iso, LOOSE_FILES_DIR

router = APIRouter(prefix="/files", tags=["files"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class LooseFileOut(BaseModel):
    id: str
    chat_id: Optional[str]
    origin: str
    filename: str
    file_type: str
    size_bytes: int
    created_at: str


class GalleryItemOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    created_at: str
    source: str            # "loose" | "project"
    origin: Optional[str]  # "upload" | "generated" (só para loose)
    chat_id: Optional[str]
    project_id: Optional[str]


def _row_to_loose(row) -> dict:
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "origin": row["origin"],
        "filename": row["filename"],
        "file_type": row["file_type"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
    }


@router.post("/upload", response_model=LooseFileOut, status_code=201)
async def upload_loose_file(chat_id: Optional[str] = None, file: UploadFile = File(...)):
    with db_cursor() as cur:
        if chat_id:
            cur.execute("SELECT id FROM chats WHERE id = ?", (chat_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Chat não encontrado")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Arquivo excede o tamanho máximo de 20MB")

    ext = Path(file.filename).suffix.lower()
    fid = new_id()
    LOOSE_FILES_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = LOOSE_FILES_DIR / f"{fid}{ext}"
    with open(stored_path, "wb") as f:
        f.write(contents)

    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO loose_files (id, chat_id, origin, filename, file_type, stored_path, size_bytes, created_at)
               VALUES (?, ?, 'upload', ?, ?, ?, ?, ?)""",
            (fid, chat_id, file.filename, ext.lstrip("."), str(stored_path), len(contents), ts),
        )
        cur.execute("SELECT * FROM loose_files WHERE id = ?", (fid,))
        return _row_to_loose(cur.fetchone())


def save_generated_file(chat_id: Optional[str], filename: str, path: str) -> dict:
    """Helper interno: registra um arquivo já gerado em disco (por tools, MVP.5+)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo gerado não encontrado em disco: {path}")

    fid = new_id()
    ext = p.suffix.lower().lstrip(".")
    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO loose_files (id, chat_id, origin, filename, file_type, stored_path, size_bytes, created_at)
               VALUES (?, ?, 'generated', ?, ?, ?, ?, ?)""",
            (fid, chat_id, filename, ext, str(p), p.stat().st_size, ts),
        )
        cur.execute("SELECT * FROM loose_files WHERE id = ?", (fid,))
        return _row_to_loose(cur.fetchone())


@router.get("/", response_model=List[LooseFileOut])
def list_loose_files(origin: Optional[str] = None, chat_id: Optional[str] = None):
    query = "SELECT * FROM loose_files WHERE 1=1"
    params = []
    if origin:
        query += " AND origin = ?"
        params.append(origin)
    if chat_id:
        query += " AND chat_id = ?"
        params.append(chat_id)
    query += " ORDER BY created_at DESC"

    with db_cursor() as cur:
        cur.execute(query, params)
        return [_row_to_loose(r) for r in cur.fetchall()]


@router.get("/all-sources", response_model=List[GalleryItemOut])
def list_all_sources():
    items = []
    with db_cursor() as cur:
        cur.execute("SELECT * FROM loose_files ORDER BY created_at DESC")
        for r in cur.fetchall():
            items.append({
                "id": r["id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "size_bytes": r["size_bytes"],
                "created_at": r["created_at"],
                "source": "loose",
                "origin": r["origin"],
                "chat_id": r["chat_id"],
                "project_id": None,
            })

        cur.execute("SELECT * FROM project_files ORDER BY uploaded_at DESC")
        for r in cur.fetchall():
            items.append({
                "id": r["id"],
                "filename": r["filename"],
                "file_type": r["file_type"],
                "size_bytes": r["size_bytes"],
                "created_at": r["uploaded_at"],
                "source": "project",
                "origin": "upload",
                "chat_id": None,
                "project_id": r["project_id"],
            })

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


@router.get("/{file_id}/download")
def download_loose_file(file_id: str):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM loose_files WHERE id = ?", (file_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    path = Path(row["stored_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado em disco")
    return FileResponse(path, filename=row["filename"])


@router.delete("/{file_id}", status_code=204)
def delete_loose_file(file_id: str):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM loose_files WHERE id = ?", (file_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        cur.execute("DELETE FROM loose_files WHERE id = ?", (file_id,))
    path = Path(row["stored_path"])
    if path.exists():
        path.unlink()
    return None