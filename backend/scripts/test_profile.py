"""
Valida:
  1. GET/PATCH /profile persistem corretamente no SQLite (sem subir servidor
     HTTP de verdade — chama as funções da rota diretamente, como
     test_memory_scope.py faz para o módulo de memória).
  2. build_profile_system_section() (usado por chat.py) reflete os valores
     salvos: nickname, display_name, about, personality (+ custom),
     warmth/enthusiasm/emoji, content_filter_level (+ custom), e que o piso
     de segurança fixo aparece em QUALQUER nível de filtro, incluindo o 1
     ("sem filtro") e o custom.

Uso:
    cd backend
    python scripts/test_profile.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db, db_cursor
from app.profile import get_profile, update_profile, ProfileUpdate
from app.profile_prompt import build_profile_system_section, SAFETY_FLOOR


def snapshot_profile() -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cur.fetchone()
        return dict(row) if row else None


def restore_profile(snapshot):
    with db_cursor() as cur:
        if snapshot is None:
            cur.execute("DELETE FROM user_profile WHERE id = 1")
            return
        cols = ", ".join(f"{k} = ?" for k in snapshot.keys() if k != "id")
        values = [v for k, v in snapshot.items() if k != "id"]
        cur.execute(f"UPDATE user_profile SET {cols} WHERE id = 1", values)


def main():
    init_db()
    original = snapshot_profile()

    try:
        # ---------- Teste 1: PATCH persiste no banco ----------
        update_profile(ProfileUpdate(
            display_name="Felipe",
            hermes_nickname="H",
            about="Desenvolvedor focado em firmware e IA local.",
            personality="tecnico",
            content_filter_level=1,
            warmth_level=3,
            enthusiasm_level=1,
            emoji_level=2,
            use_saved_memory=True,
        ))
        profile = get_profile()
        assert profile["display_name"] == "Felipe"
        assert profile["hermes_nickname"] == "H"
        assert profile["personality"] == "tecnico"
        assert profile["content_filter_level"] == 1
        assert profile["warmth_level"] == 3
        assert profile["enthusiasm_level"] == 1
        assert profile["emoji_level"] == 2
        print("[OK] PATCH /profile persiste os campos corretamente")

        # ---------- Teste 2: system prompt reflete nickname/nome/about/tecnico ----------
        section = build_profile_system_section(profile)
        assert "H" in section and "apelido" in section.lower()
        assert "Felipe" in section
        assert "Desenvolvedor focado em firmware" in section
        assert "altamente técnico" in section.lower()
        print("[OK] system prompt reflete nickname, display_name, about e personalidade")

        # ---------- Teste 3: filtro nível 1 (sem filtro) não é hedgeado, mas piso de segurança está presente ----------
        assert "sem filtro" in section.lower()
        assert SAFETY_FLOOR in section
        print("[OK] nível 1 (sem filtro) presente + piso de segurança fixo sempre incluído")

        # ---------- Teste 4: personalidade personalizada usa personality_custom ----------
        update_profile(ProfileUpdate(
            personality="personalizado",
            personality_custom="Fale como um mentor experiente, sem formalidades.",
        ))
        profile = get_profile()
        section = build_profile_system_section(profile)
        assert "mentor experiente" in section
        assert SAFETY_FLOOR in section
        print("[OK] personality=personalizado usa personality_custom + piso de segurança mantido")

        # ---------- Teste 5: filtro custom (-1) usa content_filter_custom, sem revogar o piso ----------
        update_profile(ProfileUpdate(
            content_filter_level=-1,
            content_filter_custom="Evite falar sobre política partidária.",
        ))
        profile = get_profile()
        section = build_profile_system_section(profile)
        assert "Evite falar sobre política partidária." in section
        assert SAFETY_FLOOR in section
        print("[OK] filtro custom (-1) aplica content_filter_custom + piso de segurança mantido")

        # ---------- Teste 6: piso de segurança aparece em TODOS os níveis 1-4 ----------
        for level in (1, 2, 3, 4):
            update_profile(ProfileUpdate(content_filter_level=level))
            profile = get_profile()
            section = build_profile_system_section(profile)
            assert SAFETY_FLOOR in section, f"piso de segurança ausente no nível {level}"
        print("[OK] piso de segurança presente em todos os níveis (1 a 4)")

        # ---------- Teste 7: sem perfil configurado, piso de segurança ainda aparece ----------
        section_no_profile = build_profile_system_section(None)
        assert SAFETY_FLOOR in section_no_profile
        print("[OK] piso de segurança presente mesmo sem perfil configurado")

        print("\nTodos os testes de perfil passaram.")
    finally:
        restore_profile(original)


if __name__ == "__main__":
    main()