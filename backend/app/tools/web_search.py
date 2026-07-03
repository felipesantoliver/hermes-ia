from typing import Any, Dict
import httpx
from .base import Tool, ToolResult
from ..config import settings

SEARCH_TIMEOUT_S = 5


class WebSearchTool(Tool):
    """Busca na web via uma instância local do SearXNG (meta-buscador
    self-hosted), usando a API JSON dele. Requer que o SearXNG esteja
    configurado com `json` habilitado em `search.formats`."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Busca na web usando uma instância local do SearXNG e retorna resultados estruturados (título, snippet, url)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termos de busca"},
                "max_results": {"type": "integer", "description": "Número máximo de resultados a retornar (default 5)"}
            },
            "required": ["query"]
        }

    def run(self, **kwargs) -> ToolResult:
        query = kwargs.get("query")
        max_results = kwargs.get("max_results", 5)
        if not query or not query.strip():
            return ToolResult(success=False, error="Query de busca não fornecida")

        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 5
        max_results = max(1, min(max_results, 20))

        base_url = getattr(settings, "SEARXNG_BASE_URL", "http://localhost:8081")

        try:
            response = httpx.get(
                f"{base_url}/search",
                params={"q": query, "format": "json"},
                timeout=SEARCH_TIMEOUT_S,
            )
        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"Timeout ao contatar o SearXNG em {base_url} (limite de {SEARCH_TIMEOUT_S}s)")
        except httpx.ConnectError:
            return ToolResult(success=False, error=f"Não foi possível conectar ao SearXNG em {base_url}. Verifique se a instância local está rodando.")
        except httpx.HTTPError as e:
            return ToolResult(success=False, error=f"Erro de rede ao consultar o SearXNG: {e}")

        if response.status_code != 200:
            return ToolResult(success=False, error=f"SearXNG retornou status {response.status_code}")

        try:
            data = response.json()
        except ValueError:
            return ToolResult(success=False, error="Resposta do SearXNG não é JSON válido (verifique se 'json' está habilitado em search.formats)")

        raw_results = data.get("results", [])[:max_results]
        results = [
            {
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
                "url": item.get("url", ""),
            }
            for item in raw_results
        ]

        return ToolResult(success=True, data={"results": results, "result_count": len(results)})

    # Preparação para futura busca em documentação local (V2.4)
    @staticmethod
    def search_local(query: str) -> Dict[str, Any]:
        """Placeholder para busca em índices locais (PDFs, datasheets)."""
        return {"results": [], "message": "Busca local ainda não implementada"}