# ===================== INSTALADOR OPCIONAL DO HERMES AI =====================
# Uso: clique com o botão direito neste arquivo > "Executar com PowerShell"
# (ou rode `powershell -ExecutionPolicy Bypass -File install.ps1` num
# terminal). Precisa ser executado de dentro da pasta que já contém
# Hermes-ia.exe, models/ etc. (ou seja, rode isso a partir de dist/, ou da
# pasta que você extraiu do .zip de distribuição).
#
# O que faz:
#   1. Copia a pasta atual para C:\Program Files\Hermes-ia\
#   2. Cria atalho na Área de Trabalho
#   3. Cria atalho no Menu Iniciar
#
# Totalmente opcional — o Hermes-ia.exe funciona rodando direto de qualquer
# pasta, sem instalação. Isso é só conveniência.

$ErrorActionPreference = "Stop"

$sourceDir = $PSScriptRoot
$exeName = "Hermes-ia.exe"
$exePath = Join-Path $sourceDir $exeName

if (-not (Test-Path $exePath)) {
    Write-Host "❌ $exeName não encontrado em $sourceDir." -ForegroundColor Red
    Write-Host "   Rode este script a partir da pasta que contém o Hermes-ia.exe (normalmente dist/)."
    exit 1
}

$installDir = "C:\Program Files\Hermes-ia"

Write-Host "📁 Copiando arquivos para $installDir ..."
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir '*') -Destination $installDir -Recurse -Force

$installedExe = Join-Path $installDir $exeName

# --------------------- Atalho na Área de Trabalho ---------------------
$desktop = [Environment]::GetFolderPath("Desktop")
$desktopShortcut = Join-Path $desktop "Hermes AI.lnk"

Write-Host "🖥️  Criando atalho na Área de Trabalho ..."
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $installedExe
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $installedExe
$shortcut.Description = "Hermes AI - assistente local de engenharia de software"
$shortcut.Save()

# --------------------- Atalho no Menu Iniciar ---------------------
$startMenu = [Environment]::GetFolderPath("StartMenu")
$startMenuPrograms = Join-Path $startMenu "Programs"
$startMenuShortcut = Join-Path $startMenuPrograms "Hermes AI.lnk"

Write-Host "📌 Criando atalho no Menu Iniciar ..."
$shortcut2 = $shell.CreateShortcut($startMenuShortcut)
$shortcut2.TargetPath = $installedExe
$shortcut2.WorkingDirectory = $installDir
$shortcut2.IconLocation = $installedExe
$shortcut2.Description = "Hermes AI - assistente local de engenharia de software"
$shortcut2.Save()

Write-Host ""
Write-Host "✅ Instalação concluída." -ForegroundColor Green
Write-Host "   - Instalado em: $installDir"
Write-Host "   - Atalho na Área de Trabalho: $desktopShortcut"
Write-Host "   - Atalho no Menu Iniciar: $startMenuShortcut"
Write-Host ""
Write-Host "⚠️  Lembre-se de colocar o modelo .gguf em:"
Write-Host "   $installDir\models\hermes-core.gguf"