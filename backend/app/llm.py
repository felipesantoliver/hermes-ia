# ===================== CLIENTE LLM LOCAL =====================
import httpx
from typing import List, Dict, Any, Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(
        self,
        base_url: str = settings.LLM_BASE_URL,
        timeout: int = settings.LLM_TIMEOUT_S,
        default_model: str = settings.LLM_DEFAULT_MODEL,
        engineer_base_url: Optional[str] = settings.ENGINEER_MODEL_BASE_URL,
        engineer_model: str = settings.ENGINEER_MODEL_NAME,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.default_model = default_model
        self.engineer_base_url = engineer_base_url.rstrip('/') if engineer_base_url else None
        self.engineer_model = engineer_model
        self.client = httpx.Client(timeout=timeout)

    def _get_url(self, model: str = "default") -> str:
        if model == "engineer" and self.engineer_base_url:
            return f"{self.engineer_base_url}/v1/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        model: str = "default",
        **kwargs
    ) -> str:
        """
        Envia mensagens para o servidor llama.cpp (formato OpenAI) e retorna a resposta.
        Se model="engineer" e ENGINEER_MODEL_BASE_URL não estiver configurado,
        retorna erro e fallback para "default".
        """
        if model == "engineer" and not self.engineer_base_url:
            logger.warning("Modo engenheiro solicitado, mas ENGINEER_MODEL_BASE_URL não configurado. Fallback para default.")
            model = "default"

        url = self._get_url(model)

        payload = {
            "model": self.default_model if model == "default" else self.engineer_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            # Espera-se o formato OpenAI: data['choices'][0]['message']['content']
            return data['choices'][0]['message']['content']
        except httpx.TimeoutException:
            raise Exception(f"Timeout ao comunicar com servidor LLM em {url}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Erro HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise Exception(f"Erro ao gerar resposta: {str(e)}")

# Singleton
_llm_client = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client