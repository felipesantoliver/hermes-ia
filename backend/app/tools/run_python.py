import os
import subprocess
import sys
import tempfile
from typing import Any, Dict
from .base import Tool, ToolResult
from .audit import log_execution

try:
    import resource  # POSIX apenas; indisponível no Windows
except ImportError:  # pragma: no cover - ambiente alvo é Linux
    resource = None

DEFAULT_TIMEOUT_S = 10
MAX_TIMEOUT_S = 30
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024  # 128 MB por processo

# Preamble injetado ANTES do código do usuário no mesmo arquivo temporário.
# Desabilita sockets explicitamente (rede) fazendo qualquer tentativa de
# criar um socket levantar OSError. Isso é além do limite de memória e do
# isolamento de processo; é a camada "cinto e suspensório" citada no pedido,
# já que não temos garantia de CAP_NET_ADMIN/namespaces neste ambiente.
_NETWORK_BLOCK_PREAMBLE = '''
import socket as _hermes_socket

def _hermes_blocked_socket(*args, **kwargs):
    raise OSError("Acesso de rede bloqueado no sandbox do Hermes AI.")

_hermes_socket.socket = _hermes_blocked_socket
_hermes_socket.create_connection = _hermes_blocked_socket
_hermes_socket.getaddrinfo = _hermes_blocked_socket
'''


def _limit_resources():
    """Executado no processo filho (preexec_fn) antes do exec do python3.
    Aplica limite de memória e reduz RLIMIT_NPROC como proteção extra
    contra fork bombs.
    """
    if resource is None:
        return
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except (ValueError, OSError):
        pass
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
        cap = min(32, hard) if hard != resource.RLIM_INFINITY else 32
        resource.setrlimit(resource.RLIMIT_NPROC, (cap, hard))
    except (ValueError, OSError):
        pass
    try:
        # Evita que o processo crie arquivos gigantes de propósito.
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    except (ValueError, OSError):
        pass


class RunPythonTool(Tool):
    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return (
            "Executa código Python em um ambiente isolado (sem rede, com limite "
            "de memória de 128MB e timeout) e retorna a saída."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código Python a ser executado"},
                "timeout": {"type": "integer", "description": f"Timeout em segundos (default {DEFAULT_TIMEOUT_S}, máximo {MAX_TIMEOUT_S})"}
            },
            "required": ["code"]
        }

    def run(self, **kwargs) -> ToolResult:
        code = kwargs.get("code")
        timeout = kwargs.get("timeout", DEFAULT_TIMEOUT_S)
        if not code:
            result = ToolResult(success=False, error="Código não fornecido")
            log_execution("run_python", {"code": code, "timeout": timeout}, False, error=result.error)
            return result

        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT_S
        timeout = max(1, min(timeout, MAX_TIMEOUT_S))

        full_source = _NETWORK_BLOCK_PREAMBLE + "\n# ----- código do usuário -----\n" + code

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(full_source)
                tmp_path = f.name

            env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
            }

            run_kwargs = dict(
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=tempfile.gettempdir(),
            )
            if resource is not None:
                run_kwargs["preexec_fn"] = _limit_resources

            result = subprocess.run([sys.executable or "python3", tmp_path], **run_kwargs)

            payload = {"code": code, "timeout": timeout, "memory_limit_bytes": MEMORY_LIMIT_BYTES}
            if result.returncode == 0:
                tool_result = ToolResult(success=True, data=result.stdout)
                log_execution("run_python", payload, True, output=result.stdout)
                return tool_result
            else:
                err = result.stderr or "Erro na execução"
                tool_result = ToolResult(success=False, error=err)
                log_execution("run_python", payload, False, error=err)
                return tool_result
        except subprocess.TimeoutExpired:
            err = f"Timeout após {timeout}s"
            log_execution("run_python", {"code": code, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)
        except Exception as e:
            log_execution("run_python", {"code": code, "timeout": timeout}, False, error=str(e))
            return ToolResult(success=False, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)