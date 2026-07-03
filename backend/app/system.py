# ===================== STATUS DO SISTEMA (RAM/CPU) =====================
# Responsabilidade: expor o snapshot do ResourceMonitor para o frontend
# (indicador de uso na tela de Armazenamento, polling a cada 5s).

from fastapi import APIRouter
from .monitor import get_monitor

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def get_system_status():
    """Retorna CPU%, RAM usada/limite e número de processos ativos do
    backend. force_refresh=True garante uma leitura fresca mesmo que o
    tick de background ainda não tenha rodado."""
    monitor = get_monitor()
    return monitor.get_status(force_refresh=True)