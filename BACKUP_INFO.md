# 📦 Informações de Backup - Dashboard Financeiro

## ✅ Backups Criados

### 1. Git Repository (Principal)
- **Localização:** GitHub - `julianebenetti/mgd-benetti`
- **Branch:** `claude/financial-dashboard-pbj1ts`
- **Status:** ✅ Commits automáticos após cada mudança
- **Acesso:** https://github.com/julianebenetti/mgd-benetti

### 2. Backup Compactado Local
- **Arquivo:** `MGD-Benetti-backup-20260812-014227.tar.gz`
- **Tamanho:** 9.2 MB
- **Localização:** `/tmp/claude-0/-home-user-MGD-Benetti/30a0a797-34c2-5ab7-8b83-56ad8b2a637d/scratchpad/`
- **Inclui:** Projeto completo + node_modules + dados
- **Data:** 12 de Agosto de 2026, 01:42 UTC

### 3. Backup na VPS Hostinger
- **Localização:** `/root/backups/MGD-Benetti-backup-*.tar.gz`
- **Como criar:**
```bash
ssh root@179.98.96.133
mkdir -p ~/backups
cd ~/mgd-benetti
tar -czf ~/backups/MGD-Benetti-backup-$(date +%Y%m%d-%H%M%S).tar.gz .
```

---

## 📋 Conteúdo do Backup

```
MGD-Benetti/
├── financeiro/                 # Projeto principal do dashboard
│   ├── server.js              # Servidor Node.js
│   ├── package.json           # Dependências
│   ├── ecosystem.config.js    # Configuração PM2
│   ├── public/                # Frontend (HTML, CSS, JS)
│   │   └── index.html         # Dashboard SPA
│   ├── data/                  # Dados JSON
│   │   ├── financeiro.json    # Dados financeiros
│   │   └── apontamentos.json  # Apontamentos/notas
│   ├── node_modules/          # Dependências Node
│   ├── logs/                  # Logs da aplicação
│   ├── DEPLOY_VPSFINANCEIRO.md
│   ├── FLUXO_ALIMENTACAO_DADOS.md
│   └── README.md
├── CLAUDE.md                  # Instruções do projeto
├── .gitignore
└── [outros arquivos]
```

---

## 🔐 Como Restaurar do Backup

### Na VPS (Quick Restore)
```bash
cd ~
tar -xzf backups/MGD-Benetti-backup-*.tar.gz
cd mgd-benetti/financeiro
npm install
pm2 start ecosystem.config.js
```

### Localmente
```bash
tar -xzf MGD-Benetti-backup-*.tar.gz
cd MGD-Benetti/financeiro
npm install
npm start
```

---

## 📊 Dados Críticos Protegidos

✅ **Estrutura do Dashboard**
- 6 abas funcionais
- API REST completa
- Frontend SPA responsivo

✅ **Dados Financeiros**
- historico_black_card (12 meses)
- Pessoas (Juliane, Hugo)
- Dívidas (6 contas)
- Despesas (categorias)
- Fluxo mensal
- Regras de ouro

✅ **Configurações**
- PM2 ecosystem.config.js
- Nginx reverse proxy (DEPLOY_VPSFINANCEIRO.md)
- SSL/TLS Let's Encrypt
- CORS e segurança

✅ **Documentação**
- Guia de deployment
- Fluxo de alimentação de dados
- Scripts de diagnóstico

---

## 🔄 Política de Backups Recomendada

### Frequência
- ✅ **Automático via Git:** Cada commit
- ✅ **Manual:** Antes de mudanças grandes
- ✅ **VPS:** Semanal (adicione ao cron)

### Rotina Sugerida (Adicionar ao crontab da VPS)
```bash
# Fazer backup semanal toda segunda-feira às 2AM
0 2 * * 1 tar -czf ~/backups/MGD-Benetti-backup-$(date +\%Y\%m\%d).tar.gz -C ~ mgd-benetti/

# Limpar backups com mais de 30 dias
0 3 * * 1 find ~/backups -name "*.tar.gz" -mtime +30 -delete
```

---

## 📌 Últimas Ações Registradas

- ✅ **12/08/2026 01:42** - Backup completo criado
- ✅ **12/08/2026 01:30** - Dashboard 100% operacional em produção
- ✅ **12/08/2026 01:15** - PM2 iniciado com sucesso
- ✅ **12/08/2026 01:00** - Servidor Node.js validado
- ✅ **12/08/2026 00:45** - Firewall e porta 3001 configuradas
- ✅ **11/08/2026** - Branch `claude/financial-dashboard-pbj1ts` criada

---

## 🆘 Recuperação de Emergência

Se algo der errado:

1. **Conectar via SSH:**
```bash
ssh root@179.98.96.133
```

2. **Parar aplicação:**
```bash
pm2 stop financeiro
```

3. **Restaurar do backup:**
```bash
cd ~
rm -rf mgd-benetti
tar -xzf backups/MGD-Benetti-backup-*.tar.gz
cd mgd-benetti/financeiro
npm install
pm2 start ecosystem.config.js
```

4. **Verificar status:**
```bash
pm2 status
curl http://localhost:3001/api/health
```

---

## 📞 Suporte

- **Dashboard:** https://financeiro.descontoirresistivel.com.br
- **VPS IP:** 179.98.96.133:3001
- **Local:** http://localhost:3001
- **Logs:** `pm2 logs financeiro`
- **Status:** `pm2 status`

---

**Backup criado em:** 12 de Agosto de 2026, 01:42 UTC  
**Próximo backup recomendado:** Após mudanças no fluxo de dados
