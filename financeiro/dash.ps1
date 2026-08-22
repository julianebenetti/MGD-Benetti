<#
.SYNOPSIS
    Controla a dashboard financeira a partir do PowerShell.

.DESCRIPTION
    Reúne num só lugar o que antes exigia abrir o terminal do VPS pelo
    navegador. Os comandos se dividem em dois grupos:

      Só precisam de SSH (já vem no Windows 10 e 11):
        deploy    publica no VPS a última versão e reinicia o serviço
        status    mostra se o serviço está no ar e o que ele carregou
        log       últimas linhas do log do servidor
        abrir     abre a dashboard no navegador

      Precisam de Git e Node.js na máquina (rode 'setup' uma vez):
        setup       prepara a cópia local
        importar    lê as faturas .xlsx e atualiza os dados
        regras      aplica as regras de classificação
        planilha    gera o .xlsx de revisão de classificação
        testar      roda a suíte de testes
        enviar      envia para o GitHub o que foi processado aqui

.EXAMPLE
    .\dash.ps1 deploy
    .\dash.ps1 importar C:\Users\Juliane\Downloads\faturas
    .\dash.ps1 status
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('deploy', 'status', 'log', 'abrir', 'setup', 'importar', 'regras', 'planilha', 'testar', 'enviar', 'ajuda')]
    [string]$Comando = 'ajuda',

    [Parameter(Position = 1)]
    [string]$Caminho,

    [switch]$Simular
)

$ErrorActionPreference = 'Stop'

# --------------------------------------------------------------- configuração

$ArquivoConfig = Join-Path $PSScriptRoot 'dash.config.json'

$Config = if (Test-Path $ArquivoConfig) {
    Get-Content $ArquivoConfig -Raw | ConvertFrom-Json
} else {
    [pscustomobject]@{
        VpsHost      = 'root@179.198.96.133'
        VpsPasta     = '/root/mgd-benetti'
        Branch       = 'claude/financial-dashboard-pbj1ts'
        Servico      = 'financeiro'
        UrlDashboard = 'http://179.198.96.133:3001'
        PastaLocal   = Join-Path $HOME 'mgd-benetti'
        RepoGit      = 'https://github.com/julianebenetti/MGD-Benetti.git'
    }
}

if (-not (Test-Path $ArquivoConfig)) {
    $Config | ConvertTo-Json | Set-Content $ArquivoConfig -Encoding UTF8
    Write-Host "Configuração criada em $ArquivoConfig — ajuste o endereço do VPS se precisar.`n" -ForegroundColor DarkGray
}

# ------------------------------------------------------------------- auxiliares

function Escrever($Texto, $Cor = 'Gray') { Write-Host $Texto -ForegroundColor $Cor }
function Titulo($Texto) { Write-Host "`n$Texto" -ForegroundColor Cyan }
function Erro($Texto) { Write-Host "  $Texto" -ForegroundColor Red }
function Ok($Texto) { Write-Host "  $Texto" -ForegroundColor Green }

function TemComando($Nome) { $null -ne (Get-Command $Nome -ErrorAction SilentlyContinue) }

function ExigirSsh {
    if (-not (TemComando 'ssh')) {
        Erro 'O SSH não está disponível.'
        Escrever '  No Windows 10 ou 11: Configurações > Aplicativos > Recursos opcionais'
        Escrever '  > Adicionar recurso > "Cliente OpenSSH".'
        exit 1
    }
}

function ExigirFerramentasLocais {
    $faltando = @()
    if (-not (TemComando 'git'))  { $faltando += 'Git — https://git-scm.com/download/win' }
    if (-not (TemComando 'node')) { $faltando += 'Node.js — https://nodejs.org (versão LTS)' }

    if ($faltando.Count) {
        Erro 'Falta instalar para rodar este comando na sua máquina:'
        $faltando | ForEach-Object { Escrever "    $_" }
        Escrever ''
        Escrever '  Enquanto isso, deploy, status, log e abrir continuam funcionando.'
        exit 1
    }
}

function ExigirCopiaLocal {
    ExigirFerramentasLocais
    if (-not (Test-Path (Join-Path $Config.PastaLocal 'financeiro'))) {
        Erro "Não encontrei a cópia local em $($Config.PastaLocal)."
        Escrever '  Rode primeiro:  .\dash.ps1 setup'
        exit 1
    }
}

function NoVps($ComandoRemoto) {
    ExigirSsh
    ssh $Config.VpsHost $ComandoRemoto
    if ($LASTEXITCODE -ne 0) { throw "O comando falhou no VPS (código $LASTEXITCODE)." }
}

