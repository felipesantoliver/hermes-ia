<#
============================================================
 DownloadFile.ps1
 Usado pelo instalador do Hermes AI (HermesSetup.iss) para
 baixar o modelo .gguf com barra de progresso e retomada
 automática, usando o BITS (Background Intelligent Transfer
 Service), nativo do Windows e sem necessidade de admin.

 Parâmetros:
   -Url          URL do arquivo a baixar
   -Destination  Caminho completo do arquivo de destino
   -StatusFile   Arquivo JSON onde o progresso é escrito
                 (lido pelo instalador a cada 1 segundo)
   -LogFile      Arquivo de log para erros
============================================================
#>

param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Destination,
    [Parameter(Mandatory = $true)][string]$StatusFile,
    [Parameter(Mandatory = $true)][string]$LogFile,
    [Parameter(Mandatory = $false)][string]$PidFile,
    [Parameter(Mandatory = $false)][string]$CancelFile
)

$ErrorActionPreference = "Stop"
$jobName = "HermesAI-ModelDownload"

# Grava o próprio PID assim que possível, para que o instalador (Inno Setup)
# consiga localizar e encerrar este processo caso o usuário clique em
# "Cancelar download" — antes disso, não havia nenhuma forma de interromper
# o download em andamento a partir da UI do instalador.
if ($PidFile) {
    try { [System.IO.File]::WriteAllText($PidFile, $PID.ToString()) } catch {}
}

function Write-Status {
    param($State, $Percent, $Transferred, $Total, $Message)
    $obj = [PSCustomObject]@{
        state       = $State
        percent     = $Percent
        transferred = $Transferred
        total       = $Total
        message     = $Message
    }
    $json = $obj | ConvertTo-Json -Compress
    # WriteAllText sem BOM - o parser simples do lado do Inno Setup espera
    # que o arquivo comece direto com "{"
    [System.IO.File]::WriteAllText($StatusFile, $json)
}

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format s)  $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

try {
    $destDir = Split-Path -Parent $Destination
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }

    Write-Status "starting" 0 0 0 "Iniciando download..."

    # Remove um job travado de uma tentativa anterior com o mesmo nome
    $existing = Get-BitsTransfer -Name $jobName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-BitsTransfer -BitsJob $existing -ErrorAction SilentlyContinue
    }

    # Inicia a transferência de forma assíncrona. O BITS cuida sozinho de
    # retomar em caso de queda de conexão (RetryInterval/RetryTimeout),
    # sem reiniciar o download do zero.
    $job = Start-BitsTransfer -Source $Url -Destination $Destination -DisplayName $jobName `
        -Asynchronous -RetryInterval 60 -RetryTimeout 3600 -ErrorAction Stop

    $jobId = $job.JobId
    $missingLookups = 0
    $maxMissingLookups = 3  # tolera algumas consultas falhas antes de desistir

    do {
        Start-Sleep -Seconds 1

        # Cancelamento solicitado pelo instalador (botão "Cancelar download"):
        # sem isso, mesmo matando este processo PowerShell, o BITS continuaria
        # baixando o arquivo em segundo plano gerenciado pelo Windows.
        if ($CancelFile -and (Test-Path $CancelFile)) {
            Write-Log "Download cancelado pelo usuário."
            $jobToRemove = Get-BitsTransfer -JobId $jobId -ErrorAction SilentlyContinue
            if ($jobToRemove) {
                Remove-BitsTransfer -BitsJob $jobToRemove -ErrorAction SilentlyContinue
            }
            Write-Status "cancelled" 0 0 0 "Download cancelado pelo usuário."
            exit 2
        }

        # Reconsulta pelo JobId (identificador único e estável) em vez do
        # nome: logo após a criação assíncrona pode haver uma pequena janela
        # em que o BITS ainda não indexou o job para busca por -Name, o que
        # fazia esta consulta falhar mesmo com o download rodando normalmente.
        $job = Get-BitsTransfer -JobId $jobId -ErrorAction SilentlyContinue

        if ($null -eq $job) {
            $missingLookups++
            Write-Log "AVISO: consulta ao job do BITS não encontrou resultado (tentativa $missingLookups de $maxMissingLookups)."
            if ($missingLookups -ge $maxMissingLookups) {
                Write-Log "ERRO: job de download desapareceu inesperadamente."
                Write-Status "error" 0 0 0 "O processo de download foi interrompido inesperadamente."
                exit 1
            }
            continue
        }
        $missingLookups = 0

        switch ($job.JobState) {
            "Connecting" {
                Write-Status "downloading" 0 0 0 "Conectando ao servidor..."
            }
            "Transferring" {
                $percent = 0
                if ($job.BytesTotal -gt 0) {
                    $percent = [math]::Round(($job.BytesTransferred / $job.BytesTotal) * 100)
                }
                Write-Status "downloading" $percent $job.BytesTransferred $job.BytesTotal ""
            }
            "TransientError" {
                # Conexão instável/caiu - o BITS tenta de novo sozinho
                Write-Status "downloading" 0 $job.BytesTransferred $job.BytesTotal `
                    "Conexão instável, tentando reconectar..."
            }
            "Transferred" {
                Complete-BitsTransfer -BitsJob $job
                Write-Status "done" 100 $job.BytesTotal $job.BytesTotal "Download concluído."
            }
            "Error" {
                $errorDesc = $job.ErrorDescription
                Write-Log "ERRO no download: $errorDesc"
                Remove-BitsTransfer -BitsJob $job -ErrorAction SilentlyContinue
                Write-Status "error" 0 0 0 $errorDesc
                exit 1
            }
        }
    } while ($job.JobState -ne "Transferred")

    exit 0
}
catch {
    Write-Log "ERRO FATAL: $($_.Exception.Message)"
    Write-Status "error" 0 0 0 $_.Exception.Message
    exit 1
}