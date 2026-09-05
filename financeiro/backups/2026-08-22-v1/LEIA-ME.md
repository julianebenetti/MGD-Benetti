# Backup v1 — Dashboard Financeira (22/08/2026)

Ponto de restauração criado **antes** da reestruturação contábil da dashboard.

## O que está guardado aqui

| Arquivo | O que é |
|---|---|
| `financeiro.json` | Dados principais — 629 transações, total R$ 40.086,47 |
| `index.html` | Dashboard completa (versão com 12 abas) |
| `server.js` | Backend Express |
| `classificacoes.json` | Regras de classificação |
| `configuracoes.json` | Pessoas, tipos de despesa, config de abas |
| `cargas.json` | Histórico de importações |
| `totais_esperados.json` | Totais para reconciliação de faturas |
| `apontamentos.json` | Anotações |

## Integridade verificada

```
Transações: 629
Total:      R$ 40.086,47
MD5:        cca775d0ebe74deeb7184ec8b020a36b (financeiro.json)
```

## Como restaurar

### Opção 1 — Restaurar só os dados (mais comum)

```bash
cd /root/mgd-benetti/financeiro
cp backups/2026-08-22-v1/financeiro.json data/financeiro.json
pm2 restart financeiro
```

### Opção 2 — Restaurar dashboard + dados

```bash
cd /root/mgd-benetti/financeiro
cp backups/2026-08-22-v1/index.html public/index.html
cp backups/2026-08-22-v1/*.json data/
rm -f data/LEIA-ME.md
pm2 restart financeiro
```

Depois: Ctrl+Shift+R no navegador para limpar o cache.

### Opção 3 — Voltar o repositório inteiro para este ponto

```bash
cd /root/mgd-benetti
git checkout v1-dashboard-estavel
```

Ou usar a branch de backup:

```bash
git checkout backup/dashboard-antes-reestruturacao
```

## Referências no Git

- **Tag:** `v1-dashboard-estavel`
- **Branch:** `backup/dashboard-antes-reestruturacao`
- **Commit:** `de285ce`

## Estado da dashboard neste ponto

### Funcionando
- 629 transações de cartão de crédito Itaú carregadas (Ago/25 a Mai/26)
- Todas marcadas corretamente como `saida`
- Sincronização entre abas corrigida (`renderizarTodas` chama todas as abas)
- Abas Resumo, Fluxo, Despesas e Dashboard Contábil exibindo valores

### Limitações conhecidas
- **Nenhuma receita cadastrada** — por isso o saldo aparece como -R$ 40.086,47
- Não há despesas fixas fora do cartão (aluguel, luz, água, etc.)
- Dívidas e investimentos vazios
- Aba Fluxo não tem filtro por mês de vencimento da fatura
- Resumo por Categoria sem ordenação alfabética nem quebra mensal
- Cálculos com meses fixos (Jan–Mai) hardcoded em vários pontos
