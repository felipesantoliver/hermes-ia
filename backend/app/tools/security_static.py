import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict
from .base import Tool, ToolResult

STATIC_ANALYSIS_TIMEOUT_S = 15


class BanditTool(Tool):
    """Roda o Bandit (análise estática de segurança para Python) localmente
    sobre um trecho de código e retorna as issues encontradas."""

    @property
    def name(self) -> str:
        return "bandit_scan"

    @property
    def description(self) -> str:
        return "Analisa código Python com Bandit e retorna issues de segurança encontradas (se o Bandit estiver instalado)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código Python a ser analisado"}
            },
            "required": ["code"]
        }

    def run(self, **kwargs) -> ToolResult:
        code = kwargs.get("code")
        if not code:
            return ToolResult(success=False, error="Código não fornecido")

        if shutil.which("bandit") is None:
            return ToolResult(success=False, error="Bandit não está instalado neste ambiente")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                tmp_path = f.name

            result = subprocess.run(
                ["bandit", "-f", "json", "-q", tmp_path],
                capture_output=True,
                text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT_S,
            )
            # Bandit retorna exit code != 0 quando encontra issues, então não
            # tratamos isso como falha da tool em si.
            if not result.stdout.strip():
                return ToolResult(success=False, error=result.stderr or "Bandit não retornou saída")

            try:
                report = json.loads(result.stdout)
            except json.JSONDecodeError:
                return ToolResult(success=False, error=f"Falha ao interpretar saída do Bandit: {result.stdout[:500]}")

            issues = [
                {
                    "severity": item.get("issue_severity"),
                    "confidence": item.get("issue_confidence"),
                    "test_id": item.get("test_id"),
                    "text": item.get("issue_text"),
                    "line": item.get("line_number"),
                }
                for item in report.get("results", [])
            ]
            return ToolResult(success=True, data={"issues": issues, "issue_count": len(issues)})
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Timeout após {STATIC_ANALYSIS_TIMEOUT_S}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)


class ShellCheckTool(Tool):
    """Roda o ShellCheck sobre um script shell e retorna as issues
    encontradas."""

    @property
    def name(self) -> str:
        return "shellcheck_scan"

    @property
    def description(self) -> str:
        return "Analisa scripts shell com ShellCheck e retorna issues encontradas (se o ShellCheck estiver instalado)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Conteúdo do script shell a ser analisado"}
            },
            "required": ["script"]
        }

    def run(self, **kwargs) -> ToolResult:
        script = kwargs.get("script")
        if not script:
            return ToolResult(success=False, error="Script não fornecido")

        if shutil.which("shellcheck") is None:
            return ToolResult(success=False, error="ShellCheck não está instalado neste ambiente")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(script)
                tmp_path = f.name

            result = subprocess.run(
                ["shellcheck", "-f", "json", tmp_path],
                capture_output=True,
                text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT_S,
            )
            if not result.stdout.strip():
                return ToolResult(success=True, data={"issues": [], "issue_count": 0})

            try:
                report = json.loads(result.stdout)
            except json.JSONDecodeError:
                return ToolResult(success=False, error=f"Falha ao interpretar saída do ShellCheck: {result.stdout[:500]}")

            issues = [
                {
                    "severity": item.get("level"),
                    "code": item.get("code"),
                    "message": item.get("message"),
                    "line": item.get("line"),
                }
                for item in report
            ]
            return ToolResult(success=True, data={"issues": issues, "issue_count": len(issues)})
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Timeout após {STATIC_ANALYSIS_TIMEOUT_S}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)