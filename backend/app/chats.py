from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .db import db_cursor, new_id, now_iso

router = APIRouter(prefix="/chats", tags=["chats"])


# ---------- Schemas ----------

class ChatCreate(BaseModel):
    title: str = Field(..., min_length=1)
    project_id: Optional[str] = None


class ChatUpdate(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    project_id: Optional[str] = None  # pode ser setado para None para "tirar do projeto"


class ChatOut(BaseModel):
    id: str
    title: str
    project_id: Optional[str]
    pinned: bool
    archived: bool
    created_at: str
    updated_at: str


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|hermes)$")
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    created_at: str


# ---------- Helpers ----------

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


def _row_to_message(row) -> dict:
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def _get_chat_or_404(cur, chat_id: str):
    cur.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Chat não encontrado")
    return row


# ---------- Routes ----------

@router.get("/", response_model=List[ChatOut])
def list_chats(scope: Optional[str] = Query(None)):
    with db_cursor() as cur:
        if scope == "sidebar":
            cur.execute(
                """SELECT * FROM chats WHERE project_id IS NULL AND archived = 0
                   ORDER BY pinned DESC, updated_at DESC"""
            )
        else:
            cur.execute("SELECT * FROM chats ORDER BY pinned DESC, updated_at DESC")
        return [_row_to_chat(r) for r in cur.fetchall()]


@router.post("/", response_model=ChatOut, status_code=201)
def create_chat(payload: ChatCreate):
    with db_cursor() as cur:
        if payload.project_id:
            cur.execute("SELECT id FROM projects WHERE id = ?", (payload.project_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Projeto não encontrado")

        cid = new_id()
        ts = now_iso()
        cur.execute(
            """INSERT INTO chats (id, title, project_id, pinned, archived, created_at, updated_at)
               VALUES (?, ?, ?, 0, 0, ?, ?)""",
            (cid, payload.title, payload.project_id, ts, ts),
        )
        cur.execute("SELECT * FROM chats WHERE id = ?", (cid,))
        return _row_to_chat(cur.fetchone())


@router.patch("/{chat_id}", response_model=ChatOut)
def update_chat(chat_id: str, payload: ChatUpdate):
    with db_cursor() as cur:
        _get_chat_or_404(cur, chat_id)

        fields = payload.dict(exclude_unset=True)
        if "project_id" in fields and fields["project_id"] is not None:
            cur.execute("SELECT id FROM projects WHERE id = ?", (fields["project_id"],))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Projeto não encontrado")

        if not fields:
            cur.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
            return _row_to_chat(cur.fetchone())

        # bool -> int para sqlite
        for k in ("pinned", "archived"):
            if k in fields:
                fields[k] = int(fields[k])

        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [now_iso(), chat_id]
        cur.execute(f"UPDATE chats SET {set_clause}, updated_at = ? WHERE id = ?", values)
        cur.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
        return _row_to_chat(cur.fetchone())


@router.delete("/", status_code=204)
def delete_chats_bulk(scope: str = Query(...)):
    if scope not in ("all", "non_project"):
        raise HTTPException(status_code=422, detail="scope deve ser 'all' ou 'non_project'")
    with db_cursor() as cur:
        if scope == "all":
            cur.execute("DELETE FROM chats")
        else:
            cur.execute("DELETE FROM chats WHERE project_id IS NULL")
    return None


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: str):
    with db_cursor() as cur:
        _get_chat_or_404(cur, chat_id)
        cur.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    return None


@router.get("/{chat_id}/messages", response_model=List[MessageOut])
def list_messages(chat_id: str):
    with db_cursor() as cur:
        _get_chat_or_404(cur, chat_id)
        cur.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
        return [_row_to_message(r) for r in cur.fetchall()]


@router.post("/{chat_id}/messages", response_model=MessageOut, status_code=201)
def create_message(chat_id: str, payload: MessageCreate):
    with db_cursor() as cur:
        _get_chat_or_404(cur, chat_id)
        mid = new_id()
        ts = now_iso()
        cur.execute(
            """INSERT INTO messages (id, chat_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (mid, chat_id, payload.role, payload.content, ts),
        )
        cur.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (ts, chat_id))
        cur.execute("SELECT * FROM messages WHERE id = ?", (mid,))
        return _row_to_message(cur.fetchone())