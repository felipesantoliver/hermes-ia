# ===================== ROTAS DE CHAT =====================
# Responsabilidade: receber mensagens do frontend e devolver a resposta do agente.
# Placeholder até o loop de agente (pensar -> agir -> observar) ser implementado.

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    mode: str | None = None  # "code" ou "think"


class ChatResponse(BaseModel):
    reply: str


@router.post("/", response_model=ChatResponse)
def send_message(payload: ChatRequest):
    """TODO: plugar o loop real do agente aqui, conforme roadmap do MVP."""
    return ChatResponse(reply=f"Recebido: {payload.message}")