import subprocess
import shlex
from typing import Any, Dict, List
from .base import Tool, ToolResult

# Lista de comandos permitidos (allowlist)
ALLOWED_COMMANDS = {"ls", "cat", "echo", "grep", "wc", "find", "head", "tail"}

class RunShellTool(Tool):
    @property
    def name(self) -> str:
        return "run_shell"

    @property
    def description(self) -> str:
        return "Executa um comando shell simples (apenas comandos permitidos)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando a executar (ex: ls -la)"},
                "timeout": {"type": "integer", "description": "Timeout em segundos (default 15)"}
            },
            "required": ["command"]
        }

    def run(self, **kwargs) -> ToolResult:
        command = kwargs.get("command")
        timeout = kwargs.get("timeout", 15)
        if not command:
            return ToolResult(success=False, error="Comando não fornecido")

        # Verificar se o comando principal está na allowlist
        parts = shlex.split(command)
        if not parts:
            return ToolResult(success=False, error="Comando vazio")
        cmd = parts[0]
        if cmd not in ALLOWED_COMMANDS:
            return ToolResult(success=False, error=f"Comando '{cmd}' não permitido")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return ToolResult(success=True, data=result.stdout)
            else:
                return ToolResult(success=False, error=result.stderr or "Erro na execução")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Timeout após {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))