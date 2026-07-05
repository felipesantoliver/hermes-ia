# ===================== HERMES-IA.EXE — LAUNCHER NATIVO (WINDOWS) =====================
# Responsabilidade: este é o ponto de entrada do executável final. Ele NÃO
# contém lógica de produto — só orquestra o processo:
#
#   1. Descobre onde o app está rodando de fato (pasta do .exe em modo
#      empacotado, ou raiz do repo em modo dev) e exporta isso como env vars
#      ANTES de importar qualquer coisa do backend, para que backend/app/db.py
#      e backend/app/config.py gravem dados/leiam o modelo no lugar certo.
#   2. Sobe o backend FastAPI (uvicorn) numa thread, sem abrir terminal.
#   3. Opcionalmente inicia o llama-server como subprocesso, se configurado.
#   4. Espera o backend responder antes de abrir a janela — evita tela em
#      branco / erro de conexão do WebView2.
#   5. Abre a janela nativa (pywebview + Edge WebView2) apontando para o
#      backend local. A splash screen inteligente (frontend/js/spheres.js)
#      já cuida da transição visual assim que a página carrega.
#   6. No fechamento da janela, derruba backend e llama-server de forma limpa.
#
# Este arquivo roda tanto em modo dev (`python main.py`) quanto empacotado
# (Hermes-ia.exe via PyInstaller — ver build.py).

import os
import sys
import time
import socket
import threading
import subprocess
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
BACKEND_READY_TIMEOUT_S = 15
APP_TITLE = "Hermes AI"
WINDOW_W, WINDOW_H = 1280, 800
WINDOW_MIN_W, WINDOW_MIN_H = 960, 600


# --------------------- 1. RESOLVER DIRETÓRIO BASE ---------------------
def _app_dir() -> Path:
    """Pasta onde o Hermes-ia.exe está (modo empacotado) ou raiz do repo
    (modo dev). NUNCA usar sys._MEIPASS aqui para dados persistentes — essa
    pasta é temporária e é apagada a cada execução do .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_dir() -> Path:
    """Pasta de onde ler os arquivos EMBUTIDOS no .exe (backend/ e frontend/
    copiados via --add-data). Em modo dev é a mesma raiz do repo."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


APP_DIR = _app_dir()
BUNDLE_DIR = _bundle_dir()

DATA_DIR = APP_DIR / "data"
MODELS_DIR = APP_DIR / "models"
LOG_DIR = DATA_DIR / "logs"

# Exporta ANTES de importar o backend (db.py e config.py leem essas env vars
# no import do módulo, então a ordem aqui importa).
os.environ["HERMES_DATA_DIR"] = str(DATA_DIR)
os.environ["HERMES_BASE_DIR"] = str(APP_DIR)
os.environ["HERMES_FRONTEND_DIR"] = str(BUNDLE_DIR / "frontend")

DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Permite o backend (que foi extraído em BUNDLE_DIR/backend) ser importado
# como pacote "app".
sys.path.insert(0, str(BUNDLE_DIR / "backend"))


