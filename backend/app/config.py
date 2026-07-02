# ===================== CONFIGURAÇÕES GERAIS DO BACKEND =====================
# Responsabilidade: centralizar parâmetros configuráveis do projeto.

class Settings:
    APP_NAME: str = "Hermes AI"
    VERSION: str = "0.1.0"

    # Caminho local do modelo LLM (ajustar conforme sua instalação)
    MODEL_PATH: str = "./models/hermes-core.gguf"

    # Respeita o hardware alvo do projeto (16GB RAM)
    MAX_CONTEXT_TOKENS: int = 4096


settings = Settings()