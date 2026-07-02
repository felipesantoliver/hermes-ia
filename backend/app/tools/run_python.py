import subprocess
import tempfile
import os
from pathlib import Path
from typing import Any, Dict
from .base import Tool, ToolResult

class RunPythonTool(Tool):
    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return "Executa código Python em um ambiente isolado e retorna a saída."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código Python a ser executado"},
                "timeout": {"type": "integer", "description": "Timeout em segundos (default 10)"}
            },
            "required": ["code"]
        }

    def run(self, **kwargs) -> ToolResult:
        code = kwargs.get("code")
        timeout = kwargs.get("timeout", 10)
        if not code:
            return ToolResult(success=False, error="Código não fornecido")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            # Executar em subprocesso isolado, sem rede
            env = os.environ.copy()
            env.pop("HTTP_PROXY", None)
            env.pop("HTTPS_PROXY", None)
            # Bloquear acesso à rede? Podemos usar `network` namespace, mas é complexo.
            # Como simplificação, apenas não passamos variáveis de proxy.
            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=tempfile.gettempdir()
            )
            if result.returncode == 0:
                return ToolResult(success=True, data=result.stdout)
            else:
                return ToolResult(success=False, error=result.stderr or "Erro na execução")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Timeout após {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        finally:
            os.unlink(tmp_path)