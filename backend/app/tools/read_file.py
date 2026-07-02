import os
from pathlib import Path
from typing import Any, Dict
from .base import Tool, ToolResult
from ..db import db_cursor, PROJECTS_FILES_DIR

class ReadFileTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Lê o conteúdo de um arquivo dentro do diretório do projeto."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "ID do projeto"},
                "file_path": {"type": "string", "description": "Caminho relativo ao diretório do projeto"}
            },
            "required": ["project_id", "file_path"]
        }

    def run(self, **kwargs) -> ToolResult:
        project_id = kwargs.get("project_id")
        file_path = kwargs.get("file_path")
        if not project_id or not file_path:
            return ToolResult(success=False, error="project_id e file_path são obrigatórios")

        # Sanitizar caminho para evitar path traversal
        base_dir = PROJECTS_FILES_DIR / project_id / "files"
        # A pasta "files" é onde armazenamos os arquivos do projeto no backend (ver projects.py)
        # Mas o usuário pode querer ler outros arquivos? Vamos restringir à pasta do projeto.
        # Para simplificar, permitimos ler qualquer arquivo dentro da pasta do projeto.
        try:
            # Resolve caminho absoluto e verifica se está dentro do diretório base
            target = (base_dir / file_path).resolve()
            if not str(target).startswith(str(base_dir.resolve())):
                return ToolResult(success=False, error="Caminho fora do diretório do projeto")
            if not target.exists():
                return ToolResult(success=False, error="Arquivo não encontrado")
            if target.is_dir():
                return ToolResult(success=False, error="É um diretório, não um arquivo")
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(success=True, data=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))