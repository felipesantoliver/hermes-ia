from typing import Optional
import re

def select_agent(mode: Optional[str], user_message: str) -> str:
    """
    Heurística simples para escolher entre Desenvolvedor e Arquiteto.
    Retorna 'developer' ou 'architect'.
    """
    # Palavras-chave que indicam necessidade de arquitetura/design
    architecture_keywords = ["arquitetura", "design", "estrutura", "planejamento", "como organizar", "melhor forma", "escalabilidade"]
    # Palavras-chave que indicam desenvolvimento direto
    dev_keywords = ["código", "implementar", "função", "classe", "bug", "corrigir", "refatorar", "teste", "compilar"]

    if mode == "code":
        return "developer"
    if mode == "think":
        return "architect"

    # Análise simples por palavra-chave
    text = user_message.lower()
    if any(kw in text for kw in architecture_keywords):
        return "architect"
    if any(kw in text for kw in dev_keywords):
        return "developer"
    # Padrão
    return "developer"