# ===================== MONITOR DE RECURSOS (RAM/CPU) =====================
# Responsabilidade: medir o uso de RAM/CPU do processo atual do backend em
# background (thread daemon, tick a cada 5s por padrão) e notificar
# callbacks quando o uso de RAM cruza o limiar de pressão configurado
# (80% do ram_limit_gb do perfil). Não depende do event loop do FastAPI,
# então funciona igual em request síncrona, streaming ou fora de request
# nenhuma.

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import psutil

from .db import db_cursor

logger = logging.getLogger(__name__)

CHECK_INTERVAL_S = 5
PRESSURE_THRESHOLD = 0.8  # 80% do ram_limit_gb configurado no perfil
DEFAULT_RAM_LIMIT_GB = 8.0

# Tools que de fato consomem CPU/RAM de forma significativa (executam
# subprocessos, geram embeddings, etc.). São essas que o orquestrador pausa
# quando o monitor sinaliza pressão — tools leves (read_file, web_search)
# continuam liberadas.
HEAVY_TOOL_NAMES = {
    "run_python",
    "run_shell",
    "bandit_scan",
    "shellcheck_scan",
    "codebase_index",
    "firmware_check",
}

PressureCallback = Callable[[Dict[str, Any]], None]


class ResourceMonitor:
    """Monitora RAM/CPU do processo atual em background e expõe:
      - get_status(): snapshot mais recente das métricas.
      - is_under_pressure(): leitura rápida do estado atual (usada pelo
        orquestrador para decidir se pausa tools pesadas).
      - register_callback()/unregister_callback(): notificados quando o
        estado de pressão MUDA (edge-triggered: dispara ao entrar e ao sair
        de pressão, não a cada tick, para não inundar o frontend).
    """

    def __init__(
        self,
        check_interval_s: float = CHECK_INTERVAL_S,
        pressure_threshold: float = PRESSURE_THRESHOLD,
    ) -> None:
        self._process = psutil.Process()
        self._check_interval_s = check_interval_s
        self._pressure_threshold = pressure_threshold

        self._callbacks: List[PressureCallback] = []
        self._callbacks_lock = threading.Lock()

        self._state_lock = threading.Lock()
        self._last_status: Optional[Dict[str, Any]] = None
        self._under_pressure = False

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Primeira chamada a cpu_percent() sempre retorna 0.0 (precisa de
        # um intervalo de referência); disparamos aqui para que a primeira
        # leitura relevante já venha com um valor útil.
        try:
            self._process.cpu_percent(interval=None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="hermes-resource-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def register_callback(self, callback: PressureCallback) -> None:
        with self._callbacks_lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: PressureCallback) -> None:
        with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _emit(self, status: Dict[str, Any]) -> None:
        with self._callbacks_lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(status)
            except Exception as e:
                logger.warning(f"Callback de pressão de recursos falhou: {e}")

    # ------------------------------------------------------------------
    # Leitura de configuração
    # ------------------------------------------------------------------
    def _get_ram_limit_gb(self) -> float:
        try:
            with db_cursor() as cur:
                cur.execute("SELECT ram_limit_gb FROM user_profile WHERE id = 1")
                row = cur.fetchone()
                if row and row["ram_limit_gb"]:
                    return float(row["ram_limit_gb"])
        except Exception as e:
            logger.warning(f"Falha ao ler ram_limit_gb do perfil, usando default: {e}")
        return DEFAULT_RAM_LIMIT_GB

    # ------------------------------------------------------------------
    # Medição
    # ------------------------------------------------------------------
    def _measure(self) -> Dict[str, Any]:
        ram_limit_gb = self._get_ram_limit_gb()
        try:
            mem_info = self._process.memory_info()
            ram_used_gb = mem_info.rss / (1024 ** 3)
        except Exception as e:
            logger.warning(f"Falha ao medir RAM do processo: {e}")
            ram_used_gb = 0.0
        try:
            cpu_percent = self._process.cpu_percent(interval=None)
        except Exception as e:
            logger.warning(f"Falha ao medir CPU do processo: {e}")
            cpu_percent = 0.0
        try:
            process_count = 1 + len(self._process.children(recursive=True))
        except Exception:
            process_count = 1

        ram_percent = (ram_used_gb / ram_limit_gb) if ram_limit_gb > 0 else 0.0
        under_pressure = ram_percent >= self._pressure_threshold

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": round(cpu_percent, 1),
            "ram_used_gb": round(ram_used_gb, 3),
            "ram_limit_gb": ram_limit_gb,
            "ram_percent": round(ram_percent * 100, 1),
            "process_count": process_count,
            "under_pressure": under_pressure,
        }

    def _check_once(self) -> Dict[str, Any]:
        status = self._measure()
        with self._state_lock:
            was_under_pressure = self._under_pressure
            self._under_pressure = status["under_pressure"]
            self._last_status = status

        # Edge-triggered: só notifica quando o estado MUDA, para não
        # inundar o frontend/orquestrador com o mesmo aviso a cada tick.
        if status["under_pressure"] != was_under_pressure:
            self._emit(status)

        return status

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_once()
            except Exception as e:
                logger.warning(f"Erro no ciclo do ResourceMonitor: {e}")
            self._stop_event.wait(self._check_interval_s)

    # ------------------------------------------------------------------
    # Leitura pública
    # ------------------------------------------------------------------
    def get_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        if force_refresh:
            return self._check_once()
        with self._state_lock:
            if self._last_status is not None:
                return dict(self._last_status)
        return self._check_once()

    def is_under_pressure(self) -> bool:
        with self._state_lock:
            return self._under_pressure


_monitor_singleton: Optional[ResourceMonitor] = None
_monitor_singleton_lock = threading.Lock()


def get_monitor() -> ResourceMonitor:
    global _monitor_singleton
    if _monitor_singleton is None:
        with _monitor_singleton_lock:
            if _monitor_singleton is None:
                _monitor_singleton = ResourceMonitor()
                _monitor_singleton.start()
    return _monitor_singleton