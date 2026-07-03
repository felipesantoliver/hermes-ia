import sqlite3
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

# Em modo dev, BASE_DIR = backend/ (ao lado deste arquivo).
# Em modo empacotado (.exe via PyInstaller), backend/app/db.py roda de dentro
# da pasta temporária de extração (sys._MEIPASS), que é apagada ao fechar o
# app — gravar o banco lá destruiria os dados a cada reinício. Por isso o
# launcher raiz (main.py, fora do pacote) exporta HERMES_DATA_DIR apontando
# para uma pasta "data/" ao lado do Hermes-ia.exe antes de importar o app.
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
_env_data_dir = os.environ.get("HERMES_DATA_DIR")
DATA_DIR = Path(_env_data_dir).resolve() if _env_data_dir else (BASE_DIR / "data")
DB_PATH = DATA_DIR / "hermes.db"
PROJECTS_FILES_DIR = DATA_DIR / "projects"
LOOSE_FILES_DIR = DATA_DIR / "loose"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILES_DIR.mkdir(parents=True, exist_ok=True)
    LOOSE_FILES_DIR.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    persona TEXT,
    memory_scope TEXT NOT NULL DEFAULT 'isolated',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    project_id TEXT,
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS loose_files (
    id TEXT PRIMARY KEY,
    chat_id TEXT,
    origin TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS architectural_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS code_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    file_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversation_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    chat_id TEXT,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    display_name TEXT NOT NULL DEFAULT '',
    about TEXT,
    hermes_nickname TEXT,
    personality TEXT NOT NULL DEFAULT 'amigavel',
    personality_custom TEXT,
    content_filter_level INTEGER NOT NULL DEFAULT 1,
    content_filter_custom TEXT,
    warmth_level INTEGER NOT NULL DEFAULT 2,
    enthusiasm_level INTEGER NOT NULL DEFAULT 2,
    emoji_level INTEGER NOT NULL DEFAULT 2,
    use_saved_memory INTEGER NOT NULL DEFAULT 1,
    theme TEXT NOT NULL DEFAULT 'dark',
    language TEXT NOT NULL DEFAULT 'pt-br',
    ram_limit_gb INTEGER NOT NULL DEFAULT 8,
    push_on_response_done INTEGER NOT NULL DEFAULT 0,
    show_thinking INTEGER NOT NULL DEFAULT 0,
    engineer_mode_enabled INTEGER NOT NULL DEFAULT 0
);
"""


# Migrações simples e idempotentes para bancos criados antes de uma coluna
# nova existir (CREATE TABLE IF NOT EXISTS não adiciona colunas em tabelas
# já existentes). Cada entrada é (tabela, coluna, definição SQL do ALTER).
_MIGRATIONS = [
    ("user_profile", "show_thinking", "ALTER TABLE user_profile ADD COLUMN show_thinking INTEGER NOT NULL DEFAULT 0"),
    ("user_profile", "engineer_mode_enabled", "ALTER TABLE user_profile ADD COLUMN engineer_mode_enabled INTEGER NOT NULL DEFAULT 0"),
    ("user_profile", "engineer_model_path", "ALTER TABLE user_profile ADD COLUMN engineer_model_path TEXT"),
    ("user_profile", "engineer_model_url", "ALTER TABLE user_profile ADD COLUMN engineer_model_url TEXT"),
]


def _run_migrations(conn: sqlite3.Connection) -> None:
    for table, column, alter_sql in _MIGRATIONS:
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(alter_sql)


def init_db():
    ensure_dirs()
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()