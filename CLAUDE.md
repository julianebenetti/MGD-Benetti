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
- **Auto posto / combustível** → `transporte` / **Família** — o carro serve a todos.

Pendente de confirmação: **Esc Inf Mundo Cores** é escola infantil, mas não foi
dito de qual filho (Luca ou Valentina). A regra genérica de escola não define
pessoa, justamente para não chutar.

### Ferramentas de manutenção (`financeiro/scripts/`)
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
