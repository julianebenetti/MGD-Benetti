@echo off
REM Conversor XLS/XLSX para CSV - Script Batch
REM Executa o conversor Python

cd /d "%~dp0"

REM Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo Erro: Python não está instalado ou não está no PATH
    echo Baixe Python em: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Instala dependências se necessário
echo Verificando dependências...
pip install -r requirements_converter.txt -q

REM Executa o conversor
echo.
echo Iniciando conversor...
echo.
python xlsx_to_csv_converter.py %*

pause
