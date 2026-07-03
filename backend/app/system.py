# ===================== STATUS DO SISTEMA (RAM/CPU + PRÉ-REQUISITOS) =====
# Responsabilidade: expor (1) o snapshot do ResourceMonitor para o
# frontend (indicador de uso na tela de Armazenamento, polling a cada 5s)
# e (2) o status dos pré-requisitos de inicialização (backend/llm/db/tools)
# consumido pela splash screen (frontend/js/spheres.js) durante o boot.

import httpx
from fastapi import APIRouter
from .monitor import get_monitor
from .config import settings
from .db import DB_PATH, db_cursor

router = APIRouter(prefix="/system", tags=["system"])


def _check_llm_status() -> str:
    """Consulta um health check simples no llama-server (default). Não
    bloqueia por muito tempo: timeout curto, pois isso é chamado a cada
    poll de 500ms pela splash screen."""
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(f"{settings.LLM_BASE_URL.rstrip('/')}/health")
            if resp.status_code == 200:
                return "ok"
            return "loading"
    except Exception:
        return "unavailable"


def _check_db_status() -> str:
    try:
        if not DB_PATH.exists():
            return "error"
        with db_cursor() as cur:
            cur.execute("SELECT id FROM user_profile WHERE id = 1")
        return "ok"
    except Exception:
        return "error"


def _check_tools_status() -> str:
    try:
        from .tools.registry import list_tools
        return "ok" if list_tools() else "initializing"
    except Exception:
        return "initializing"


@router.get("/status")
def get_system_status():
    """Retorna CPU%, RAM usada/limite e número de processos ativos do
    backend. force_refresh=True garante uma leitura fresca mesmo que o
    tick de background ainda não tenha rodado."""
    monitor = get_monitor()
    return monitor.get_status(force_refresh=True)


@router.get("/prereqs")
def get_system_prereqs():
    """Status dos pré-requisitos de boot, usado pela splash screen:
    - backend: sempre "ok" quando esta rota responde (FastAPI já está de pé).
    - llm: "ok" | "loading" | "unavailable" (health check no llama-server).
    - db: "ok" | "error" (SQLite inicializado e tabela user_profile existe).
    - tools: "ok" | "initializing" (registry de tools carregado).
    """
    return {
        "backend": "ok",
        "llm": _check_llm_status(),
        "db": _check_db_status(),
        "tools": _check_tools_status(),
    }


@router.get("/engineer-info")
def get_engineer_info():
    """Metadados do modo engenheiro (link de download e onde instalar o
    modelo maior), usados pelo painel de configurações. O modo em si
    continua opcional e desligado por padrão."""
    return {
        "download_url": settings.ENGINEER_MODEL_DOWNLOAD_URL,
        "install_dir": settings.ENGINEER_MODEL_INSTALL_DIR,
        "configured": bool(settings.ENGINEER_MODEL_BASE_URL) or bool(settings.ENGINEER_MODEL_PATH),
    }


@router.get("/test-engineer")
def test_engineer():
    """Testa a conectividade com o modelo engenheiro (servidor ou embarcado)."""
    from .llm import get_llm_client
    client = get_llm_client()
    if not client.has_engineer():
        return {"status": "unavailable", "message": "Modelo engenheiro não configurado"}
    try:
        response = client.generate(
            messages=[{"role": "user", "content": "Diga 'ok'"}],
            max_tokens=10,
            model="engineer"
        )
        return {"status": "ok", "message": "Conexão bem-sucedida", "response": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}