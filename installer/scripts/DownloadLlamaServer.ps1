<#
============================================================
 DownloadLlamaServer.ps1
 Usado pelo instalador do Hermes AI (HermesSetup.iss) para
 baixar o binário do llama-server (motor de inferência) a
 partir dos releases oficiais do llama.cpp no GitHub, e
 extraí-lo direto na pasta de instalação.

 Isso existe porque main.py (_maybe_start_llama_server) exige
 "{app}\llama-server.exe" para subir o LLM local — e, até esta
 correção, nada no instalador nem no build.py colocava esse
 arquivo lá. O .gguf sozinho não é suficiente.

 Parâmetros:
   -Variant     "cpu" ou "vulkan" (decidido pela GPU escolhida
                no instalador; Vulkan funciona tanto em NVIDIA
                quanto AMD/Intel, evitando lidar com runtime
                CUDA separado)
   -DestDir     Pasta onde extrair (a raiz da instalação, ao
                lado de Hermes-ia.exe)
   -StatusFile  Arquivo JSON de progresso (mesmo formato usado
                por DownloadFile.ps1, lido pelo instalador)
   -LogFile     Arquivo de log para erros
============================================================
#>

param(
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "vulkan")][string]$Variant,
    [Parameter(Mandatory = $true)][string]$DestDir,
    [Parameter(Mandatory = $true)][string]$StatusFile,
    [Parameter(Mandatory = $true)][string]$LogFile
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Write-Status {
    param($State, $Percent, $Message)
    $obj = [PSCustomObject]@{
        state   = $State
        percent = $Percent
        message = $Message
    }
    $json = $obj | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($StatusFile, $json)
}

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format s)  $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

try {
    if (-not (Test-Path $DestDir)) {
        New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    }

    Write-Status "starting" 0 "Verificando última versão do llama.cpp..."

    # Repositório oficial: https://github.com/ggml-org/llama.cpp
    # A API do GitHub exige um User-Agent explícito, senão retorna 403.
    $headers = @{ "User-Agent" = "Hermes-AI-Installer" }
    $release = $null
    $attempts = 0
    while ($attempts -lt 3 -and $null -eq $release) {
        $attempts++
        try {
            $release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" `
                -Headers $headers -TimeoutSec 15
        } catch {
            Write-Log "AVISO: falha ao consultar release mais recente (tentativa $attempts de 3): $($_.Exception.Message)"
            Start-Sleep -Seconds 2
        }
    }

    if ($null -eq $release) {
        Write-Log "ERRO: não foi possível consultar a API do GitHub para achar a versão mais recente do llama.cpp."
        Write-Status "error" 0 "Não foi possível verificar a versão mais recente do motor de IA (llama.cpp). Verifique sua conexão."
        exit 1
    }

    $tag = $release.tag_name
    $assetName = "llama-$tag-bin-win-$Variant-x64.zip"
    $asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1

    if ($null -eq $asset) {
        Write-Log "ERRO: asset '$assetName' não encontrado no release '$tag'."
        Write-Status "error" 0 "Não achei o pacote '$assetName' no release mais recente do llama.cpp."
        exit 1
    }

    $zipPath = Join-Path $env:TEMP "hermes_llama_$tag.zip"
    Remove-Item -Path $zipPath -ErrorAction SilentlyContinue

    Write-Status "downloading" 10 "Baixando o motor de IA ($tag)..."
    Write-Log "Baixando $($asset.browser_download_url) -> $zipPath"

    $downloaded = $false
    for ($i = 1; $i -le 3; $i++) {
        try {
            Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing -TimeoutSec 300
            $downloaded = $true
            break
        } catch {
            Write-Log "AVISO: falha no download (tentativa $i de 3): $($_.Exception.Message)"
            Start-Sleep -Seconds 3
        }
    }

    if (-not $downloaded -or -not (Test-Path $zipPath)) {
        Write-Log "ERRO: download do llama-server falhou após 3 tentativas."
        Write-Status "error" 0 "Falha ao baixar o motor de IA (llama-server) após várias tentativas."
        exit 1
    }

    Write-Status "extracting" 80 "Extraindo o motor de IA..."
    Expand-Archive -Path $zipPath -DestinationPath $DestDir -Force
    Remove-Item -Path $zipPath -ErrorAction SilentlyContinue

    $serverExe = Join-Path $DestDir "llama-server.exe"
    if (-not (Test-Path $serverExe)) {
        Write-Log "ERRO: llama-server.exe não encontrado em $DestDir após extração."
        Write-Status "error" 0 "O pacote foi baixado, mas llama-server.exe não apareceu na pasta esperada."
        exit 1
    }

    Write-Log "OK: llama-server.exe instalado em $DestDir (release $tag, variante $Variant)."
    Write-Status "done" 100 "Motor de IA instalado."
    exit 0
}
catch {
    Write-Log "ERRO FATAL: $($_.Exception.Message)"
    Write-Status "error" 0 $_.Exception.Message
    exit 1
}