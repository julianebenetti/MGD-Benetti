# 📘 Guia de Deployment - Dashboard Financeiro VPS Hostinger

## 🎯 Objetivo
Fazer deploy do **Dashboard Financeiro** em um VPS Hostinger próprio com domínio personalizado:
- URL: `https://financeiro.descontoirresistivel.com.br`
- Backend: Express.js + PM2
- Reverse Proxy: Nginx
- SSL: Let's Encrypt

---

## 📋 Pré-Requisitos

- ✅ VPS Hostinger (não hospedagem compartilhada) com **Node.js 16+** e **npm** instalados
- ✅ Domínio apontando para o VPS (`financeiro.descontoirresistivel.com.br`)
- ✅ Acesso SSH ao VPS com permissões de `sudo`
- ✅ Nginx instalado (`sudo apt-get install nginx`)
- ✅ Git instalado (`sudo apt-get install git`)

---

## 🚀 Passo 1: Clonar e Configurar o Projeto

```bash
# Acessar a pasta principal do VPS (ex: /home/seu_usuario)
cd /home/seu_usuario

# Clonar o repositório
git clone https://github.com/julianebenetti/mgd-benetti.git
cd mgd-benetti

# Entrar na pasta do projeto financeiro
cd financeiro

# Instalar dependências
npm install

# Criar pasta de logs se não existir
mkdir -p logs
```

---

## 🔧 Passo 2: Configurar PM2 (Process Manager)

PM2 garante que o Node.js fique sempre rodando e reinicie automaticamente.

```bash
# Instalar PM2 globalmente (se ainda não estiver)
sudo npm install -g pm2

# Iniciar a aplicação com PM2
pm2 start ecosystem.config.js

# Fazer PM2 iniciar com o sistema
pm2 startup
pm2 save

# Verificar status
pm2 status
pm2 logs financeiro
```

**Dica:** Use `pm2 monit` para monitorar CPU/Memória em tempo real.

---

## 🌐 Passo 3: Configurar Nginx (Reverse Proxy)

Nginx recebe requisições na porta 80/443 e encaminha para Node.js (porta 3001).

### 3.1 Criar arquivo de configuração Nginx

```bash
sudo nano /etc/nginx/sites-available/financeiro.descontoirresistivel.com.br
```

Colar o conteúdo abaixo:

```nginx
upstream financeiro_backend {
    server 127.0.0.1:3001;
}

server {
    listen 80;
    server_name financeiro.descontoirresistivel.com.br;

    location / {
        proxy_pass http://financeiro_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://financeiro_backend;
        proxy_cache_valid 200 30d;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 3.2 Ativar o site

```bash
# Criar link simbólico
sudo ln -s /etc/nginx/sites-available/financeiro.descontoirresistivel.com.br \
           /etc/nginx/sites-enabled/

# Testar configuração
sudo nginx -t

# Reiniciar Nginx
sudo systemctl restart nginx
```

---

## 🔒 Passo 4: Configurar SSL com Let's Encrypt (HTTPS)

```bash
# Instalar Certbot
sudo apt-get install certbot python3-certbot-nginx

# Gerar certificado SSL
sudo certbot --nginx -d financeiro.descontoirresistivel.com.br

# Seguir as instruções do Certbot (aceitar ToS, email, etc.)

# Verificar renovação automática
sudo systemctl status certbot.timer

# Teste manual de renovação
sudo certbot renew --dry-run
```

**Resultado:** Nginx agora redireciona automaticamente HTTP → HTTPS

---

## ✅ Passo 5: Testar o Deployment

```bash
# 1. Verificar se Node.js está rodando
pm2 status

# 2. Verificar logs
pm2 logs financeiro

# 3. Health check via API
curl https://financeiro.descontoirresistivel.com.br/api/health

# 4. Testar no navegador
# Abrir: https://financeiro.descontoirresistivel.com.br
```

---

## 📊 Passo 6: Verificar Dados Iniciais

Os dados são salvos em `data/financeiro.json`. Para editar:

```bash
# Via SSH, editar diretamente
nano /home/seu_usuario/mgd-benetti/financeiro/data/financeiro.json

# Ou usar o Dashboard (Aba Editor) para editar via interface web
# https://financeiro.descontoirresistivel.com.br → Aba "⚙️ Editor"
```

---

## 🔄 Passo 7: Atualizar Código Após Mudanças

Se você fizer mudanças no repositório e quiser fazer deploy:

```bash
# Entrar na pasta do projeto
cd /home/seu_usuario/mgd-benetti/financeiro

