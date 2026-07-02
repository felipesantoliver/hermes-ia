# ===================== PONTO DE ENTRADA DO BACKEND =====================
# Responsabilidade: criar a aplicação FastAPI e registrar todas as rotas.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat import router as chat_router
from app.projects import router as projects_router
from app.chats import router as chats_router
from app.profile import router as profile_router
from app.files import router as files_router

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
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(chats_router, prefix="/chats", tags=["chats"])
app.include_router(profile_router, prefix="/profile", tags=["profile"])
app.include_router(files_router, prefix="/files", tags=["files"])


# --------------------- HEALTHCHECK ---------------------
@app.get("/")
def root():
    """Verificação simples de que o backend está no ar."""
    return {"status": f"{settings.APP_NAME} backend no ar"}