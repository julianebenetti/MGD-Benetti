# Contexto do projeto (MGD-Benetti)

## Nomenclatura
- O dashboard principal se chama **AfiliDash** — não usar mais o nome "BenettiDash".
  `BenettiDash.html` é um arquivo antigo/legado no repositório; não é mais usado.

## Hospedagem
- A AfiliDash roda no **VPS da Hostinger** (não é hospedagem compartilhada via hPanel
  File Manager comum — é um VPS). É essa a única hospedagem em uso atualmente.
- `garimpo-shopee.html` (página standalone do Garimpo de Produtos, que conecta no
  mesmo Supabase da aba Garimpo da AfiliDash) precisa ser publicado nesse mesmo VPS,
  não em hospedagem compartilhada separada.

## Dashboard Financeira (`financeiro/`)

Controle das contas **pessoais** da Juliane e do Hugo. Não tem relação nenhuma
com Shopee, afiliados ou e-commerce — se surgir essa mistura, é engano.

### Estrutura
- 5 abas: Painel, Lançamentos, Para Onde Vai, Cartão & Faturas, Dívidas & Patrimônio.
  Importar / Configurações / Editor ficam no menu **⚡ Ferramentas**.
- Escopo: **somente 2026** (`ANO_DASHBOARD` em `public/index.html`).
- O mês usado em tudo é `mes_vencimento` (regime de caixa) — quando o dinheiro
  sai da conta, não quando a compra foi feita.

### Pessoal x empresa
A Juliane tem a **Benetti UP**, empresa de marketing digital, e as contas ainda
não estão separadas na prática — o mesmo cartão traz gasto da casa e da empresa.
É a razão principal de ela precisar deste controle.

- Pessoa cadastrada com `tipo: "empresa"` em `configuracoes.json` define o
  campo `ambito` do lançamento (`pessoal` ou `empresa`).
- Seletor no topo da dashboard: **Pessoal** (padrão) / **Benetti UP** / **Tudo somado**.
- **A aba Cartão & Faturas nunca filtra por âmbito** — a fatura é obrigação de
  pagamento e vem inteira, misturada mesmo. As abas de análise (Painel,
  Lançamentos, Para Onde Vai) filtram.
- Facebook/Meta/Google Ads → `trafego_pago` / **Benetti UP**.

### Faturas: situação e rotativo
Cada fatura guarda `situacao` (paga, paga_parcial, fechada, aberta),
`total_fatura`, `saldo_anterior`, `pago` e `em_aberto`.

**O total da fatura não é o gasto do mês.** Quando a anterior não foi quitada,
o saldo rola com juros e entra no total sem aparecer linha a linha. Somar o
total como despesa contaria a mesma coisa duas vezes. Use `cobrado`
(lançamentos do período) para gasto e `total_fatura` para obrigação.

### Fatura renegociada
A Juliane parcelou o pagamento do total de algumas faturas, e as parcelas vêm
cobradas nos meses seguintes (`Parc Fatura Seg`, `Parcela de Refinanciamento`,
`Credito Por Parcelamento`).

**A parcela não é consumo novo** — as compras que geraram a dívida já foram
contadas uma a uma na fatura em que aconteceram. Ficam com
`natureza: "divida_parcelada"`: saem dos totais de gasto e do Para Onde Vai, e
aparecem na aba Dívidas com quanto falta pagar. Contá-las como despesa inflava
agosto, setembro e outubro em R$ 4 a 6 mil cada.

Os **juros, IOF e encargos** do parcelamento são custo novo de verdade e seguem
como despesa, na categoria `encargos_financeiros`.

Na aba **Cartão & Faturas** a parcela continua aparecendo: a fatura cobra ela, e
tirar faria a soma da tela não bater com o valor a pagar. O `cobrado` do
cabeçalho também a inclui.

### Múltiplos cartões
Dois cartões: **4846** (Itaú Black, pessoal) e **0442** (Visa Infinite, quase
só tráfego pago). A chave de uma fatura é **cartão + mês** — só o mês faria a
fatura de um cartão sobrescrever a do outro.

### Regra de ouro dos dados
**Onde não há dado cadastrado, a tela diz "não cadastrado" — nunca R$ 0,00.**
Zero parece informação e induz leitura errada. Foi exatamente isso que fez a
Juliane desconfiar da dashboard na primeira versão.

### Faturas do cartão
- Sempre importar do **XLSX original do Itaú**, nunca deduzir mês de fatura a
  partir da data da compra. A fatura traz cada parcela com a data da compra
  original, então deduzir empilha parcelas de meses diferentes no mesmo mês.
- A coluna **Parcelamento** da fatura traz "Parcela N de M" — usar isso, não inferir.
- Linhas de **"Pagamento Débito Automático"** e **"Pagamento Com Saldo"** são
  quitação da fatura anterior, **não são despesa**. Ficam com `natureza: "pagamento"`
  e são excluídas de todo total de gasto.
