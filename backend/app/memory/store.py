# ===================== ACESSO A DADOS DA MEMÓRIA =====================
# Responsabilidade: CRUD cru das 3 tabelas de memória. Não decide o que
# entra no contexto do LLM — isso é papel do context_builder.py.

from typing import Optional, List
from ..db import db_cursor, new_id, now_iso


def _row_to_architectural(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "title": row["title"],
        "content": row["content"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_code(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "title": row["title"],
        "content": row["content"],
        "file_ref": row["file_ref"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_conversation(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "chat_id": row["chat_id"],
        "summary": row["summary"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------- Escrita ----------

def add_architectural(project_id: Optional[str], title: str, content: str) -> dict:
    ts = now_iso()
    mid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO architectural_memory (id, project_id, title, content, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mid, project_id, title, content, ts, ts),
        )
        cur.execute("SELECT * FROM architectural_memory WHERE id = ?", (mid,))
        return _row_to_architectural(cur.fetchone())


def add_code_memory(project_id: Optional[str], title: str, content: str, file_ref: Optional[str] = None) -> dict:
    ts = now_iso()
    mid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO code_memory (id, project_id, title, content, file_ref, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mid, project_id, title, content, file_ref, ts, ts),
        )
        cur.execute("SELECT * FROM code_memory WHERE id = ?", (mid,))
        return _row_to_code(cur.fetchone())


def add_conversation_summary(project_id: Optional[str], chat_id: Optional[str], summary: str) -> dict:
    ts = now_iso()
    mid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO conversation_memory (id, project_id, chat_id, summary, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mid, project_id, chat_id, summary, ts, ts),
        )
        cur.execute("SELECT * FROM conversation_memory WHERE id = ?", (mid,))
        return _row_to_conversation(cur.fetchone())


# ---------- Leitura ----------
# Todas aceitam project_id=None para buscar memória "geral" (chats soltos).
# include_external permite, no modo isolated_read_external, ler também a
# memória geral (project_id IS NULL) além da do projeto.

def list_architectural(project_id: Optional[str], include_external: bool = False) -> List[dict]:
    with db_cursor() as cur:
        if project_id is None:
            cur.execute(
                "SELECT * FROM architectural_memory WHERE project_id IS NULL ORDER BY updated_at DESC"
            )
        elif include_external:
            cur.execute(
                "SELECT * FROM architectural_memory WHERE project_id = ? OR project_id IS NULL ORDER BY updated_at DESC",
                (project_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM architectural_memory WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            )
        return [_row_to_architectural(r) for r in cur.fetchall()]


def list_code_memory(project_id: Optional[str], include_external: bool = False) -> List[dict]:
    with db_cursor() as cur:
        if project_id is None:
            cur.execute(
                "SELECT * FROM code_memory WHERE project_id IS NULL ORDER BY updated_at DESC"
            )
        elif include_external:
            cur.execute(
                "SELECT * FROM code_memory WHERE project_id = ? OR project_id IS NULL ORDER BY updated_at DESC",
                (project_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM code_memory WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            )
        return [_row_to_code(r) for r in cur.fetchall()]


def list_conversation_memory(project_id: Optional[str], include_external: bool = False) -> List[dict]:
    with db_cursor() as cur:
        if project_id is None:
            cur.execute(
                "SELECT * FROM conversation_memory WHERE project_id IS NULL ORDER BY updated_at DESC"
            )
        elif include_external:
            cur.execute(
                "SELECT * FROM conversation_memory WHERE project_id = ? OR project_id IS NULL ORDER BY updated_at DESC",
                (project_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM conversation_memory WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            )
        return [_row_to_conversation(r) for r in cur.fetchall()]


def get_use_saved_memory() -> bool:
    """Lê o disjuntor geral do perfil do usuário (id=1)."""
    with db_cursor() as cur:
        cur.execute("SELECT use_saved_memory FROM user_profile WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            return True  # default do schema é 1
        return bool(row["use_saved_memory"])


def get_project_memory_scope(project_id: str) -> Optional[str]:
    with db_cursor() as cur:
        cur.execute("SELECT memory_scope FROM projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return row["memory_scope"] if row else None