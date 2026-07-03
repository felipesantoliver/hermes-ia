# ===================== PONTO DE ENTRADA DO BACKEND =====================
# Responsabilidade: criar a aplicação FastAPI, registrar todas as rotas e
# (novo, empacotamento Windows) servir o frontend como estático, para que
# a janela nativa do pywebview aponte só para http://127.0.0.1:8000/ — sem
# precisar de um servidor HTTP separado para os arquivos estáticos.

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.chat import router as chat_router
from app.projects import router as projects_router
from app.chats import router as chats_router
from app.profile import router as profile_router
from app.files import router as files_router
from app.system import router as system_router

from app.db import init_db
from app.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)

# Inicialização do banco (se necessário no startup)
init_db()


# --------------------- CORS ---------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------- ROUTERS ---------------------
# Cada router já declara seu próprio prefix (ver app/projects.py, chats.py,
# files.py, profile.py) — NÃO repetir o prefix aqui, senão as rotas ficam
# duplicadas (ex: /projects/projects/...) e o frontend, que chama /projects/,
# /chats/, /files/, /profile/ diretamente, recebe 404 em tudo.
# IMPORTANTE: todos os routers de API precisam ser registrados ANTES do
# mount do StaticFiles lá embaixo — o Starlette resolve rotas na ordem em
# que foram adicionadas, então se o mount "/" viesse primeiro ele engoliria
# as chamadas de API antes de chegarem nos routers.
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(projects_router, tags=["projects"])
app.include_router(chats_router, tags=["chats"])
app.include_router(profile_router, tags=["profile"])
app.include_router(files_router, tags=["files"])
app.include_router(system_router, tags=["system"])


# --------------------- HEALTHCHECK (API) ---------------------
@app.get("/api/health")
def health():
    """Verificação simples de que o backend está no ar. Usado por scripts e
    pelo launcher do .exe antes de servir a UI (ver system.get_system_prereqs
    para o healthcheck mais completo, consumido pela splash screen)."""
    return {"status": f"{settings.APP_NAME} backend no ar"}


# --------------------- FRONTEND ESTÁTICO ---------------------
# Em modo dev: frontend/ ao lado de backend/ (raiz do repo).
# Em modo empacotado: o launcher (main.py, raiz) exporta HERMES_FRONTEND_DIR
# apontando para a pasta frontend/ extraída pelo PyInstaller (--add-data
# "frontend;frontend"), dentro de sys._MEIPASS.
_env_frontend_dir = os.environ.get("HERMES_FRONTEND_DIR")
if _env_frontend_dir:
    FRONTEND_DIR = Path(_env_frontend_dir).resolve()
else:
    FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # html=True: serve index.html em "/" e em qualquer subpasta sem arquivo
    # correspondente (fallback de SPA). Precisa ser o ÚLTIMO app.mount/route.
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")