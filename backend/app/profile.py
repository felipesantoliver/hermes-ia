from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .db import db_cursor

router = APIRouter(prefix="/profile", tags=["profile"])

VALID_PERSONALITIES = {"amigavel", "sarcastico", "direto", "tecnico", "personalizado"}


class ProfileOut(BaseModel):
    display_name: str
    about: Optional[str]
    hermes_nickname: Optional[str]
    personality: str
    personality_custom: Optional[str]
    content_filter_level: int
    content_filter_custom: Optional[str]
    warmth_level: int
    enthusiasm_level: int
    emoji_level: int
    use_saved_memory: bool
    theme: str
    language: str
    ram_limit_gb: int
    push_on_response_done: bool


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    about: Optional[str] = None
    hermes_nickname: Optional[str] = None
    personality: Optional[str] = None
    personality_custom: Optional[str] = None
    content_filter_level: Optional[int] = None
    content_filter_custom: Optional[str] = None
    warmth_level: Optional[int] = None
    enthusiasm_level: Optional[int] = None
    emoji_level: Optional[int] = None
    use_saved_memory: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    ram_limit_gb: Optional[int] = None
    push_on_response_done: Optional[bool] = None


def _row_to_profile(row) -> dict:
    return {
        "display_name": row["display_name"],
        "about": row["about"],
        "hermes_nickname": row["hermes_nickname"],
        "personality": row["personality"],
        "personality_custom": row["personality_custom"],
        "content_filter_level": row["content_filter_level"],
        "content_filter_custom": row["content_filter_custom"],
        "warmth_level": row["warmth_level"],
        "enthusiasm_level": row["enthusiasm_level"],
        "emoji_level": row["emoji_level"],
        "use_saved_memory": bool(row["use_saved_memory"]),
        "theme": row["theme"],
        "language": row["language"],
        "ram_limit_gb": row["ram_limit_gb"],
        "push_on_response_done": bool(row["push_on_response_done"]),
    }


def _ensure_profile(cur):
    cur.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO user_profile (id) VALUES (1)")
        cur.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cur.fetchone()
    return row


@router.get("/", response_model=ProfileOut)
def get_profile():
    with db_cursor() as cur:
        row = _ensure_profile(cur)
        return _row_to_profile(row)


@router.patch("/", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate):
    fields = payload.dict(exclude_unset=True)

    if "personality" in fields and fields["personality"] not in VALID_PERSONALITIES:
        raise HTTPException(status_code=422, detail=f"personality inválida: {fields['personality']}")

    if "content_filter_level" in fields:
        lvl = fields["content_filter_level"]
        if lvl not in (1, 2, 3, 4, -1):
            raise HTTPException(status_code=422, detail="content_filter_level deve ser 1-4 ou -1 (custom)")

    for key in ("warmth_level", "enthusiasm_level", "emoji_level"):
        if key in fields and fields[key] not in (1, 2, 3):
            raise HTTPException(status_code=422, detail=f"{key} deve estar entre 1 e 3")

    with db_cursor() as cur:
        _ensure_profile(cur)
        if not fields:
            cur.execute("SELECT * FROM user_profile WHERE id = 1")
            return _row_to_profile(cur.fetchone())

        for k in ("use_saved_memory", "push_on_response_done"):
            if k in fields:
                fields[k] = int(fields[k])

        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values())
        cur.execute(f"UPDATE user_profile SET {set_clause} WHERE id = 1", values)
        cur.execute("SELECT * FROM user_profile WHERE id = 1")
        return _row_to_profile(cur.fetchone())