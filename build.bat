@echo off
setlocal enabledelayedexpansion
title Hermes-ia - Build

echo ===================================
echo   Hermes-ia - Build do executavel
echo ===================================
echo.

echo [1/3] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Python nao foi encontrado no PATH.
    echo Instale o Python 3.10+ em https://www.python.org/downloads/
    echo e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)
python --version
echo.

echo [2/3] Instalando dependencias do backend (backend\requirements.txt)...
pip install -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias do backend.
    echo Verifique sua conexao com a internet e o arquivo backend\requirements.txt
    echo.
    pause
    exit /b 1
)
echo.

echo [3/3] Rodando build.py (gera o icone, empacota com PyInstaller)...
python build.py
if errorlevel 1 (
    echo.
    echo [ERRO] O build falhou. Veja as mensagens acima para detalhes.
    echo.
    pause
    exit /b 1
)

echo.
echo ===================================
echo   Build concluido com sucesso!
echo   Executavel gerado em: dist\Hermes-ia.exe
echo ===================================
echo.
pause
exit /b 0