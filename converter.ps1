# Conversor XLS/XLSX para CSV - Script PowerShell
# Executa o conversor Python com suporte a agendamento automático

param(
    [string]$Action = "convert",
    [string]$File = $null,
    [switch]$ScheduleDaily = $false
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptPath "xlsx_to_csv_converter.py"
$requirementsFile = Join-Path $scriptPath "requirements_converter.txt"

function Test-PythonInstalled {
    try {
        $output = & python --version 2>&1
        Write-Host "Python encontrado: $output" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Erro: Python não está instalado ou não está no PATH" -ForegroundColor Red
        Write-Host "Baixe Python em: https://www.python.org/downloads/" -ForegroundColor Yellow
        return $false
    }
}

function Install-Dependencies {
    Write-Host "Instalando dependências..." -ForegroundColor Cyan
    & pip install -r $requirementsFile -q
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Dependências instaladas com sucesso" -ForegroundColor Green
    } else {
        Write-Host "Erro ao instalar dependências" -ForegroundColor Red
        return $false
    }
    return $true
}

function Run-Converter {
    param([string]$Argument = "")

    Write-Host "`nIniciando conversor..." -ForegroundColor Cyan
    Write-Host ("="*50)

    if ($Argument) {
        & python $pythonScript $Argument
    } else {
        & python $pythonScript
    }

    Write-Host ("="*50)
}

function Schedule-Daily {
    Write-Host "Configurando tarefa agendada diária..." -ForegroundColor Cyan

    $taskName = "Conversor XLS para CSV - Itaú"
    $taskDescription = "Converte automaticamente arquivos XLS/XLSX para CSV da pasta do Itaú"
    $taskTime = "06:00"  # 6 da manhã

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" -Action convert"

    $trigger = New-ScheduledTaskTrigger -Daily -At $taskTime

    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest

    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

    $task = New-ScheduledTask -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description $taskDescription -TaskName $taskName

    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

    Write-Host "Tarefa agendada criada: '$taskName'" -ForegroundColor Green
    Write-Host "Horário: Todos os dias às $taskTime" -ForegroundColor Green
}

# Principal
if (-not (Test-PythonInstalled)) {
    exit 1
}

if (-not (Install-Dependencies)) {
    exit 1
}

switch ($Action) {
    "convert" {
        if ($File) {
            Run-Converter --single $File
        } else {
            Run-Converter
        }
    }
    "schedule" {
        Schedule-Daily
    }
    "help" {
        Write-Host @"
Conversor XLS/XLSX para CSV

Uso:
  .\converter.ps1                              # Converte todos os arquivos
  .\converter.ps1 -Action convert -File arquivo.xlsx  # Converte um arquivo
  .\converter.ps1 -Action schedule             # Agenda conversão diária
  .\converter.ps1 -Action help                 # Mostra esta ajuda

Recursos:
  • Converte automaticamente arquivos Excel
  • Suporta múltiplas abas
  • Agendamento automático diário
  • Log de operações
"@
    }
    default {
        Write-Host "Ação desconhecida: $Action" -ForegroundColor Red
        Write-Host "Use '-Action help' para mais informações" -ForegroundColor Yellow
    }
}
