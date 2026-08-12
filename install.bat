@echo off
REM Instalador Automático - Conversor XLS para CSV
REM Faz toda a configuração sozinho!

setlocal enabledelayedexpansion

color 0A
cls

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                   INSTALADOR AUTOMÁTICO                    ║
echo ║            Conversor XLS/XLSX para CSV v1.0                ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Verifica se tem privilégios de administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [⚠] Este programa precisa ser executado como Administrador
    echo.
    echo Clique com botão direito em install.bat e selecione:
    echo "Executar como administrador"
    echo.
    pause
    exit /b 1
)

echo [✓] Privilégios de administrador confirmados
echo.

REM ==================== VERIFICAR PYTHON ====================
echo ════════════════════════════════════════════════════════════
echo [1/4] Verificando Python...
echo ════════════════════════════════════════════════════════════

python --version >nul 2>&1

if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [✓] Python já está instalado: !PYTHON_VERSION!
    set PYTHON_INSTALLED=1
    goto :CHECK_PIP
)

echo [✗] Python não encontrado. Vou tentar instalar...
echo.

REM ==================== INSTALAR PYTHON ====================
echo [⚙] Baixando Python 3.12...

cd %temp%

REM Usa PowerShell para baixar Python
powershell -Command "(New-Object System.Net.ServicePointManager).SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe', 'python-installer.exe')" >nul 2>&1

if exist python-installer.exe (
    echo [✓] Download concluído
    echo.
    echo [⚙] Instalando Python (por favor aguarde ~2 minutos)...
    echo.

    REM Instala Python silenciosamente com PATH
    python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 >nul 2>&1

    REM Aguarda a instalação terminar
    timeout /t 5 >nul

    REM Verifica se instalação foi bem-sucedida
    python --version >nul 2>&1

    if !errorlevel! equ 0 (
        for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo [✓] Python instalado com sucesso: !PYTHON_VERSION!
        set PYTHON_INSTALLED=1

        REM Limpa o instalador
        del python-installer.exe >nul 2>&1
    ) else (
        echo [✗] Falha ao instalar Python
        echo.
        echo Solução: Instale Python manualmente em:
        echo https://www.python.org/downloads/
        echo.
        echo Importante: Marque "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
) else (
    echo [✗] Não conseguiu baixar Python
    echo.
    echo Solução: Instale Python manualmente em:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM ==================== VERIFICAR PIP ====================
:CHECK_PIP
echo.
echo ════════════════════════════════════════════════════════════
echo [2/4] Verificando gerenciador de pacotes (pip)...
echo ════════════════════════════════════════════════════════════

pip --version >nul 2>&1

if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('pip --version') do set PIP_VERSION=%%i
    echo [✓] pip está funcionando
) else (
    echo [✗] pip não encontrado
    echo [⚙] Instalando pip...

    python -m ensurepip --upgrade >nul 2>&1

    if !errorlevel! equ 0 (
        echo [✓] pip instalado com sucesso
    ) else (
        echo [✗] Falha ao instalar pip
        pause
        exit /b 1
    )
)

REM ==================== INSTALAR DEPENDÊNCIAS ====================
cd /d "%~dp0"

echo.
echo ════════════════════════════════════════════════════════════
echo [3/4] Instalando dependências Python...
echo ════════════════════════════════════════════════════════════

if exist requirements_converter.txt (
    echo [⚙] Instalando openpyxl e pandas (por favor aguarde ~1 minuto)...
    echo.

    pip install -r requirements_converter.txt -q

    if !errorlevel! equ 0 (
        echo [✓] Dependências instaladas com sucesso
    ) else (
        echo [⚠] Aviso ao instalar dependências
        echo Tentando instalar manualmente...

        pip install openpyxl pandas -q

        if !errorlevel! equ 0 (
            echo [✓] Dependências instaladas com sucesso
        ) else (
            echo [✗] Falha ao instalar dependências
            pause
            exit /b 1
        )
    )
) else (
    echo [✗] Arquivo requirements_converter.txt não encontrado
    pause
    exit /b 1
)

REM ==================== TESTE ====================
echo.
echo ════════════════════════════════════════════════════════════
echo [4/4] Testando instalação...
echo ════════════════════════════════════════════════════════════

python -c "import openpyxl; import pandas; print('OK')" >nul 2>&1

if !errorlevel! equ 0 (
    echo [✓] Todas as dependências estão funcionando
) else (
    echo [✗] Erro ao carregar dependências
    pause
    exit /b 1
)

REM ==================== SUCESSO ====================
echo.
echo ════════════════════════════════════════════════════════════
echo                    ✓ INSTALAÇÃO COMPLETA!
echo ════════════════════════════════════════════════════════════
echo.
echo Tudo está pronto! Agora você pode usar o conversor.
echo.
echo Para converter seus arquivos Excel:
echo.
echo   1. Abra esta pasta
echo   2. Clique DUPLO no arquivo: converter.bat
echo   3. Pronto! Os CSVs serão criados automaticamente
echo.
echo Arquivos Excel serão lidos de:
echo   C:\Users\Juliane\OneDrive\Documentos\Itaú
echo.
echo Os arquivos CSV aparecem na mesma pasta!
echo.
echo ════════════════════════════════════════════════════════════
echo.

pause

REM Executa o conversor automaticamente após instalação bem-sucedida
echo.
echo Executando conversor...
echo.

call converter.bat
