# 💰 Dashboard Financeiro

Dashboard financeiro completo para Juliane e Hugo com 5 abas de visualização e editor JSON.

## 🚀 Quick Start (Desenvolvimento)

```bash
cd financeiro
npm install
npm start
# Acessa em: http://localhost:3001
```

## 📊 Características

✅ **5 Abas Principais:**
- 📊 **Resumo** — KPIs, gráfico Black Card, timeline de alívios
- 🏦 **Dívidas** — 6 contas com status e parcelas
- 💸 **Despesas** — Categorização estratégica (Necessidades/Avaliar/Parar)
- 📈 **Fluxo** — Ciclo mensal, alertas, cenários futuros
- ⚙️ **Editor** — JSON interativo com import/export

✅ **Backend REST:**
- GET/POST `/api/dados` — Sincronizar dados
- CRUD `/api/apontamentos` — Notas e alertas
- GET `/api/health` — Health check

✅ **Design:**
- Dark theme nativo
- Responsivo (mobile/desktop)
- Vanilla JS (sem dependências frontend)
- ~1000 linhas HTML + CSS + JS

## 📁 Estrutura

```
financeiro/
├── server.js              # Express API
├── public/
│   └── index.html         # Dashboard (5 abas)
├── data/
│   ├── financeiro.json    # Dados financeiros
│   └── apontamentos.json  # Notas/apontamentos
├── ecosystem.config.js    # PM2 config
├── DEPLOY_VPSFINANCEIRO.md # Guia de deployment
└── package.json
```

## 🚀 Deployment VPS

Veja **[DEPLOY_VPSFINANCEIRO.md](./DEPLOY_VPSFINANCEIRO.md)** para:
- Instalar Node.js, npm, PM2
- Configurar Nginx reverse proxy
- Setup SSL com Let's Encrypt
- Troubleshooting

**URL Production:** `https://financeiro.descontoirresistivel.com.br`

## 🔧 PM2 (Production)

```bash
# Iniciar
pm2 start ecosystem.config.js

# Status
pm2 status

# Logs
pm2 logs financeiro

# Monitor
pm2 monit
```

## 📝 Dados

Editar via:
1. **Interface:** Aba "⚙️ Editor" → JSON editor → Salvar
2. **Terminal:** `nano data/financeiro.json`

Estrutura:
- `pessoas` — Juliane, Hugo (salários/rendas)
- `dividas` — 6 contas (Consignados, Cenira, Black Card, MP)
- `despesas` — 3 categorias (Necessidades/Avaliar/Parar)
- `cenarios_futuros` — Projeções (dez/26, fev/27, etc)
- `regras_ouro` — Constraints principais

## 🎯 Próximas Evoluções

- [ ] Banco de dados (PostgreSQL/Supabase)
- [ ] Autenticação (Juliane + Hugo)
- [ ] Histórico de transações
- [ ] Notificações (email/SMS)
- [ ] Integração bancária
- [ ] Relatórios PDF

---

**Versão:** 1.0.0  
**Criado:** 2026-08-11  
**Maintainer:** Claude Code
