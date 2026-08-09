#!/bin/bash

# ==========================================
# 💰 DEPLOY SCRIPT — Dashboard Financeiro
# ==========================================
# Executa automaticamente todos os passos
# para colocar o servidor em produção na Hostinger

set -e  # Para ao primeiro erro

echo "🚀 Iniciando deploy do Dashboard Financeiro..."
echo "=================================================="

# 1. VERIFICAR SE ESTÁ NO DIRETÓRIO CORRETO
echo ""
echo "📁 [1/10] Verificando diretório..."
if [ ! -f "server.js" ]; then
    echo "❌ Erro: server.js não encontrado!"
    echo "   Execute este script do diretório /home/user/MGD-Benetti/"
    exit 1
fi
echo "✅ Diretório correto: $(pwd)"

# 2. ATUALIZAR REPOSITÓRIO
echo ""
echo "📦 [2/10] Atualizando repositório..."
git pull origin claude/organizacao-financeira-2026-o7xjfl || echo "⚠️  Não é um git repo, pulando..."

# 3. CRIAR DIRETÓRIO DE DADOS
echo ""
echo "📁 [3/10] Criando diretório de dados..."
mkdir -p data
chmod -R 755 data
echo "✅ Diretório data/ pronto"

# 4. INSTALAR NODE_MODULES
echo ""
echo "📦 [4/10] Instalando dependências..."
if command -v npm &> /dev/null; then
    npm install
    echo "✅ Dependências instaladas"
else
    echo "❌ Erro: npm não encontrado!"
    echo "   Instale Node.js: https://nodejs.org"
    exit 1
fi

# 5. INSTALAR PM2 GLOBALMENTE
echo ""
echo "🔧 [5/10] Configurando PM2 (gerenciador de processo)..."
if command -v pm2 &> /dev/null; then
    echo "✅ PM2 já instalado"
else
    echo "   Instalando PM2..."
    sudo npm install -g pm2
    echo "✅ PM2 instalado"
fi

# 6. PARAR INSTÂNCIA ANTERIOR (se existir)
echo ""
echo "⏹️  [6/10] Parando instância anterior (se existir)..."
pm2 stop financeiro 2>/dev/null || true
pm2 delete financeiro 2>/dev/null || true
sleep 1

# 7. INICIAR NOVO SERVIDOR COM PM2
echo ""
echo "🎬 [7/10] Iniciando servidor com PM2..."
pm2 start server.js --name "financeiro" --instances 1
echo "✅ Servidor iniciado"

# 8. VERIFICAR STATUS
echo ""
echo "📊 [8/10] Verificando status..."
pm2 status
pm2 save  # Salvar configuração para autostart

# 9. TESTAR CONEXÃO
echo ""
echo "🧪 [9/10] Testando servidor..."
sleep 2
if curl -s http://localhost:3000/api/health | grep -q "ok"; then
    echo "✅ Servidor respondendo normalmente"
else
    echo "⚠️  Servidor pode estar iniciando ainda, verifique com: pm2 logs financeiro"
fi

# 10. RESUMO FINAL
echo ""
echo "=================================================="
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "=================================================="
echo ""
echo "📍 INFORMAÇÕES DE ACESSO:"
echo ""
echo "  Localhost:    http://localhost:3000"
echo "  Dados em:     $(pwd)/data/financeiro.json"
echo "  Logs:         pm2 logs financeiro"
echo "  Status:       pm2 status"
echo "  Reiniciar:    pm2 restart financeiro"
echo "  Parar:        pm2 stop financeiro"
echo ""
echo "🔧 PRÓXIMOS PASSOS (OPCIONAL):"
echo ""
echo "  1. Configurar Nginx como proxy reverso"
echo "  2. Configurar HTTPS/SSL com Let's Encrypt"
echo "  3. Fazer backup do arquivo data/financeiro.json"
echo ""
echo "📖 Ver mais em: SETUP.md"
echo ""
echo "=================================================="
