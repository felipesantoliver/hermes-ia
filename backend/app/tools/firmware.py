import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from .base import Tool, ToolResult
from ..db import PROJECTS_FILES_DIR

PLATFORMIO_COMPILE_TIMEOUT_S = 120

# Sinais de que um arquivo é firmware/bare-metal para microcontrolador,
# distinto de C/C++ genérico de aplicação.
EMBEDDED_SIGNALS = [
    "avr/io.h", "HAL_", "stm32", "Arduino.h", "freertos", "FreeRTOS.h",
    "__attribute__((interrupt", "ISR(", "esp_", "nrf_", "platformio",
]


def _looks_embedded(text: str) -> bool:
    lowered = text.lower()
    return any(signal.lower() in lowered for signal in EMBEDDED_SIGNALS)


class FirmwareTool(Tool):
    """Tool placeholder para o domínio de firmware (preparação para V2.4).
    Hoje: detecta se o código do projeto parece ser C/C++ para
    microcontrolador e valida a estrutura de um projeto PlatformIO,
    oferecendo compilar via `pio run` se o PlatformIO estiver instalado.
    Não faz nada além de validar estrutura + compilar quando disponível."""

    @property
    def name(self) -> str:
        return "firmware_check"

    @property
    def description(self) -> str:
        return (
            "Detecta se um projeto é firmware C/C++ para microcontrolador e valida "
            "a estrutura de um projeto PlatformIO, compilando com PlatformIO se "
            "estiver instalado (placeholder, preparação para V2.4)."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "ID do projeto a analisar"}
            },
            "required": ["project_id"]
        }

    def run(self, **kwargs) -> ToolResult:
        project_id = kwargs.get("project_id")
        if not project_id:
            return ToolResult(success=False, error="project_id é obrigatório")

        project_dir = PROJECTS_FILES_DIR / project_id / "files"
        if not project_dir.exists():
            return ToolResult(success=False, error=f"Diretório do projeto não encontrado: {project_dir}")

        c_cpp_files: List[Path] = [
            p for p in project_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".c", ".h", ".cpp", ".hpp", ".ino"}
        ]

        if not c_cpp_files:
            return ToolResult(success=True, data={
                "is_embedded_project": False,
                "reason": "Nenhum arquivo .c/.h/.cpp/.hpp/.ino encontrado no projeto.",
            })

        embedded_hits = 0
        for f in c_cpp_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if _looks_embedded(content):
                embedded_hits += 1

        is_embedded = embedded_hits > 0
        if not is_embedded:
            return ToolResult(success=True, data={
                "is_embedded_project": False,
                "reason": "Arquivos C/C++ encontrados, mas sem sinais de firmware embarcado (registradores, HALs, ISR etc.).",
                "c_cpp_file_count": len(c_cpp_files),
            })

        platformio_ini = project_dir / "platformio.ini"
        structure_valid = platformio_ini.exists()
        pio_available = shutil.which("pio") is not None or shutil.which("platformio") is not None

        result_data: Dict[str, Any] = {
            "is_embedded_project": True,
            "embedded_signal_files": embedded_hits,
            "c_cpp_file_count": len(c_cpp_files),
            "platformio_ini_found": structure_valid,
            "platformio_installed": pio_available,
        }

        if not structure_valid:
            result_data["message"] = (
                "Projeto parece ser firmware embarcado, mas não há platformio.ini na raiz. "
                "Estrutura de projeto PlatformIO não confirmada; compilação não tentada."
            )
            return ToolResult(success=True, data=result_data)

        if not pio_available:
            result_data["message"] = (
                "platformio.ini encontrado, mas o binário 'pio'/'platformio' não está "
                "instalado neste ambiente. Compilação não tentada."
            )
            return ToolResult(success=True, data=result_data)

        pio_bin = shutil.which("pio") or shutil.which("platformio")
        try:
            compile_result = subprocess.run(
                [pio_bin, "run"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=PLATFORMIO_COMPILE_TIMEOUT_S,
            )
            result_data["compiled"] = compile_result.returncode == 0
            result_data["compile_output"] = (compile_result.stdout or compile_result.stderr)[-4000:]
            result_data["message"] = (
                "Compilação com PlatformIO concluída com sucesso."
                if compile_result.returncode == 0
                else "Compilação com PlatformIO falhou; veja compile_output."
            )
            return ToolResult(success=compile_result.returncode == 0, data=result_data, error=None if compile_result.returncode == 0 else "Falha na compilação PlatformIO")
        except subprocess.TimeoutExpired:
            result_data["compiled"] = False
            result_data["message"] = f"Timeout na compilação após {PLATFORMIO_COMPILE_TIMEOUT_S}s"
            return ToolResult(success=False, error=result_data["message"], data=result_data)
        except Exception as e:
            result_data["compiled"] = False
            result_data["message"] = f"Erro ao invocar PlatformIO: {e}"
            return ToolResult(success=False, error=result_data["message"], data=result_data)