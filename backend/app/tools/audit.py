# ===================== LOG DE AUDITORIA DE EXECUÇÃO =====================
# Responsabilidade: registrar toda execução feita por tools que rodam
# código/comandos (RunPythonTool, RunShellTool) em um arquivo append-only,
# separado dos logs de conversa. Nunca lança exceção para o chamador: falha
# de auditoria não pode derrubar a execução da tool.

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..db import DATA_DIR

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = DATA_DIR / "logs" / "tool_audit.jsonl"
_write_lock = threading.Lock()


def log_execution(
    tool_name: str,
    payload: Dict[str, Any],
    success: bool,
    output: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Registra uma execução no log de auditoria.

    `payload` deve conter apenas o necessário para reconstruir o que foi
    pedido (ex: código/comando, timeout, limites aplicados) — evitamos
    truncar aqui pra manter o log completo, mas o chamador pode truncar
    campos muito grandes antes de passar.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "success": success,
        "payload": payload,
        "output_excerpt": (output or "")[:2000] if output else None,
        "error": error,
    }
    if extra:
        entry.update(extra)

    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Auditoria nunca pode quebrar a execução real da tool.
        logger.warning(f"Falha ao gravar log de auditoria para '{tool_name}': {e}")