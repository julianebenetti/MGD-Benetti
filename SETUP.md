# Setup — Dashboard Financeiro Dinâmico

## 📋 Pré-requisitos
- Node.js 14+ instalado no VPS da Hostinger
- Acesso SSH ao VPS
- Porta disponível (usaremos 3000, mas pode ser customizada)

## 🚀 Instalação Rápida

### 1. Instalar dependências
```bash
cd /home/user/MGD-Benetti
npm install
```

Isso vai instalar:
- **Express** (servidor web)
- **CORS** (para requisições do frontend)

### 2. Iniciar o servidor
```bash
npm start
```

Você verá:
```
💰 Servidor financeiro rodando em http://localhost:3000
📁 Dados armazenados em: /home/user/MGD-Benetti/data/financeiro.json
```

### 3. Acessar no navegador
- **Localmente**: http://localhost:3000
- **Remotamente** (se VPS estiver acessível): http://seu-ip-vps:3000

---

## 📁 Estrutura de Arquivos

```
MGD-Benetti/
├── server.js              # Backend Node.js + Express
├── package.json           # Dependências
├── public/
│   └── index.html         # Frontend dinâmico
├── data/
│   └── financeiro.json    # Dados (criado automaticamente)
└── SETUP.md               # Este arquivo
```

---

## 🔧 Configuração para Produção (Hostinger)

### Opção 1: Usar PM2 (Recomendado)

1. **Instalar PM2 globalmente:**
   ```bash
   npm install -g pm2
   ```

2. **Iniciar com PM2:**
   ```bash
   pm2 start server.js --name "financeiro"
   ```

3. **Ver logs:**
   ```bash
   pm2 logs financeiro
   ```

4. **Fazer PM2 iniciar ao reboot:**
   ```bash
   pm2 startup
   pm2 save
   ```

### Opção 2: Usar Nginx como Proxy Reverso

Se você já tem Nginx rodando (para AfiliDash), pode proxear o financeiro:

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location /financeiro {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Depois acesse: `http://seu-dominio.com/financeiro`

---

## 📊 Usando o Dashboard

### Seções:

1. **📊 Resumo** — Visão geral de salários, saldo, dívida total e fluxo rápido
2. **🏦 Dívidas** — Detalhamento de todos os empréstimos e cartões
3. **💸 Despesas** — Lista de despesas fixas mensais
4. **📈 Fluxo** — Análise entradas vs saídas
5. **⚙️ Editor** — Painel para editar dados e sincronizar

### Editando Dados:

- Clique em **"Editar"** nos cards para atualizar valores
- Os dados são salvos **automaticamente** no servidor
- Você pode **exportar JSON** para backup

---

## 💾 API Endpoints

Se quiser integrar com outras ferramentas:

### GET `/api/dados`
Retorna todos os dados

```bash
curl http://localhost:3000/api/dados
```

### POST `/api/dados`
Salva dados completos

```bash
curl -X POST http://localhost:3000/api/dados \
  -H "Content-Type: application/json" \
  -d @financeiro.json
```

### PUT `/api/dados/contas`
Atualiza apenas uma seção (ex: contas)

```bash
curl -X PUT http://localhost:3000/api/dados/contas \
  -H "Content-Type: application/json" \
  -d '{"saldoAtual": 10000}'
```

### GET `/api/health`
Health check

```bash
curl http://localhost:3000/api/health
```

---

## 🔒 Segurança

### Recomendações:

1. **Adicionar autenticação** (se necessário):
   - Implementar JWT ou sessões
   - Proteger endpoints sensíveis

2. **HTTPS:**
   - Use certificado SSL (Let's Encrypt)
   - Configure no Nginx/Apache

3. **Backup automático:**
   - Faça backup do `data/financeiro.json` regularmente
   - Versione no Git

---

## 🐛 Troubleshooting

### "Port 3000 already in use"
```bash
# Mude a porta em server.js
const PORT = 3001; // ou outra porta disponível
```

### "Cannot find module 'express'"
```bash
npm install
```

### "Permission denied ao salvar dados"
```bash
# Verifique permissões
chmod -R 755 /home/user/MGD-Benetti/data
```

---

## 🚢 Deploy Completo (Passo a Passo)

```bash
# 1. SSH no VPS
ssh seu-usuario@seu-vps

# 2. Entrar no diretório
cd /home/user/MGD-Benetti

# 3. Instalar dependências
npm install

# 4. Iniciar com PM2
pm2 start server.js --name "financeiro"

# 5. Salvar configuração PM2
pm2 save

# 6. Testar
curl http://localhost:3000/api/health

# 7. Configurar Nginx (se necessário)
# Editar /etc/nginx/sites-available/seu-site
sudo systemctl reload nginx
```

---

## 📱 Acessar Remotamente

Se o VPS tem IP público (ex: 123.45.67.89):

```
http://123.45.67.89:3000
```

Ou com domínio (via DNS):

```
http://financeiro.seu-dominio.com
```

---

## 💡 Próximas Melhorias

- [ ] Adicionar autenticação
- [ ] Sincronizar com Google Sheets
- [ ] Notificações de vencimento de contas
- [ ] Gráficos mais avançados (Chart.js)
- [ ] App mobile
- [ ] Integração com Supabase

---

## 📞 Suporte

Em caso de dúvidas, verifique:
- Logs: `pm2 logs financeiro`
- Status: `pm2 status`
- Arquivo de dados: `cat data/financeiro.json`