function LocalmenteNode($Argumentos) {
    $pasta = Join-Path $Config.PastaLocal 'financeiro'
    Push-Location $pasta
    try {
        & node @Argumentos
        if ($LASTEXITCODE -ne 0) { throw "O script terminou com erro (código $LASTEXITCODE)." }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------- comandos

function Comando-Deploy {
    Titulo 'Publicando no VPS'
    NoVps "cd $($Config.VpsPasta)/financeiro && ./atualizar.sh"
    Ok 'Publicado. Abra a dashboard e dê Ctrl+Shift+R para limpar o cache.'
}

function Comando-Status {
    Titulo 'Situação do serviço'
    ExigirSsh

    $saude = ssh $Config.VpsHost "curl -sf localhost:3001/api/health || echo INDISPONIVEL"
    if ($saude -match 'INDISPONIVEL') {
        Erro 'O serviço não está respondendo.'
        Escrever '  Veja o motivo com:  .\dash.ps1 log'
        return
    }
    Ok 'No ar'

    $resumo = ssh $Config.VpsHost @'
curl -s localhost:3001/api/dados | node -e '
let e="";process.stdin.on("data",d=>e+=d).on("end",()=>{
  const j=JSON.parse(e);
  const t=(j.fluxo_mensal||{}).transacoes||[];
  const g=t.filter(x=>x.natureza!=="pagamento");
  const brl=v=>"R$ "+v.toLocaleString("pt-BR",{minimumFractionDigits:2});
  const por={};g.forEach(x=>{const a=x.ambito||"pessoal";por[a]=(por[a]||0)+x.valor;});
  console.log("lancamentos|"+g.length);
  Object.entries(por).forEach(([k,v])=>console.log(k+"|"+brl(v)));
  (j.faturas_cartao||[]).filter(f=>f.em_aberto>0.05)
    .forEach(f=>console.log("aberto "+f.cartao+" "+f.mes+"|"+brl(f.em_aberto)));
});'
'@
    $resumo -split "`n" | Where-Object { $_ -match '\|' } | ForEach-Object {
        $parte = $_ -split '\|'
        $cor = if ($parte[0] -like 'aberto*') { 'Yellow' } else { 'Gray' }
        Write-Host ("  {0,-22} {1}" -f $parte[0], $parte[1]) -ForegroundColor $cor
    }
}

function Comando-Log {
    Titulo 'Últimas linhas do log'
    NoVps "pm2 logs $($Config.Servico) --lines 40 --nostream"
}

function Comando-Abrir {
    Escrever "Abrindo $($Config.UrlDashboard)"
    try { Start-Process $Config.UrlDashboard -ErrorAction Stop }
    catch { Escrever "  Abra no navegador: $($Config.UrlDashboard)" -Cor DarkGray }
}

function Comando-Setup {
    Titulo 'Preparando a cópia local'
    ExigirFerramentasLocais

    if (Test-Path (Join-Path $Config.PastaLocal '.git')) {
        Escrever '  Já existe. Atualizando.'
        Push-Location $Config.PastaLocal
        try { git pull --ff-only origin $Config.Branch } finally { Pop-Location }
    } else {
        Escrever "  Clonando em $($Config.PastaLocal)"
        git clone --branch $Config.Branch $Config.RepoGit $Config.PastaLocal
    }

    Escrever '  Instalando dependências'
    Push-Location (Join-Path $Config.PastaLocal 'financeiro')
    try { npm install --silent } finally { Pop-Location }

    Ok 'Pronto. Agora dá para usar importar, regras, planilha e testar.'
    Escrever ''
    Escrever '  Para a suíte de testes é preciso também o Chromium:'
    Escrever '    npx playwright install chromium'
}

function Comando-Importar {
    ExigirCopiaLocal

    if (-not $Caminho) {
        Erro 'Informe a pasta com as faturas .xlsx.'
        Escrever '  Exemplo:  .\dash.ps1 importar C:\Users\Juliane\Downloads\faturas'
        exit 1
    }
    if (-not (Test-Path $Caminho)) { Erro "Pasta não encontrada: $Caminho"; exit 1 }

    $faturas = Get-ChildItem -Path $Caminho -Filter '*.xlsx' -File
    if (-not $faturas) { Erro "Nenhum .xlsx em $Caminho"; exit 1 }

    Titulo "Importando de $Caminho"
    $faturas | ForEach-Object { Escrever "  $($_.Name)" }

    $env:DIR_FATURAS = (Resolve-Path $Caminho).Path
    $args = @('scripts/importar-faturas-itau.js')
    if (-not $Simular) { $args += '--aplicar' }
    LocalmenteNode $args

    if ($Simular) { Escrever "`n  Foi só simulação. Repita sem -Simular para gravar." -Cor DarkGray }
    else { Ok 'Importado. Rode .\dash.ps1 enviar e depois .\dash.ps1 deploy.' }
}

function Comando-Regras {
    ExigirCopiaLocal
    Titulo 'Aplicando as regras de classificação'
    $args = @('scripts/classificar.js', 'aplicar')
    if (-not $Simular) { $args += '--aplicar' }
    LocalmenteNode $args
}

function Comando-Planilha {
    ExigirCopiaLocal
    Titulo 'Gerando a planilha de revisão'
    $saida = if ($Caminho) { $Caminho } else { Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'classificar.xlsx' }
    LocalmenteNode @('scripts/classificar.js', 'exportar', $saida, '--so-pendentes')
    if (Test-Path $saida) {
        Ok "Salva em $saida"
        # Abrir e conveniencia, nao parte do trabalho: se nao houver programa
        # associado, avisa em vez de interromper.
        try { Start-Process $saida -ErrorAction Stop }
        catch { Escrever '  (abra o arquivo manualmente)' -Cor DarkGray }
    }
}

function Comando-Testar {
    ExigirCopiaLocal
    Titulo 'Rodando a suíte de testes'
    Escrever '  Subindo o servidor local'

    $pasta = Join-Path $Config.PastaLocal 'financeiro'

    # -WindowStyle so existe no Windows; no Linux e macOS o parametro nao e aceito
    $opcoes = @{ FilePath = 'node'; ArgumentList = 'server.js'; WorkingDirectory = $pasta; PassThru = $true }
    if ($IsWindows -or $null -eq $IsWindows) { $opcoes.WindowStyle = 'Hidden' }

    $servidor = Start-Process @opcoes
    try {
        Start-Sleep -Seconds 3
        LocalmenteNode @('scripts/testar-dashboard.js')
    } finally {
        if ($servidor -and -not $servidor.HasExited) {
            Stop-Process -Id $servidor.Id -Force -ErrorAction SilentlyContinue
            Escrever '  Servidor local encerrado' -Cor DarkGray
        }
    }
}

function Comando-Enviar {
    ExigirCopiaLocal
    Titulo 'Enviando para o GitHub'
    Push-Location $Config.PastaLocal
    try {
        $mudou = git status --porcelain
        if (-not $mudou) { Escrever '  Nada mudou.'; return }

        Escrever '  Arquivos alterados:'
        $mudou -split "`n" | ForEach-Object { Escrever "    $_" }

        git add -A
        git commit -m "Atualiza dados financeiros a partir das faturas"
        git push origin $Config.Branch
        Ok 'Enviado. Agora rode .\dash.ps1 deploy.'
    } finally { Pop-Location }
}

function Comando-Ajuda {
    Write-Host @"

  DASHBOARD FINANCEIRA — comandos

  Só precisam de SSH, que já vem no Windows:

    .\dash.ps1 deploy        publica a última versão no VPS e reinicia
    .\dash.ps1 status        mostra se está no ar e o que carregou
    .\dash.ps1 log           últimas linhas do log do servidor
    .\dash.ps1 abrir         abre a dashboard no navegador

  Precisam de Git e Node.js instalados aqui:

    .\dash.ps1 setup                 prepara a cópia local (uma vez só)
    .\dash.ps1 importar <pasta>      lê as faturas .xlsx e atualiza os dados
    .\dash.ps1 regras                aplica as regras de classificação
    .\dash.ps1 planilha [arquivo]    gera o .xlsx de revisão
    .\dash.ps1 testar                roda a suíte de testes
    .\dash.ps1 enviar                envia o que foi processado para o GitHub

  -Simular  em importar e regras: mostra o que aconteceria, sem gravar.

  Fluxo depois de baixar uma fatura nova:

    .\dash.ps1 importar C:\...\faturas
    .\dash.ps1 testar
    .\dash.ps1 enviar
    .\dash.ps1 deploy

  Configuração do VPS e das pastas: dash.config.json, na mesma pasta.

"@ -ForegroundColor Gray
}

# ------------------------------------------------------------------- execução

try {
    switch ($Comando) {
        'deploy'   { Comando-Deploy }
        'status'   { Comando-Status }
        'log'      { Comando-Log }
        'abrir'    { Comando-Abrir }
        'setup'    { Comando-Setup }
        'importar' { Comando-Importar }
        'regras'   { Comando-Regras }
        'planilha' { Comando-Planilha }
        'testar'   { Comando-Testar }
        'enviar'   { Comando-Enviar }
        default    { Comando-Ajuda }
    }
} catch {
    Write-Host ''
    Erro $_.Exception.Message
    exit 1
}
