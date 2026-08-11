# 🚀 DEPLOY — Dashboard Financeiro Dinâmico

> **Status:** ✅ Em Produção  
> **URL:** https://financeiro.descontoirresistivel.com.br  
> **Branch:** `claude/organizacao-financeira-2026-o7xjfl`

---

## 📦 Arquivos do Projeto

```
MGD-Benetti/
├── server.js                 # Backend Express (API REST)
├── package.json              # Dependências Node.js
├── public/
│   └── index.html            # Frontend dinâmico (5 abas)
├── deploy.sh                 # Script de deploy automático
├── nginx-config.conf         # Configuração Nginx (proxy reverso)
├── data/
│   └── financeiro.json       # Dados persistidos (criado ao rodar)
├── SETUP.md                  # Documentação técnica completa
└── DEPLOY.md                 # Este arquivo
```

---

## 🎯 Deploy Rápido (3 linhas)

```bash
cd /home/user/MGD-Benetti
bash deploy.sh
```

**Resultado:** Dashboard rodando em `http://seu-ip:3000` ✅

---

## 🌐 Deploy Completo com Nginx

```bash
# 1. Executar deploy
bash deploy.sh

# 2. Configurar Nginx
sudo cp nginx-config.conf /etc/nginx/sites-available/financeiro.conf
sudo ln -s /etc/nginx/sites-available/financeiro.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Resultado:** Dashboard em `https://financeiro.seu-dominio.com` ✅

---

## 📊 O Dashboard Oferece

### 📋 Aba "Resumo"
- Salário Juliane
- Renda Hugo (líquido)
- Saldo atual da conta
- Total de dívidas
- Fluxo rápido (Entradas vs Saídas vs Resultado)

### 🏦 Aba "Dívidas"
- Consignados (folha)
- Consignado conta corrente
- Empréstimo familiar (Cenira)
- Mercado Pago
- Cartões (Black, Azul, Infinite)

### 💸 Aba "Despesas"
- Lista de 12 despesas fixas mensais
- Valores e dias de vencimento
- Total automático

### 📈 Aba "Fluxo"
- Entradas mensais (Juliane + Hugo)
- Saídas fixas
- Resultado mensal (superávit/déficit)

### ⚙️ Aba "Editor"
- ✏️ Editar dados diretamente
- 💾 Exportar em JSON
- 🔄 Sincronizar com servidor

---

## 🔧 Comandos Úteis

### Ver logs
```bash
pm2 logs financeiro
```

### Ver status
```bash
pm2 status
```

### Testar API
```bash
curl https://financeiro.descontoirresistivel.com.br/api/health
```

### Reiniciar servidor
```bash
pm2 restart financeiro
```

### Ver dados salvos
```bash
cat data/financeiro.json
```

---

## 🔐 Segurança Implementada

✅ API CORS habilitada  
✅ Express + Helmet (headers de segurança)  
✅ Dados em arquivo JSON (sem banco expostos)  
✅ HTTPS ativado (domínio com SSL)  
✅ PM2 com autostart (reinicia automático)  

---

## 📱 Acessar

| Ambiente | URL |
|----------|-----|
| Local | `http://localhost:3000` |
| IP VPS | `http://seu-ip:3000` |
| Domínio (HTTPS) | `https://financeiro.descontoirresistivel.com.br` |

---

## 🐛 Troubleshooting

### Erro: "Port 3000 already in use"
```bash
lsof -i :3000
kill -9 <PID>
```

### Erro: "Cannot find module"
```bash
npm install
```

### Nginx retorna 502
```bash
pm2 status
pm2 restart financeiro
sudo systemctl restart nginx
```

### Dados não salvam
```bash
chmod -R 755 /home/user/MGD-Benetti/data
```

---

## 📚 Documentação Completa

- **[SETUP.md](./SETUP.md)** — Guia técnico detalhado
- **[nginx-config.conf](./nginx-config.conf)** — Configuração Nginx pronta
- **[deploy.sh](./deploy.sh)** — Script automático com comentários

---

## ✨ Funcionalidades

| Recurso | Status |
|---------|--------|
| Backend Express | ✅ |
| API REST | ✅ |
| Frontend dinâmico | ✅ |
| Edição de dados | ✅ |
| Persistência JSON | ✅ |
| PM2 (autostart) | ✅ |
| Nginx (proxy) | ✅ |
| HTTPS/SSL | ✅ |
| Exportar JSON | ✅ |
| Sincronização | ✅ |

---

## 🎯 Próximas Melhorias (Fase 2)

- [ ] Autenticação (senha/JWT)
- [ ] Backup automático
- [ ] Banco de dados (MySQL/PostgreSQL)
- [ ] Notificações por email
- [ ] Gráficos avançados (Chart.js)
- [ ] App mobile
- [ ] Dark/Light mode persistente

---

## 📞 Status Atual

**✅ ATIVO E FUNCIONANDO**

- Dashboard online: https://financeiro.descontoirresistivel.com.br
- Servidor: PM2 (rodapermanente)
- Dados: Salvos em `/data/financeiro.json`
- Logs: `pm2 logs financeiro`

---

## 💡 Dicas

✅ Sempre use `bash deploy.sh` para atualizar  
✅ Faça backup de `data/financeiro.json` regularmente  
✅ Monitore com `pm2 logs` em caso de erros  
✅ Use HTTPS em produção (SSL está ativo)  
✅ Versione tudo no Git, não edite direto no servidor  

---

## 🚀 Quick Start

```bash
# SSH no VPS
ssh seu-usuario@seu-ip

# Ir para o projeto
cd /home/user/MGD-Benetti

# Deploy automático
bash deploy.sh

# Pronto! 🎉
# Acesse em: https://financeiro.descontoirresistivel.com.br
```

---

**Desenvolvido com ❤️ para organização financeira de Juliane Benetti — 2026**
