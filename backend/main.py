# ===================== PONTO DE ENTRADA DO BACKEND =====================
# Responsabilidade: criar a aplicação FastAPI e registrar as rotas de chat.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chat import router as chat_router

app = FastAPI(title="Hermes AI - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/chat", tags=["chat"])


@app.get("/")
def root():
    """Verificação simples de que o backend está no ar."""
    return {"status": "Hermes backend no ar"}