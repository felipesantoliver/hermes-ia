import shlex
import subprocess
from typing import Any, Dict
from .base import Tool, ToolResult
from .audit import log_execution

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

DEFAULT_TIMEOUT_S = 5
MAX_TIMEOUT_S = 15
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024

# Allowlist de comandos considerados seguros e somente-leitura.
ALLOWED_COMMANDS = {"ls", "cat", "echo", "grep", "wc", "find", "head", "tail", "pwd", "file"}

# Qualquer um desses caracteres na string bruta do comando é motivo de
# bloqueio IMEDIATO, antes mesmo do parsing com shlex. Isso impede
# encadeamento de comandos, substituição de comando, redirecionamento de
# I/O e expansão de variáveis — mesmo dentro de um comando "permitido".
FORBIDDEN_METACHARS = set("|;&$`><(){}!\n")


def _contains_forbidden_metachars(command: str) -> bool:
    return any(ch in FORBIDDEN_METACHARS for ch in command)


def _limit_resources():
    if resource is None:
        return
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except (ValueError, OSError):
        pass
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
        cap = min(16, hard) if hard != resource.RLIM_INFINITY else 16
        resource.setrlimit(resource.RLIMIT_NPROC, (cap, hard))
    except (ValueError, OSError):
        pass


class RunShellTool(Tool):
    @property
    def name(self) -> str:
        return "run_shell"

    @property
    def description(self) -> str:
        return (
            "Executa um comando shell simples e somente-leitura, restrito a uma "
            f"allowlist ({', '.join(sorted(ALLOWED_COMMANDS))}). Sem pipes, "
            "redirecionamento, encadeamento ou substituição de comando."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando a executar (ex: ls -la)"},
                "timeout": {"type": "integer", "description": f"Timeout em segundos (default {DEFAULT_TIMEOUT_S}, máximo {MAX_TIMEOUT_S})"}
            },
            "required": ["command"]
        }

    def run(self, **kwargs) -> ToolResult:
        command = kwargs.get("command")
        timeout = kwargs.get("timeout", DEFAULT_TIMEOUT_S)

        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT_S
        timeout = max(1, min(timeout, MAX_TIMEOUT_S))

        if not command or not command.strip():
            err = "Comando vazio"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        # 1) Bloqueio de metacaracteres ANTES de qualquer parsing. Isso é o
        # que impede "ls; rm -rf /", "cat foo | sh", "echo $(whoami)" etc.,
        # independente do primeiro token ser um comando permitido.
        if _contains_forbidden_metachars(command):
            err = "Comando contém caracteres não permitidos (pipes, redirecionamento, encadeamento ou substituição)"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        try:
            parts = shlex.split(command)
        except ValueError as e:
            err = f"Comando malformado: {e}"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        if not parts:
            err = "Comando vazio"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        cmd = parts[0]
        if cmd not in ALLOWED_COMMANDS:
            err = f"Comando '{cmd}' não permitido"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        # 2) Nenhum argumento pode, por si só, tentar escapar para outro
        # binário (ex: "find . -exec sh -c ... \;"). Bloqueamos flags de
        # execução conhecidas dos comandos permitidos.
        DANGEROUS_FLAGS = {"-exec", "-execdir", "--exec"}
        if any(arg in DANGEROUS_FLAGS for arg in parts[1:]):
            err = "Flag não permitida: possibilita execução de outros programas"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)

        try:
            run_kwargs = dict(
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": "/usr/bin:/bin"},
            )
            if resource is not None:
                run_kwargs["preexec_fn"] = _limit_resources

            # shell=False + lista de argumentos: nunca passa pelo shell do
            # sistema, então não há injeção possível via metacaracteres
            # mesmo que algum tivesse escapado do filtro acima.
            result = subprocess.run(parts, shell=False, **run_kwargs)

            payload = {"command": command, "timeout": timeout}
            if result.returncode == 0:
                log_execution("run_shell", payload, True, output=result.stdout)
                return ToolResult(success=True, data=result.stdout)
            else:
                err = result.stderr or "Erro na execução"
                log_execution("run_shell", payload, False, error=err)
                return ToolResult(success=False, error=err)
        except subprocess.TimeoutExpired:
            err = f"Timeout após {timeout}s"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)
        except FileNotFoundError:
            err = f"Comando '{cmd}' não encontrado no sistema"
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=err)
            return ToolResult(success=False, error=err)
        except Exception as e:
            log_execution("run_shell", {"command": command, "timeout": timeout}, False, error=str(e))
            return ToolResult(success=False, error=str(e))