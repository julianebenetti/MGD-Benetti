#!/bin/bash

# Gestão Financeira - Deploy para VPS Hostinger
# Este script copia os arquivos necessários para o seu VPS

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Gestão Financeira - Deploy para VPS${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Verificar se os arquivos existem
if [ ! -f "GestaoFinanceira.html" ]; then
  echo -e "${RED}❌ Erro: GestaoFinanceira.html não encontrado${NC}"
  exit 1
fi

if [ ! -f "financial-backup.json" ]; then
  echo -e "${RED}❌ Erro: financial-backup.json não encontrado${NC}"
  exit 1
fi

echo -e "${YELLOW}⚙️  Configuração do Deploy${NC}\n"

# Pedir dados do usuário se não fornecidos
VPS_HOST=${VPS_HOST:-}
VPS_USER=${VPS_USER:-}
VPS_PATH=${VPS_PATH:-}

if [ -z "$VPS_HOST" ]; then
  read -p "IP ou domínio do VPS: " VPS_HOST
fi

if [ -z "$VPS_USER" ]; then
  read -p "Usuário SSH (ex: root): " VPS_USER
fi

if [ -z "$VPS_PATH" ]; then
  read -p "Caminho no VPS (ex: /home/seu_usuario/public_html): " VPS_PATH
fi

# Confirmar dados
echo -e "\n${YELLOW}Dados do Deploy:${NC}"
echo "  Host: $VPS_HOST"
echo "  Usuário: $VPS_USER"
echo "  Caminho: $VPS_PATH"
echo ""

read -p "Continuar? (s/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
  echo -e "${RED}Deploy cancelado${NC}"
  exit 1
fi

echo -e "\n${BLUE}📤 Iniciando upload...${NC}\n"

# Criar diretório no VPS se não existir
echo "Criando diretório no VPS..."
ssh "$VPS_USER@$VPS_HOST" "mkdir -p $VPS_PATH" 2>/dev/null || true

# Upload dos arquivos principais
echo "Copiando GestaoFinanceira.html..."
scp -q "GestaoFinanceira.html" "$VPS_USER@$VPS_HOST:$VPS_PATH/"

echo "Copiando financial-backup.json..."
scp -q "financial-backup.json" "$VPS_USER@$VPS_HOST:$VPS_PATH/"

echo "Copiando categories-parsed.json..."
scp -q "categories-parsed.json" "$VPS_USER@$VPS_HOST:$VPS_PATH/" 2>/dev/null || true

echo "Copiando FINANCIAL_BACKUP_README.md..."
scp -q "FINANCIAL_BACKUP_README.md" "$VPS_USER@$VPS_HOST:$VPS_PATH/" 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}\n"

echo -e "${BLUE}📍 Próximas ações:${NC}"
echo -e "  1. Acesse: ${YELLOW}http://$VPS_HOST$VPS_PATH/GestaoFinanceira.html${NC}"
echo -e "  2. Configure seu HTTPS/SSL se necessário"
echo -e "  3. Faça backup regular de suas transações"
echo ""

# Salvar configuração
if [ -f ".deploy-config" ]; then
  read -p "Salvar configuração para próximos deploys? (s/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo "VPS_HOST=$VPS_HOST" > .deploy-config
    echo "VPS_USER=$VPS_USER" >> .deploy-config
    echo "VPS_PATH=$VPS_PATH" >> .deploy-config
    echo -e "${GREEN}✅ Configuração salva em .deploy-config${NC}\n"
  fi
fi

echo -e "${GREEN}🎉 Deploy finalizado!${NC}"
