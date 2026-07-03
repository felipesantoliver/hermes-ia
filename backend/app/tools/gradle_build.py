import subprocess
from pathlib import Path
from typing import Any, Dict
from .base import Tool, ToolResult

class GradleBuildTool(Tool):
    @property
    def name(self) -> str:
        return "gradle_build"

    @property
    def description(self) -> str:
        return "Executa uma tarefa Gradle no projeto Android."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Caminho para o diretório raiz do projeto Android"},
                "task": {"type": "string", "description": "Tarefa Gradle a executar (ex: build, assembleDebug)", "default": "build"}
            },
            "required": ["project_dir"]
        }

    def run(self, **kwargs) -> ToolResult:
        project_dir = kwargs.get("project_dir")
        task = kwargs.get("task", "build")
        if not project_dir:
            return ToolResult(success=False, error="project_dir é obrigatório")
        path = Path(project_dir)
        if not path.exists():
            return ToolResult(success=False, error=f"Diretório não encontrado: {project_dir}")

        gradlew = path / "gradlew"
        if gradlew.exists():
            cmd = [str(gradlew), task]
        else:
            # Fallback para gradle global
            cmd = ["gradle", task]

        try:
            result = subprocess.run(cmd, cwd=str(path), capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return ToolResult(success=True, data=result.stdout)
            else:
                return ToolResult(success=False, error=result.stderr or "Falha na execução do Gradle")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Timeout na execução do Gradle")
        except Exception as e:
            return ToolResult(success=False, error=str(e))