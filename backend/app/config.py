# ===================== CONFIGURAÇÕES GERAIS DO BACKEND =====================
# Responsabilidade: centralizar parâmetros configuráveis do projeto.

from typing import Optional

class Settings:
    APP_NAME: str = "Hermes AI"
    VERSION: str = "0.1.0"

    # Caminho local do modelo LLM (ajustar conforme sua instalação)
    MODEL_PATH: str = "./models/hermes-core.gguf"

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
    ENGINEER_MODEL_INSTALL_DIR: str = "./models/engineer/"

    # SearXNG local (WebSearchTool) - instância self-hosted, não serviço externo
    SEARXNG_BASE_URL: str = "http://localhost:8081"

    # CodebaseIndexTool - mesmo modelo de embeddings usado no router de agentes
    CODE_EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"


settings = Settings()