from typing import Any, Dict
from .base import Tool, ToolResult
from .indexer import index_project


class CodebaseIndexTool(Tool):
    """Dispara a indexação de um projeto (preparação para RAG V2). A busca
    sobre o índice gerado é implementada na V2.2; esta tool apenas
    dispara a indexação e retorna o status."""

    @property
    def name(self) -> str:
        return "codebase_index"

    @property
    def description(self) -> str:
        return (
            "Indexa os arquivos-fonte de um projeto (funções/classes) em um "
            "índice FAISS local, para uso futuro em busca semântica de código (V2.2). "
            "Chamada manual, disparada pelo usuário."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "ID do projeto a indexar"}
            },
            "required": ["project_id"]
        }

    def run(self, **kwargs) -> ToolResult:
        project_id = kwargs.get("project_id")
        if not project_id:
            return ToolResult(success=False, error="project_id é obrigatório")

        try:
            status = index_project(project_id)
        except Exception as e:
            return ToolResult(success=False, error=f"Falha inesperada ao indexar: {e}")

        if status["status"] == "error":
            return ToolResult(success=False, error=status["message"], data=status)
        return ToolResult(success=True, data=status)