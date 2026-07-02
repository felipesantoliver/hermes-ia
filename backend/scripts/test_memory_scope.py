"""
Valida manualmente os 3 memory_scope ("isolated", "isolated_read_external",
"none") e o disjuntor geral use_saved_memory do perfil.

Roda contra o SQLite real de backend/data/hermes.db (mesmo usado pelo app).
Cria dados de teste, valida com asserts, e limpa tudo no final.

Uso:
    cd backend
    python scripts/test_memory_scope.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db, db_cursor, new_id, now_iso
from app.memory import store as memory_store
from app.memory.context_builder import build_memory_context


def make_project(memory_scope: str) -> str:
    pid = new_id()
    ts = now_iso()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO projects (id, name, description, instructions, persona, memory_scope, created_at, updated_at)
               VALUES (?, ?, '', NULL, NULL, ?, ?, ?)""",
            (pid, f"Projeto teste {memory_scope}", memory_scope, ts, ts),
        )
    return pid


def set_use_saved_memory(value: bool):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM user_profile WHERE id = 1")
        if cur.fetchone() is None:
            cur.execute("INSERT INTO user_profile (id) VALUES (1)")
        cur.execute("UPDATE user_profile SET use_saved_memory = ? WHERE id = 1", (int(value),))


def cleanup(project_ids, general_marker):
    with db_cursor() as cur:
        for pid in project_ids:
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        cur.execute("DELETE FROM architectural_memory WHERE title LIKE ?", (f"%{general_marker}%",))
        cur.execute("DELETE FROM conversation_memory WHERE summary LIKE ?", (f"%{general_marker}%",))
        cur.execute("DELETE FROM code_memory WHERE title LIKE ?", (f"%{general_marker}%",))


def main():
    init_db()
    set_use_saved_memory(True)

    marker = "TESTE_MEMORY_SCOPE"
    project_ids = []

    # ---------- Fixtures ----------
    # Memória geral (sem projeto)
    memory_store.add_architectural(None, f"{marker} decisão geral", "conteúdo geral")

    # isolated
    p_isolated = make_project("isolated")
    project_ids.append(p_isolated)
    memory_store.add_architectural(p_isolated, f"{marker} decisão isolada", "só deste projeto")

    # isolated_read_external
    p_external = make_project("isolated_read_external")
    project_ids.append(p_external)
    memory_store.add_architectural(p_external, f"{marker} decisão externa-leitura", "deste projeto")

    # none
    p_none = make_project("none")
    project_ids.append(p_none)
    memory_store.add_architectural(p_none, f"{marker} decisão modo none", "deste projeto (modo none)")

    try:
        # ---------- Teste 1: isolated não vê memória geral ----------
        ctx = build_memory_context(project_id=p_isolated, chat_id=None)
        assert "decisão isolada" in ctx, "isolated deveria conter memória do próprio projeto"
        assert "decisão geral" not in ctx, "isolated NÃO deveria conter memória geral"
        print("[OK] isolated: só enxerga memória do próprio projeto")

        # ---------- Teste 2: isolated_read_external vê projeto + geral ----------
        ctx = build_memory_context(project_id=p_external, chat_id=None)
        assert "decisão externa-leitura" in ctx, "isolated_read_external deveria conter memória do projeto"
        assert "decisão geral" in ctx, "isolated_read_external deveria também conter memória geral"
        print("[OK] isolated_read_external: enxerga memória do projeto + geral")

        # ---------- Teste 3: none trata de forma geral ----------
        ctx = build_memory_context(project_id=p_none, chat_id=None)
        assert "decisão geral" in ctx, "none deveria conter memória geral"
        print("[OK] none: tratamento geral, sem isolamento por projeto")

        # ---------- Teste 4: chat solto sempre usa memória geral ----------
        ctx = build_memory_context(project_id=None, chat_id=None)
        assert "decisão geral" in ctx, "chat solto deveria conter memória geral"
        assert "decisão isolada" not in ctx, "chat solto não deveria ver memória de projeto isolado"
        print("[OK] chat solto: sempre memória geral")

        # ---------- Teste 5: disjuntor use_saved_memory=false sobrepõe tudo ----------
        set_use_saved_memory(False)
        for pid in (p_isolated, p_external, p_none, None):
            ctx = build_memory_context(project_id=pid, chat_id=None)
            assert ctx == "", f"disjuntor desligado deveria zerar contexto (project_id={pid})"
        print("[OK] disjuntor use_saved_memory=false: nenhuma memória é injetada, em nenhum modo")

        set_use_saved_memory(True)
        print("\nTodos os testes de memory_scope passaram.")
    finally:
        cleanup(project_ids, marker)
        set_use_saved_memory(True)


if __name__ == "__main__":
    main()