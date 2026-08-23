# 💰 MYFINANCE - Gestão Financeira

**Seu sistema de controle financeiro restaurado e pronto para usar!**

---

## 🎯 Arquivos Principais

### 📊 Dashboard
- **`GestaoFinanceira.html`** ← **ABRA ESTE ARQUIVO NO NAVEGADOR** 🚀

### 🏠 Página Inicial
- **`index.html`** - Apresentação do projeto (opcional)

### 📚 Documentação
- **`BACKUP_SUMMARY.md`** - Resumo executivo
- **`FINANCIAL_BACKUP_README.md`** - Guia completo de uso

### 💾 Dados
- **`financial-backup.json`** - Backup consolidado com 536 categorias
- **`categories-parsed.json`** - Categorias em formato JSON
- **`backup-restore.sql`** - SQL para importação em banco de dados
- **`categories-insert.sql`** - SQL de inserção de categorias

### 🔧 Scripts
- **`scripts/deploy-to-vps.sh`** - Deploy automático para VPS Hostinger
- **`scripts/parse-categories.js`** - Parser de categorias
- **`scripts/consolidate-backup.js`** - Consolidação de dados

---

## 🚀 Como Usar

### **Passo 1: Abrir o Dashboard** (⭐ COMECE AQUI)

#### No Windows/Explorador de Arquivos:
1. Navegue até: `MGD-Benetti > MYFINANCE`
2. Clique duplo em **`GestaoFinanceira.html`**
3. Pronto! Dashboard abre no navegador 🎉

#### Ou via navegador (copie na barra de endereço):
```
file:///C:/Users/[seu_usuario]/MGD-Benetti/MYFINANCE/GestaoFinanceira.html
```

---

## ✨ O Que Você Tem

### 📊 Aba Dashboard
- Resumo de receitas e despesas
- Gráficos de distribuição
- Análise de saldo

### 💰 Aba Transações
- Adicionar receitas/despesas
- 536 categorias disponíveis
- Histórico de movimentações

### 📂 Aba Categorias
- Explorar todas as 536 categorias
- Filtro de busca
- Ver frequência de uso

### 📈 Aba Relatórios
- Total de receitas/despesas
- Gráficos comparativos
- Tendência de gastos

---

## 💾 Armazenamento

✅ **Dados salvos localmente** no navegador (localStorage)  
✅ **Funciona offline** - sem necessidade de internet  
✅ **Privado** - seus dados não saem do seu computador  
✅ **Automático** - tudo é salvo enquanto você usa  

---

## 📱 Publicar no VPS Hostinger

Para colocar online no seu VPS:

```bash
bash scripts/deploy-to-vps.sh
```

O script pedirá:
- IP/domínio do VPS
- Usuário SSH
- Caminho no servidor

---

## 🎨 Categorias Disponíveis

Seu backup restaurado inclui **536 categorias** organizadas em grupos como:

- 🏠 Moradia
- 🍽️ Alimentação
- 📚 Educação
- 🏥 Saúde
- 🎬 Cultura e Lazer
- 👨‍👩‍👧 Despesas com Filhos
- 💼 Despesas de Trabalho
- 💰 Financeiras
- E muitas mais...

---

## 🔐 Segurança

- ✅ Sem servidor necessário
- ✅ Dados locais (nunca enviados)
- ✅ HTTPS recomendado para acesso remoto
- ✅ Fácil fazer backup (JSON estruturado)

---

## 📞 Próximos Passos

1. **Abra o Dashboard** → `GestaoFinanceira.html`
2. **Explore as categorias** → 536 opções disponíveis
3. **Adicione transações** → Comece a rastrear
4. **Configure backup** → Exporte dados periodicamente
5. **Publique online** → Use `deploy-to-vps.sh`

---

**Desenvolvido especialmente para você! 💝**

Qualquer dúvida, consulte:
- `FINANCIAL_BACKUP_README.md` - Documentação completa
- `BACKUP_SUMMARY.md` - Resumo do que foi restaurado
