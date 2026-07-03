import subprocess
from pathlib import Path
from typing import Any, Dict
from .base import Tool, ToolResult

class LayoutValidatorTool(Tool):
    @property
    def name(self) -> str:
        return "layout_validator"

    @property
    def description(self) -> str:
        return "Valida um arquivo de layout XML Android."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "layout_path": {"type": "string", "description": "Caminho para o arquivo XML de layout"}
            },
            "required": ["layout_path"]
        }

    def run(self, **kwargs) -> ToolResult:
        layout_path = kwargs.get("layout_path")
        if not layout_path:
            return ToolResult(success=False, error="layout_path é obrigatório")
        path = Path(layout_path)
        if not path.exists():
            return ToolResult(success=False, error=f"Arquivo não encontrado: {layout_path}")

        # Tentar usar xmllint para validar sintaxe XML
        try:
            result = subprocess.run(["xmllint", "--noout", str(path)], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return ToolResult(success=True, data="Layout XML válido.")
            else:
                return ToolResult(success=False, error=result.stderr or "Erro de validação XML")
        except FileNotFoundError:
            # Fallback: apenas verifica se o arquivo contém XML básico
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if "<?xml" in content or "<LinearLayout" in content or "<androidx." in content:
                    return ToolResult(success=True, data="Arquivo parece ser um layout XML (validação básica).")
                else:
                    return ToolResult(success=False, error="Arquivo não parece ser um layout XML válido.")
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Timeout na validação")
        except Exception as e:
            return ToolResult(success=False, error=str(e))