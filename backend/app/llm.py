# ===================== CLIENTE LLM LOCAL =====================
import json
import logging
import os
from typing import List, Dict, Any, Iterator, Optional, Union
import httpx
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
        engineer_model_path: Optional[str] = settings.ENGINEER_MODEL_PATH,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.default_model = default_model
        self.engineer_base_url = engineer_base_url.rstrip('/') if engineer_base_url else None
        self.engineer_model = engineer_model
        self.engineer_model_path = engineer_model_path
        self.client = httpx.Client(timeout=timeout)
        self._engineer_llm = None  # para modo embarcado (llama-cpp-python)

    def _get_url(self, model: str = "default") -> str:
        if model == "engineer" and self.engineer_base_url:
            return f"{self.engineer_base_url}/v1/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _resolve_model(self, model: str) -> str:
        if model == "engineer" and not self.engineer_base_url and not self.engineer_model_path:
            logger.warning("Modo engenheiro solicitado, mas nenhuma configuração (BASE_URL ou PATH) fornecida. Fallback para default.")
            return "default"
        if model == "engineer":
            if self.engineer_base_url:
                return "engineer"
            elif self.engineer_model_path and os.path.exists(self.engineer_model_path):
                return "engineer"
            else:
                logger.warning(f"Arquivo do modelo engenheiro não encontrado em {self.engineer_model_path}. Fallback para default.")
                return "default"
        return model

    def _ensure_engineer_llm(self):
        """Carrega o modelo engenheiro via llama-cpp-python se não houver servidor e o path existir."""
        if self._engineer_llm is not None:
            return
        if self.engineer_base_url:
            return  # usa servidor, não precisa carregar local
        if not self.engineer_model_path or not os.path.exists(self.engineer_model_path):
            raise ValueError(f"Modelo engenheiro não encontrado em {self.engineer_model_path}")
        try:
            from llama_cpp import Llama
            self._engineer_llm = Llama(
                model_path=self.engineer_model_path,
                n_ctx=settings.MAX_CONTEXT_TOKENS,
                n_gpu_layers=-1,  # usar GPU se disponível (Vulkan)
                verbose=False,
            )
            logger.info(f"Modelo engenheiro carregado de {self.engineer_model_path}")
        except ImportError:
            raise ImportError("llama-cpp-python não instalado. Instale com: pip install llama-cpp-python")
        except Exception as e:
            raise RuntimeError(f"Falha ao carregar modelo engenheiro: {e}")

    def has_engineer(self) -> bool:
        """Retorna True se o modelo engenheiro está disponível (servidor ou arquivo)."""
        if self.engineer_base_url:
            return True
        if self.engineer_model_path and os.path.exists(self.engineer_model_path):
            return True
        return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        model: str = "default",
        **kwargs
    ) -> str:
        """
        Envia mensagens para o servidor llama.cpp (formato OpenAI) ou para o modelo embarcado.
        Se model="engineer" e ENGINEER_MODEL_BASE_URL não estiver configurado,
        tenta carregar via ENGINEER_MODEL_PATH.
        """
        model = self._resolve_model(model)
        if model == "engineer":
            # Tenta usar servidor primeiro
            if self.engineer_base_url:
                url = self._get_url("engineer")
                payload = {
                    "model": self.engineer_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
                try:
                    response = self.client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data['choices'][0]['message']['content']
                except Exception as e:
                    logger.error(f"Erro ao usar servidor engenheiro: {e}. Tentando fallback para default.")
                    return self.generate(messages, max_tokens, temperature, "default", **kwargs)
            # Senão, tenta embarcado
            try:
                self._ensure_engineer_llm()
                prompt = self._build_prompt(messages)
                response = self._engineer_llm.create_completion(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return response['choices'][0]['text']
            except Exception as e:
                logger.error(f"Erro ao usar modelo engenheiro embarcado: {e}. Fallback para default.")
                return self.generate(messages, max_tokens, temperature, "default", **kwargs)
        else:
            # default
            url = self._get_url("default")
            payload = {
                "model": self.default_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
            try:
                response = self.client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data['choices'][0]['message']['content']
            except Exception as e:
                raise Exception(f"Erro ao gerar resposta com modelo default: {str(e)}")

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        model: str = "default",
        **kwargs
    ) -> Iterator[str]:
        """
        Mesma requisição de generate(), mas com stream=True.
        """
        model = self._resolve_model(model)
        if model == "engineer":
            if self.engineer_base_url:
                url = self._get_url("engineer")
                payload = {
                    "model": self.engineer_model,
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
                except Exception as e:
                    logger.error(f"Erro no stream do engenheiro via servidor: {e}. Fallback para default.")
                    for token in self.generate_stream(messages, max_tokens, temperature, "default", **kwargs):
                        yield token
                return
            else:
                # embarcado
                try:
                    self._ensure_engineer_llm()
                    prompt = self._build_prompt(messages)
                    stream = self._engineer_llm.create_completion(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True,
                        **kwargs
                    )
                    for chunk in stream:
                        text = chunk['choices'][0]['text']
                        if text:
                            yield text
                except Exception as e:
                    logger.error(f"Erro no stream do engenheiro embarcado: {e}. Fallback para default.")
                    for token in self.generate_stream(messages, max_tokens, temperature, "default", **kwargs):
                        yield token
                return
        else:
            # default stream
            url = self._get_url("default")
            payload = {
                "model": self.default_model,
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
            except Exception as e:
                raise Exception(f"Erro ao gerar resposta (stream) com modelo default: {str(e)}")

    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Converte lista de mensagens no formato chat para um prompt único para modelos tipo Llama."""
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == "user":
                prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == "assistant":
                prompt += f"<|im_start|>assistant\n{content}<|im_end|>\n"
            else:
                prompt += f"{content}\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

# Singleton
_llm_client = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client