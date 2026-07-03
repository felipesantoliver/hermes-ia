import time
from types import SimpleNamespace
from app.monitor import ResourceMonitor, HEAVY_TOOL_NAMES


def _make_monitor(monkeypatch, ram_limit_gb=8.0):
    """Cria um ResourceMonitor cujo _get_ram_limit_gb não depende do banco
    (evita precisar de uma tabela user_profile real nos testes)."""
    monitor = ResourceMonitor(check_interval_s=999, pressure_threshold=0.8)
    monkeypatch.setattr(monitor, "_get_ram_limit_gb", lambda: ram_limit_gb)
    return monitor


def _fake_process(rss_bytes, cpu=12.5, children=2):
    proc = SimpleNamespace()
    proc.memory_info = lambda: SimpleNamespace(rss=rss_bytes)
    proc.cpu_percent = lambda interval=None: cpu
    proc.children = lambda recursive=True: [object()] * children
    return proc


def test_status_below_threshold_not_under_pressure(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    # 2GB usados de 8GB = 25%, bem abaixo dos 80%
    monitor._process = _fake_process(rss_bytes=2 * 1024 ** 3)

    status = monitor.get_status(force_refresh=True)

    assert status["under_pressure"] is False
    assert status["ram_limit_gb"] == 8.0
    assert 24.0 <= status["ram_percent"] <= 26.0
    assert monitor.is_under_pressure() is False


def test_status_above_threshold_is_under_pressure(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    # 7GB usados de 8GB = 87.5%, acima dos 80%
    monitor._process = _fake_process(rss_bytes=7 * 1024 ** 3)

    status = monitor.get_status(force_refresh=True)

    assert status["under_pressure"] is True
    assert status["ram_percent"] > 80.0
    assert monitor.is_under_pressure() is True


def test_callback_fires_on_edge_transition(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    received = []
    monitor.register_callback(lambda status: received.append(status))

    # Começa abaixo do limiar: sem pressão, sem callback.
    monitor._process = _fake_process(rss_bytes=1 * 1024 ** 3)
    monitor.get_status(force_refresh=True)
    assert len(received) == 0

    # Cruza para acima do limiar: dispara UMA vez.
    monitor._process = _fake_process(rss_bytes=7 * 1024 ** 3)
    monitor.get_status(force_refresh=True)
    assert len(received) == 1
    assert received[0]["under_pressure"] is True

    # Permanece acima do limiar: NÃO dispara de novo (edge-triggered).
    monitor.get_status(force_refresh=True)
    assert len(received) == 1

    # Volta a ficar abaixo do limiar: dispara de novo (transição de saída).
    monitor._process = _fake_process(rss_bytes=1 * 1024 ** 3)
    monitor.get_status(force_refresh=True)
    assert len(received) == 2
    assert received[1]["under_pressure"] is False


def test_unregister_callback_stops_notifications(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    received = []

    def cb(status):
        received.append(status)

    monitor.register_callback(cb)
    monitor.unregister_callback(cb)

    monitor._process = _fake_process(rss_bytes=7 * 1024 ** 3)
    monitor.get_status(force_refresh=True)

    assert received == []


def test_callback_exception_does_not_break_monitor(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)

    def bad_callback(status):
        raise RuntimeError("callback quebrado de propósito")

    monitor.register_callback(bad_callback)
    monitor._process = _fake_process(rss_bytes=7 * 1024 ** 3)

    # Não deve propagar a exceção do callback para o chamador.
    status = monitor.get_status(force_refresh=True)
    assert status["under_pressure"] is True


def test_process_count_reflects_children(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    monitor._process = _fake_process(rss_bytes=1 * 1024 ** 3, children=5)

    status = monitor.get_status(force_refresh=True)

    assert status["process_count"] == 6  # processo atual + 5 filhos


def test_get_status_without_refresh_returns_cached_or_measures_once(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    monitor._process = _fake_process(rss_bytes=1 * 1024 ** 3)

    first = monitor.get_status(force_refresh=False)
    assert "ram_percent" in first

    # Muda o processo "por baixo" sem forçar refresh: deve retornar o
    # snapshot em cache, não remedir.
    monitor._process = _fake_process(rss_bytes=7 * 1024 ** 3)
    cached = monitor.get_status(force_refresh=False)
    assert cached["ram_percent"] == first["ram_percent"]


def test_heavy_tool_names_cover_expected_tools():
    expected = {"run_python", "run_shell", "bandit_scan", "shellcheck_scan", "codebase_index", "firmware_check"}
    assert expected == HEAVY_TOOL_NAMES


def test_start_and_stop_thread_lifecycle(monkeypatch):
    monitor = _make_monitor(monkeypatch, ram_limit_gb=8.0)
    monitor._check_interval_s = 0.05
    monitor._process = _fake_process(rss_bytes=1 * 1024 ** 3)

    monitor.start()
    try:
        time.sleep(0.2)
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
    finally:
        monitor.stop()
        monitor._thread.join(timeout=2)
        assert not monitor._thread.is_alive()