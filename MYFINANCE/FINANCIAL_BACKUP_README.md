# 📊 Gestão Financeira - Restauração de Backup

Este documento descreve a restauração e o novo sistema de gestão financeira criado a partir do seu backup.

## 📦 O que foi restaurado

### Dados do Backup
- **20 Centros de Classificação** (Moradia, Educação, Saúde, Impostos, Cultura e Lazer, etc)
- **536 Categorias** organizadas hierarquicamente
- **Estrutura completa** do sistema antigo de gestão financeira

### Arquivo Principal
- `GestaoFinanceira.html` - Dashboard interativo para gerenciar suas finanças

## 🚀 Como usar

### 1. Abrir o Dashboard
```bash
# Localmente (para testes)
open GestaoFinanceira.html
# ou
firefox GestaoFinanceira.html
```

### 2. Recursos Disponíveis

#### 📊 Dashboard
- Resumo de receitas e despesas
- Gráficos de distribuição por categoria
- Análise de tendências

#### 💰 Transações
- Adicionar novas receitas e despesas
- Selecionar categoria (536 opções)
- Registrar data e observações
- Histórico de transações

#### 📂 Categorias
- Visualizar todas as categorias
- Filtrar por nome
- Ver frequência de uso
- Identificar se é despesa ou receita

#### 📈 Relatórios
- Total de receitas e despesas
- Saldo geral
- Comparativo receitas vs despesas
- Tendência de gastos

## 🔧 Dados Técnicos

### Arquivos Criados
- `financial-backup.json` - Backup consolidado em JSON
- `categories-parsed.json` - 536 categorias estruturadas
- `backup-restore.sql` - SQL para importação em banco de dados
- `categories-insert.sql` - SQL para inserção de categorias

### Scripts de Processamento
- `scripts/restore-financial-backup.js` - Parser XML original
- `scripts/parse-categories.js` - Extração de categorias
- `scripts/consolidate-backup.js` - Consolidação do backup

## 💾 Armazenamento de Dados

### Atual (Navegador)
As transações são armazenadas em **localStorage** do navegador:
- Funciona offline
- Dados persistem entre sessões
- Limite: ~5MB por domínio

### Futuro (Supabase)
Para sincronizar com banco de dados:
1. Configure Supabase
2. Importe o SQL: `backup-restore.sql`
3. Configure autenticação
4. Sincronize transações do localStorage com servidor

## 🎨 Categorias Principais

As 20 categorias principais do seu backup:

| Categoria | Tipo | Uso Count |
|-----------|------|-----------|
| Moradia | Despesa/Receita | 10.810 |
| Aplicações | Despesa/Receita | 1.403 |
| Financeiras | Despesa/Receita | 2.446 |
| Supérfluas | Despesa/Receita | 644 |
| Saúde | Despesa/Receita | 1.698 |
| Educação | Despesa/Receita | 1.318 |
| Impostos | Despesa/Receita | 1.039 |
| Seguros | Despesa/Receita | 246 |
| Cultura e Lazer | Despesa/Receita | 3.238 |
| Pessoais | Despesa/Receita | 6.404 |
| Rendas de Trabalho | Receita | 3.183 |
| Transferência | Despesa/Receita | 1.491 |
| Rendas de Capital | Receita | 252 |
| Cartão de Crédito | Despesa/Receita | 1.091 |
| EROC - Igreja de Cristo | Receita | 53 |
| Depósito/Saque | Despesa/Receita | 123 |
| Empréstimo | Despesa/Receita | 3.151 |
| Rendas de Vendas | Receita | 679 |
| Despesas de Trabalho | Despesa | 488 |
| CashBack | Despesa/Receita | 116 |

## 📱 Publicar no VPS (Hostinger)

### Passo 1: Copiar para o VPS
```bash
scp GestaoFinanceira.html financial-backup.json seu_usuario@seu_ip:/path/to/vps/html/
```

### Passo 2: Acessar via Navegador
```
https://seu-dominio.com/GestaoFinanceira.html
```

## 🔐 Segurança

### Informações Sensíveis
- ⚠️ O arquivo `financial-backup.json` contém sua estrutura de categorias
- 💾 As transações são armazenadas localmente no navegador
- 🔒 Não há transmissão de dados para servidores por padrão

### Recomendações
1. Faça backup regular de suas transações
2. Exporte dados periodicamente em JSON
3. Se usar banco de dados, implemente autenticação
4. Considere HTTPS para acesso remoto

## 📊 Próximos Passos

### Melhorias Sugeridas
1. **Exportar/Importar** - Adicionar botão de exportação CSV
2. **Sincronização** - Conectar com Supabase
3. **Budgets** - Criar limites de gastos por categoria
4. **Alertas** - Notificar quando exceder limite
5. **Gráficos Avançados** - Análise temporal mais detalhada
6. **Mobile** - Otimizar para dispositivos móveis
7. **Backup Automático** - Sincronizar dados regularmente

## 📞 Suporte

Se precisar de ajustes:
- Modifique `GestaoFinanceira.html` conforme necessário
- Adicione novas categorias em `financial-backup.json`
- Integre com Supabase para sincronização

---

**Backup restaurado em:** 2026-08-23  
**Total de categorias:** 536  
**Dashboard versão:** 1.0
