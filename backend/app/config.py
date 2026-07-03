# ===================== CONFIGURAÇÕES GERAIS DO BACKEND =====================
# Responsabilidade: centralizar parâmetros configuráveis do projeto.

import os
from pathlib import Path
from typing import Optional

# Em modo empacotado (.exe via PyInstaller --onefile), o backend roda de
# dentro da pasta temporária de extração (sys._MEIPASS), então caminhos
# relativos como "./models/..." não apontam para a pasta "models/" real ao
# lado do Hermes-ia.exe. O launcher raiz (main.py) exporta HERMES_BASE_DIR
# com o diretório do executável antes de importar o app; em modo dev, sem
# essa env var, tudo continua relativo à raiz do repo, como antes.
_env_base_dir = os.environ.get("HERMES_BASE_DIR")
_BASE_DIR = Path(_env_base_dir).resolve() if _env_base_dir else None


def _resolve(relative_path: str) -> str:
    """Resolve um caminho relativo contra HERMES_BASE_DIR quando definido
    (modo empacotado); caso contrário devolve o caminho relativo original
    (modo dev, comportamento inalterado)."""
    if _BASE_DIR is None:
        return relative_path
    return str(_BASE_DIR / relative_path.lstrip("./"))


class Settings:
    APP_NAME: str = "Hermes AI"
    VERSION: str = "0.2.0"  # V2

    # Caminho local do modelo LLM (ajustar conforme sua instalação)
    MODEL_PATH: str = _resolve("./models/hermes-core.gguf")

    # Respeita o hardware alvo do projeto (16GB RAM)
    MAX_CONTEXT_TOKENS: int = 4096

    # Configurações do servidor llama.cpp (API compatível OpenAI)
    LLM_BASE_URL: str = "http://localhost:8080"
    LLM_TIMEOUT_S: int = 60
    LLM_DEFAULT_MODEL: str = "default"  # nome do modelo no servidor (se houver)

    # Modo engenheiro (opcional) - V2.1
    # 100% opt-in: o sistema roda de ponta a ponta sem isso. O usuário liga
    # explicitamente em Configurações > Armazenamento, ciente do requisito de
    # hardware extra (VRAM/RAM), e baixa o modelo manualmente para a pasta
    # que o backend aponta (ENGINEER_MODEL_INSTALL_DIR) — é essa pasta que o
    # llama-server do "modo engenheiro" precisa apontar/servir.
    ENGINEER_MODEL_BASE_URL: Optional[str] = None  # ex: "http://localhost:8081"
    ENGINEER_MODEL_NAME: str = "engineer"
    ENGINEER_MODEL_DOWNLOAD_URL: str = "https://huggingface.co/models?search=qwen+gguf"
    ENGINEER_MODEL_INSTALL_DIR: str = _resolve("./models/engineer/")
    ENGINEER_MODEL_PATH: str = ""  # caminho do arquivo .gguf para carregamento embarcado (opcional)

    # SearXNG local (WebSearchTool) - instância self-hosted, não serviço externo
    SEARXNG_BASE_URL: str = "http://localhost:8081"

    # CodebaseIndexTool - mesmo modelo de embeddings usado no router de agentes
    CODE_EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"


settings = Settings()