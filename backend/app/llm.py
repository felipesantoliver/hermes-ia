# ===================== CLIENTE LLM LOCAL =====================
import json
import httpx
from typing import List, Dict, Any, Iterator, Optional
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

    def _resolve_model(self, model: str) -> str:
        if model == "engineer" and not self.engineer_base_url:
            logger.warning("Modo engenheiro solicitado, mas ENGINEER_MODEL_BASE_URL não configurado. Fallback para default.")
            return "default"
        return model

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
        model = self._resolve_model(model)
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

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        model: str = "default",
        **kwargs
    ) -> Iterator[str]:
        """
        Mesma requisição de generate(), mas com stream=True. O servidor
        llama-server (formato OpenAI-compatível) responde via SSE, cada
        chunk contendo um "delta" com um pedaço do texto. Este gerador
        produz esses pedaços (tokens/fragmentos) um a um, na ordem em que
        chegam, para permitir exibição incremental no frontend.

        Uso:
            for token in llm.generate_stream(messages=...):
                ...
        """
        model = self._resolve_model(model)
        url = self._get_url(model)

        payload = {
            "model": self.default_model if model == "default" else self.engineer_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }

        try:
            with self.client.stream("POST", url, json=payload, timeout=self.timeout) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    # httpx pode entregar bytes ou str dependendo da versão
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content")
                    if token:
                        yield token
        except httpx.TimeoutException:
            raise Exception(f"Timeout ao comunicar com servidor LLM em {url}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Erro HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise Exception(f"Erro ao gerar resposta (stream): {str(e)}")

# Singleton
_llm_client = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client