# --------------------- 2. ERRO NATIVO (sem terminal) ---------------------
def _show_error(message: str) -> None:
    """Caixa de diálogo nativa do Windows, sem depender do terminal (que
    fica escondido pelo --windowed do PyInstaller)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_TITLE, message)
        root.destroy()
    except Exception:
        # Último recurso: stderr (só visível se rodando via `python main.py`)
        print(f"[{APP_TITLE}] ERRO: {message}", file=sys.stderr)


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


# --------------------- 3. LLAMA-SERVER (opcional, best-effort) ---------------------
_llama_process: subprocess.Popen | None = None


def _maybe_start_llama_server() -> None:
    """Se existir um binário llama-server.exe ao lado do modelo/app e o
    modelo padrão estiver presente, sobe o llama-server como subprocesso
    filho. É best-effort: se falhar, o app segue e a splash/painel de
    status vão mostrar "llm: unavailable" — o usuário decide se sobe o
    llama-server manualmente. Isso NUNCA bloqueia a abertura da janela."""
    global _llama_process

    model_path = MODELS_DIR / "hermes-core.gguf"
    llama_bin = APP_DIR / "llama-server.exe"

    if not model_path.exists() or not llama_bin.exists():
        return

    if not _is_port_free("127.0.0.1", 8080):
        _show_error(
            "A porta 8080 (usada pelo llama-server) já está ocupada por outro "
            "programa ou por uma instância anterior do Hermes que não foi "
            "encerrada corretamente.\n\n"
            "O Hermes vai abrir mesmo assim, mas sem respostas do LLM até "
            "você liberar a porta 8080 (verifique o Gerenciador de Tarefas "
            "por 'llama-server.exe' e finalize o processo, depois reabra o "
            "Hermes)."
        )
        return

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        # Antes isso ia pro DEVNULL: se o llama-server travasse ao subir (DLL
        # faltando, variante Vulkan incompatível com a GPU, etc.) não sobrava
        # nenhum rastro — parecia exatamente igual a "ainda carregando o
        # modelo". Agora gravamos tudo em data/logs/llama-server.log.
        llama_log_path = LOG_DIR / "llama-server.log"
        llama_log = open(llama_log_path, "a", encoding="utf-8", errors="replace")
        _llama_process = subprocess.Popen(
            [
                str(llama_bin),
                "--model", str(model_path),
                "--host", "127.0.0.1",
                "--port", "8080",
                "--ctx-size", "4096",
            ],
            cwd=str(APP_DIR),
            creationflags=creationflags,
            stdout=llama_log,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        _show_error(
            "Não foi possível iniciar o llama-server automaticamente.\n"
            f"Detalhe: {e}\n\nO Hermes vai abrir mesmo assim; inicie o "
            "modelo manualmente se quiser respostas do LLM."
        )


def _stop_llama_server() -> None:
    if _llama_process and _llama_process.poll() is None:
        try:
            _llama_process.terminate()
            _llama_process.wait(timeout=5)
        except Exception:
            try:
                _llama_process.kill()
            except Exception:
                pass


# --------------------- 4. BACKEND (uvicorn em thread) ---------------------
_uvicorn_server = None


def _load_backend_app():
    """Importa backend/backend_main.py (que define `app = FastAPI(...)`) sob
    um nome de módulo próprio ("hermes_backend_main"), para nunca colidir
    com este arquivo (que se chama main.py, mas é outro processo lógico: o
    launcher, não o backend)."""
    import importlib.util

    backend_main_path = BUNDLE_DIR / "backend" / "backend_main.py"
    spec = importlib.util.spec_from_file_location("hermes_backend_main", backend_main_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


_backend_error_path = LOG_DIR / "backend_startup_error.log"


def _run_backend() -> None:
    global _uvicorn_server
    try:
        import uvicorn

        backend_app = _load_backend_app()
        config = uvicorn.Config(
            backend_app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            # Sem isso, o uvicorn tenta decidir sozinho se deve colorir os
            # logs chamando sys.stdout.isatty() — e no .exe empacotado com
            # --windowed não existe console, então sys.stdout é None e essa
            # chamada explode com AttributeError (é exatamente o que aparece
            # em backend_startup_error.log). Forçar False evita o isatty().
            use_colors=False,
        )
        _uvicorn_server = uvicorn.Server(config)
        _uvicorn_server.run()
    except Exception:
        # A thread do backend é daemon: se algo falhar aqui (import quebrado,
        # dependência faltando no .exe empacotado, etc.), a exceção some em
        # stderr (invisível no app --windowed) e o launcher só vê o timeout
        # em _wait_backend_ready. Por isso gravamos o traceback completo em
        # disco — é o que diferencia "porta ocupada" de "bug real no backend".
        import traceback
        try:
            with open(_backend_error_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass


def _wait_backend_ready(timeout_s: int) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    url = f"http://{HOST}:{PORT}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


# --------------------- 5. JANELA (pywebview) ---------------------
def main() -> None:
    if not _is_port_free(HOST, PORT):
        _show_error(
            f"A porta {PORT} já está em uso.\n\n"
            "Feche qualquer outro programa usando essa porta (ou outra "
            "instância do Hermes já aberta) e tente novamente."
        )
        sys.exit(1)

    if not (MODELS_DIR / "hermes-core.gguf").exists():
        # Aviso não-bloqueante: o usuário pode estar usando um llama-server
        # externo já rodando, então não impedimos a abertura do app.
        pass

    _maybe_start_llama_server()

    if _backend_error_path.exists():
        try:
            _backend_error_path.unlink()
        except Exception:
            pass

    backend_thread = threading.Thread(target=_run_backend, daemon=True)
    backend_thread.start()

    if not _wait_backend_ready(BACKEND_READY_TIMEOUT_S):
        if _backend_error_path.exists():
            _show_error(
                "Erro ao iniciar o Hermes.\n\n"
                "O backend travou durante a inicialização.\n\n"
                f"Detalhes completos em:\n{_backend_error_path}"
            )
        else:
            _show_error(
                "Erro ao iniciar o Hermes.\n\n"
                "O backend não respondeu a tempo. Verifique se a porta 8000 "
                "está livre e se o modelo está em models/hermes-core.gguf.\n\n"
                f"Se o problema persistir, verifique {_backend_error_path} "
                "após a próxima tentativa."
            )
        sys.exit(1)

    import webview

    # No Windows, o ícone da janela/taskbar/atalho vem do recurso .ico
    # embutido no próprio .exe pelo PyInstaller (--icon=icon.ico, ver
    # build.py) — pywebview não precisa (nem consegue, de forma confiável,
    # no backend edgechromium) trocar o ícone em runtime.
    window = webview.create_window(
        APP_TITLE,
        url=f"http://{HOST}:{PORT}/",
        width=WINDOW_W,
        height=WINDOW_H,
        min_size=(WINDOW_MIN_W, WINDOW_MIN_H),
        background_color="#0b0b0f",
    )

    def _on_closing():
        _stop_llama_server()
        if _uvicorn_server is not None:
            _uvicorn_server.should_exit = True
        return True

    window.events.closing += _on_closing

    webview.start(gui="edgechromium", debug=False)


if __name__ == "__main__":
    main()
