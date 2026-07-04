# ===================== BUILD DO HERMES-IA.EXE (WINDOWS) =====================
# Uso: python build.py
#
# O que este script faz:
#   1. Confere que está rodando no Windows (PyInstaller --windowed +
#      Edge WebView2 são específicos de Windows).
#   2. Confere/instala pywebview e pyinstaller (dependências de build, não
#      de runtime do produto — por isso ficam fora do requirements.txt
#      principal, em requirements-windows.txt).
#   3. Gera icon.ico se ainda não existir (ou regenera se existir mas
#      estiver vazio/corrompido).
#   4. Roda o PyInstaller com os parâmetros corretos (--add-data usa ";"
#      como separador no Windows, "os.pathsep" cobre isso automaticamente).
#   5. Confirma que dist/Hermes-ia.exe foi criado e imprime os próximos
#      passos (copiar models/, testar).
#
# Requer Python 3.10+ (usa `subprocess.Popen | None` em main.py).

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ICON_PATH = ROOT / "icon.ico"


def _fail(msg: str) -> None:
    print(f"\n❌ {msg}")
    sys.exit(1)


def _check_platform() -> None:
    if os.name != "nt":
        print(
            "⚠️  Você não está no Windows. O build ainda vai rodar (útil para "
            "testar o empacotamento), mas o .exe resultante só roda de verdade "
            "em Windows 10/11 com Edge WebView2 — para distribuição final, "
            "rode este script numa máquina/CI Windows."
        )


def _ensure_build_deps() -> None:
    """pywebview e pyinstaller são dependências de BUILD/runtime do
    executável, não do backend em si — mantidas separadas do
    requirements.txt principal para não forçar quem só quer rodar o
    backend puro (dev/Linux) a instalar coisas específicas de empacotamento
    Windows."""
    req_file = ROOT / "requirements-windows.txt"
    if not req_file.exists():
        _fail(f"{req_file} não encontrado.")
    print("📦 Instalando dependências de build (requirements-windows.txt)...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        check=True,
    )


def _ensure_icon() -> None:
    if ICON_PATH.exists():
        if ICON_PATH.stat().st_size == 0:
            print("⚠️  icon.ico existe mas está vazio/corrompido (0 bytes) — removendo...")
            ICON_PATH.unlink()
        else:
            return
    print("🎨 icon.ico não encontrado — gerando um ícone padrão (make_icon.py)...")
    make_icon = ROOT / "make_icon.py"
    if not make_icon.exists():
        _fail("make_icon.py não encontrado e icon.ico ausente. Gere um .ico manualmente.")
    subprocess.run([sys.executable, str(make_icon)], check=True)
    if not ICON_PATH.exists():
        _fail("make_icon.py rodou mas icon.ico ainda não existe.")
    if ICON_PATH.stat().st_size == 0:
        _fail("make_icon.py rodou mas icon.ico ainda está vazio (0 bytes).")


def _clean_previous_build() -> None:
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"🧹 Removendo build anterior: {d}")
            shutil.rmtree(d)


def _run_pyinstaller() -> None:
    sep = os.pathsep  # ';' no Windows, ':' no Linux/Mac
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        f"--icon={ICON_PATH}",
        "--name", "Hermes-ia",
        "--add-data", f"frontend{sep}frontend",
        "--add-data", f"backend{sep}backend",
        "--hidden-import", "pywebview",
        "--hidden-import", "fastapi",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.loops.auto",
        "main.py",
    ]
    print("🔨 Rodando PyInstaller:\n   " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        _fail("PyInstaller falhou — veja o log acima.")


def main() -> None:
    print(f"=== Build Hermes-ia.exe ===\nRaiz do projeto: {ROOT}\n")
    _check_platform()
    _ensure_build_deps()
    _ensure_icon()
    _clean_previous_build()
    _run_pyinstaller()

    exe_path = DIST_DIR / "Hermes-ia.exe"
    if not exe_path.exists():
        _fail(f"Build terminou mas {exe_path} não foi encontrado.")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ Build concluído: {exe_path} ({size_mb:.1f} MB)")
    print(
        "\nPróximos passos:\n"
        f"  1. Copie a pasta models/ (com hermes-core.gguf) para {DIST_DIR}/models/\n"
        f"  2. Rode {DIST_DIR}/Hermes-ia.exe e confirme que abre sem terminal\n"
        "  3. (Opcional) rode install.ps1 para criar atalhos, ou distribua a "
        "pasta dist/ inteira como está."
    )


if __name__ == "__main__":
    main()