# Puxar atualizações
git pull origin claude/financial-dashboard-pbj1ts

# Instalar novas dependências (se houver)
npm install

# Reiniciar PM2
pm2 restart financeiro

# Verificar logs
pm2 logs financeiro
```

---

## 🛠️ Troubleshooting

### 502 Bad Gateway (nginx)
```bash
# Verificar se Node.js está rodando
pm2 status

# Se não estiver, reiniciar
pm2 restart financeiro

# Verificar logs de erro
pm2 logs financeiro
```

### Connection Refused (porta 3001)
```bash
# Verificar se a porta 3001 está aberta
netstat -tlnp | grep 3001

# Se não abrir, verificar se Node.js subiu:
pm2 status
pm2 describe financeiro
```

### 404 No JSON (dados não encontrados)
```bash
# Verificar se arquivo existe
ls -la /home/seu_usuario/mgd-benetti/financeiro/data/

# Se não existir, criar:
mkdir -p data
cp financeiro/data/financeiro.json data/
```

### Permissão Negada (Permission Denied)
```bash
# Dar permissão ao usuário
sudo chown -R seu_usuario:seu_usuario /home/seu_usuario/mgd-benetti

# Ou para PM2
sudo chown -R seu_usuario:seu_usuario ~/.pm2
```

### CORS Error (requisições bloqueadas)
- Já está configurado no `server.js` com `cors()` habilitado
- Se ainda tiver problema, verificar logs do Nginx e Node.js

---

## 📈 Monitoramento Contínuo

### PM2 Logs
```bash
# Ver logs em tempo real
pm2 logs financeiro

# Ver logs das últimas 200 linhas
pm2 logs financeiro --lines 200

# Salvar logs em arquivo
pm2 logs financeiro > /tmp/financeiro.log
```

### Monitoramento via PM2 Plus (opcional)
```bash
# Se quiser monitoramento web:
pm2 plus

# Então, acesse: https://web.pm2.io (com sua conta)
```

### Health Check Manual
```bash
# Testar API de health check
curl -I https://financeiro.descontoirresistivel.com.br/api/health

# Esperado: HTTP/1.1 200 OK
```

---

## 🔄 Rotinas Diárias

### Backup de Dados (recomendado)
```bash
# Criar script de backup automático (cron job)
# Editar crontab:
crontab -e

# Adicionar linha (backup diário às 23:00):
0 23 * * * cp /home/seu_usuario/mgd-benetti/financeiro/data/financeiro.json \
                /home/seu_usuario/backups/financeiro-$(date +\%Y\%m\%d).json
```

### Monitorar Disco
```bash
# Verificar espaço em disco
df -h

# Se estiver perto do limite, limpar logs antigos:
pm2 flush
rm -rf /home/seu_usuario/backups/financeiro-*.json  # Manter apenas últimos 30 dias
```

---

## 📝 Endpoints Disponíveis

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/` | Retorna o dashboard HTML |
| GET | `/api/dados` | Retorna JSON financeiro |
| POST | `/api/dados` | Salva dados atualizados |
| GET | `/api/apontamentos` | Lista de notas |
| POST | `/api/apontamentos` | Criar nota |
| POST | `/api/apontamentos/:id/confirmar` | Marcar nota como confirmada |
| DELETE | `/api/apontamentos/:id` | Deletar nota |
| GET | `/api/health` | Health check |

---

## 🎉 Pronto!

Seu dashboard financeiro agora está rodando em:
✅ **https://financeiro.descontoirresistivel.com.br**

Você pode:
1. Ver o dashboard em 5 abas (Resumo, Dívidas, Despesas, Fluxo, Editor)
2. Editar dados via JSON editor (Aba "⚙️ Editor")
3. Exportar/Importar dados JSON
4. Acessar via HTTPS seguro
5. Dados persistem em arquivo JSON

---

## 📞 Suporte

Se tiver problemas:
1. Verificar `pm2 logs financeiro`
2. Testar `curl -I https://financeiro.descontoirresistivel.com.br/api/health`
3. Verificar permissões de arquivo: `ls -la /home/seu_usuario/mgd-benetti/financeiro/data/`
4. Reiniciar tudo: `pm2 restart financeiro && sudo systemctl restart nginx`

---

**Versão:** 1.0.0  
**Atualizado:** 2026-08-11  
**Próximas melhorias:** Banco de dados PostgreSQL, Autenticação, Histórico de transações