- Reconciliar contra o valor **cobrado** (soma dos lançamentos), não contra o
  **pago** — eles diferem quando há saldo, crédito ou encargo.
- Não existe dia de fechamento fixo no código: cada fatura carrega o próprio
  vencimento, lido do arquivo.
- **O mês da fatura vem do vencimento, nunca do nome da aba.** O Itaú nomeia a
  aba pelo ciclo: o 0442 e o 3794 fecham num mês e vencem no dia 1º do seguinte,
  então a aba diz "Fatura 06-26" e o vencimento diz 01/07/2026. Pelo regime de
  caixa isso é julho. Lendo a aba, duas faturas seguidas do mesmo cartão caem na
  mesma chave cartão+mês e uma sobrescreve a outra — foi o que fez quatro
  faturas parecerem não enviadas.
- **Nunca somar duas leituras da mesma fatura.** A mesclagem protege contra
  reimportar uma fatura já gravada, mas não contra ler a mesma fatura duas vezes
  na mesma rodada. Cópia repetida do mesmo arquivo é ignorada; versões que
  divergem no conteúdo param a importação em vez de serem escolhidas em
  silêncio.
- **Parcela faltando denuncia fatura faltando.** Buraco na numeração ("parcela 3,
  depois parcela 5") quase sempre é a fatura daquele mês que não foi importada,
  não erro de leitura.

### Classificação de despesas
As regras vivem em **`financeiro/data/regras-classificacao.json`**. Ao aprender
uma regra nova da Juliane, **gravar lá** — não só corrigir os lançamentos, senão
a próxima importação repete o erro.

Princípio que ela definiu: **a pessoa da despesa é quem se beneficia dela, não
quem passou o cartão.**

Regras que ela informou diretamente:
- **Savegnago** (e supermercado em geral) → `alimentacao` / **Família**, mesmo
  quando pago no cartão do Hugo.
- **Sesi / Editora Sesi** → `educacao` / **Luca** — é a escola onde o filho estuda.
- **Qualquer posto de combustível** → `transporte` / **Família**. Vale para
  qualquer posto, não só os que têm "auto" no nome — a primeira versão da regra
  exigia "auto posto" e deixava escapar Posto Riviera, Posto Big e outros.
- **Transurc** → `transporte` / **Juliane** — transporte público para o trabalho.
- **Omega / natação** → `esportes` / **Valentina**.
- **Tokio Marine** → `seguro` / **Família** — seguro do carro.
- **Selva Urbana, Petcamp** → `pet` — ração.
- **McDonald's, KFC, rodízio** → `alimentacao_fora`.
- **Papelaria** → `educacao` (material escolar).
- **Facebook / Meta / Google Ads** → `trafego_pago` / **Benetti UP**.

Confirmados depois: **Mundo Cores** é a escola da Valentina; **papelaria** é
material dos dois filhos, e por isso existe a pessoa **Filhos**.

### Ferramentas de manutenção (`financeiro/scripts/`)
- `conferir-fatura.js arquivo.xlsx [...]` — só leitura. Diz de que mês a fatura
  é de verdade (pelo vencimento), se já está gravada, se o conteúdo bate e qual
  fatura anterior ela quita. Serve para checar um envio antes de importar.
- `importar-faturas-itau.js` — reconstrói tudo a partir dos XLSX. Aceita
  `DIR_FATURAS` por variável de ambiente.
- `classificar.js aplicar|exportar|importar` — aplica as regras, gera planilha
  de revisão em lote (um estabelecimento por linha) e reimporta o que foi
  revisado, opcionalmente virando regra nova.
- `testar-dashboard.js` — suíte de testes. Calcula os valores esperados direto
  do JSON e compara com o que o navegador renderiza. **Precisa de Chromium; roda
  no ambiente de desenvolvimento, não no VPS.**

Todo script grava só com `--aplicar`; sem a flag, apenas simula.

## Garimpo de Produtos — regras de curadoria
- **Nunca buscar/inserir suplementos, vitaminas, colágeno, whey** ou qualquer produto
  de suplementação alimentar/nutricional — a Juliane não anuncia esse tipo de produto,
  mesmo que passe nos critérios de comissão/nota/vendas.
- Piso mínimo de comissão pra um produto entrar no garimpo: R$9,00 (CPA máximo/comissão
  em reais). Abaixo disso nem inserir.
- Existe uma rotina diária automática (Routine `Garimpo de Produtos — Curadoria diária`)
  que roda essa curadoria sozinha todo dia às 7h (Brasília). Se precisar ajustar critérios
  de busca no futuro, atualizar o prompt dessa rotina também, não só fazer buscas manuais.
- Essa rotina busca em duas frentes todo dia: categorias gerais (evergreen) e, sempre que
  houver data/temporada comemorativa nos próximos ~90 dias, também busca produtos ligados
  a ela (big_sazonal/microsazonal) — assim o "Top 7 priorizados" não fica só com evergreen.
