# Dados fora do escopo atual

A dashboard cobre **somente 2026** (`ANO_DASHBOARD` em `public/index.html`).
O que está aqui é material já recebido que ainda não pode ser importado sem
distorcer a leitura da tela.

## `holerites-2025-juliane.xlsx`

Recebido em 23/08/2026. Traz a folha da Elektro de 2025 inteira, consolidada:

| | |
|---|---|
| comprovantes | 14 (jan a dez, incluindo PLR, adiantamento de PLR, férias e 13º) |
| proventos brutos | R$ 93.238,67 |
| descontos | R$ 25.042,28 |
| líquido depositado | R$ 68.196,39 |

Tem quatro abas: resumo anual, detalhe por mês rubrica a rubrica, valores
consolidados para a declaração do IRPF e um quadro de FGTS e deduções.

**Por que não foi importado:** não existe nenhuma fatura de cartão de 2025.
Importar só a receita faria 2025 aparecer com R$ 68 mil de sobra que nunca
existiu — exatamente o tipo de número incompleto que a regra de ouro do projeto
proíbe.

**O que destrava:** as faturas do cartão de 2025. Com elas, abre-se o escopo
para os dois anos e a comparação ano a ano passa a significar alguma coisa.

Rubricas de 2025 que ainda não existem em `scripts/importar-holerites.js` e
precisarão ser cadastradas antes da importação: `205N` e `20BN` (auxílio-creche
em duas linhas, uma delas com tributação diferente da `206N` usada em 2026).
