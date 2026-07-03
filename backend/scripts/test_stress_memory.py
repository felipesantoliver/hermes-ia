"""
Teste de estresse do ResourceMonitor.

Aloca memória artificialmente no próprio processo (o mesmo padrão que o
ResourceMonitor mede via psutil.Process()) e verifica se o sistema
detecta a pressão de RAM (edge-triggered) e se recupera corretamente
quando a memória é liberada.

Não depende do backend estar rodando (não bate na API HTTP): instancia o
ResourceMonitor diretamente, com um ram_limit_gb baixo pra não precisar
alocar memória real de mais no ambiente de teste.

Uso:
    python backend/scripts/test_stress_memory.py
"""
import gc
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.monitor import ResourceMonitor  # noqa: E402

# Limite baixo de propósito: força pressão com uma alocação modesta,
# sem arriscar OOM na máquina que roda o teste.
TEST_RAM_LIMIT_GB = 0.35
CHUNK_MB = 20
MAX_CHUNKS = 40  # trava de segurança: ~800MB no pior caso
POLL_INTERVAL_S = 0.1


def main() -> int:
    monitor = ResourceMonitor(check_interval_s=999, pressure_threshold=0.8)
    # Sem depender de um banco/perfil real: fixa o limite de RAM do teste.
    monitor._get_ram_limit_gb = lambda: TEST_RAM_LIMIT_GB

    events = []
    monitor.register_callback(lambda status: events.append(dict(status)))

    baseline = monitor.get_status(force_refresh=True)
    print(f"[stress] baseline: {baseline}")
    if baseline["under_pressure"]:
        print("[stress] AVISO: processo já começa sob pressão com o limite de teste; "
              "reduza TEST_RAM_LIMIT_GB ou libere memória antes de rodar.")

    allocations = []
    pressure_detected = False

    print(f"[stress] alocando em blocos de {CHUNK_MB}MB até detectar pressão "
          f"(limite de teste: {TEST_RAM_LIMIT_GB}GB, limiar: 80%)...")
    for i in range(1, MAX_CHUNKS + 1):
        allocations.append(bytearray(CHUNK_MB * 1024 * 1024))
        status = monitor.get_status(force_refresh=True)
        print(f"[stress] bloco {i:02d} | ram_used={status['ram_used_gb']}GB "
              f"({status['ram_percent']}%) | under_pressure={status['under_pressure']}")
        if status["under_pressure"]:
            pressure_detected = True
            break
        time.sleep(POLL_INTERVAL_S)

    if not pressure_detected:
        print("[stress] FALHOU: pressão nunca foi detectada dentro do limite de blocos.")
        return 1

    print("[stress] pressão detectada. Verificando se o callback foi disparado...")
    if not any(e["under_pressure"] for e in events):
        print("[stress] FALHOU: callback de pressão não foi disparado.")
        return 1
    print(f"[stress] OK: callback disparado com under_pressure=True ({events[-1]})")

    print("[stress] liberando memória e verificando recuperação...")
    allocations.clear()
    gc.collect()
    time.sleep(0.2)

    recovered = False
    for i in range(1, 21):
        status = monitor.get_status(force_refresh=True)
        print(f"[stress] pós-liberação, checagem {i:02d} | ram_used={status['ram_used_gb']}GB "
              f"({status['ram_percent']}%) | under_pressure={status['under_pressure']}")
        if not status["under_pressure"]:
            recovered = True
            break
        time.sleep(POLL_INTERVAL_S)

    if not recovered:
        print("[stress] FALHOU: sistema não saiu do estado de pressão após liberar memória.")
        return 1

    recovery_events = [e for e in events if not e["under_pressure"]]
    if not recovery_events:
        print("[stress] FALHOU: callback de recuperação (under_pressure=False) não disparou.")
        return 1

    print(f"[stress] OK: recuperação detectada e callback disparado ({recovery_events[-1]})")
    print("\n[stress] RESULTADO: sistema reagiu corretamente à pressão de RAM e à recuperação.")
    return 0


if __name__ == "__main__":
    sys.exit(main())