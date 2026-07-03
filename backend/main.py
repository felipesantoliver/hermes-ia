# ===================== PONTO DE ENTRADA DO BACKEND =====================
# Responsabilidade: criar a aplicação FastAPI e registrar todas as rotas.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(projects_router, tags=["projects"])
app.include_router(chats_router, tags=["chats"])
app.include_router(profile_router, tags=["profile"])
app.include_router(files_router, tags=["files"])
app.include_router(system_router, tags=["system"])


# --------------------- HEALTHCHECK ---------------------
@app.get("/")
def root():
    """Verificação simples de que o backend está no ar."""
    return {"status": f"{settings.APP_NAME} backend no ar"}