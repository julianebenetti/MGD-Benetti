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

## Salário e Receita Previsível (Juliane)

**Salário líquido real: ~R$ 4.270/mês**
- Salário base Elektro: ~R$ 3.543,89
- Auxílio-creche: R$ 724,20 (benefício da empresa para Valentina)
- PLR e férias (quando ocorrem): além do básico, não previsível mensalmente

**O que NÃO conta como receita previsível:**
- Pró-labore (Juliane não recebe)
- Contribuições do Hugo (inconstantes, valores variam)
- Rendimentos de aplicação (esporádicos)
- Outros PIX e transferências esporádicas

*Regra de ouro: a dashboard usa apenas salário + benefícios fixos (categorias `salario`, `beneficio`, `plr`, `ferias`) para calcular receita esperada.*

## Dashboard Financeira (`financeiro/`)

Controle das contas **pessoais** da Juliane e do Hugo. Não tem relação nenhuma
com Shopee, afiliados ou e-commerce — se surgir essa mistura, é engano.

**Exceção única, confirmada (30/08)**: o PIX de R$1.961 pra "CSRA Brasil"
(17/03/26, vinha como `nao_classificado`) é fornecedor do negócio de
Shopee/afiliados da Juliane, não da Benetti UP — mas ela decidiu
deliberadamente contar como despesa da Benetti UP nesta dashboard, já que
é a única empresa cadastrada aqui e não vale criar uma terceira categoria
de âmbito só por causa de um lançamento. Não é engano nem precedente pra
tratar toda mistura futura assim — se aparecer mais gasto claramente do
negócio de e-commerce, perguntar de novo antes de repetir esse tratamento.

### "Não classificado" e o bug real que apareceu no meio da limpeza (30/08)
A Juliane pediu pra classificar junto o lote de lançamentos `nao_classificado`
(R$24.271,12 no começo) que sobrou de importações antigas do extrato e da
fatura — foram várias rodadas de "me diz quem é" até restar só R$9.479,48,
a maioria cobranças de plataforma sem nome de pessoa (Asa*, Mp*, Ckt*/Cakto,
Vivianefurtadopor, Assiny) que ela ainda não identificou.

- **A viagem do Airbnb (dez/25) foi da família estendida, não só da casa
  dela** — irmãos, cunhadas e sobrinhos foram junto, e os PIX recorrentes de
  Fabio, Rogério e Miriam (R$4.878,56 no total, entrando como `receita`)
  eram o reembolso da parte de cada família no custo, não renda dela.
  Contar como receita inflava o rendimento tributável do IRPF. Reclassificado
  pra `natureza: transferencia` / categoria `reembolso_viagem_familia` — mexe
  no saldo, não conta como receita nem despesa. As 2 "DEV PIX Fabio Gomes"
  (R$377,78 e R$264,40) que eu tinha classificado errado como gasto novo de
  viagem eram, na verdade, estorno de pagamentos dele que bateram errado —
  valores idênticos aos da recorrência dele, mesma correção.
- **Bug real achado nesse processo, em `apurarIrpf()`**: `natureza:
  transferencia` (entre contas próprias, pagamento de fatura, aporte na
  empresa, o reembolso da viagem) e `natureza: emprestimo` (dinheiro novo
  tomado — consignado, Mercado Pago) não tinham exclusão própria na função,
  e categoria sem regra cadastrada cai direto em "não deduz" por padrão.
  Isso inflava o card "O que não deduz" do IRPF em **R$153 mil de
  transferências** (entre contas, fatura, aporte) **+ R$34 mil de empréstimo
  tomado** — nenhum dos dois é gasto de verdade. Corrigido excluindo os dois
  logo no início do loop, do mesmo jeito que `pagamento`/`ajuste` já eram
  excluídos. `divida_parcelada` (parcela de empréstimo) continua passando
  adiante de propósito — tem regra própria no grupo "dívida" que marca como
  não-dedutível pra aparecer como informativo, isso não mudou.
- **Os 5 boletos "PAG TIT INT 237" fora da faixa de condomínio (R$600-650)
  são o cartão Amazon/Bradescard dela**, confirmado com 2 comprovantes reais
  (R$431,58 venc. 15/01, R$459,31 venc. 18/02). Como essa dashboard só lê o
  extrato Itaú (não tem acesso à fatura itemizada desse 4º cartão), o boleto
  pago é a única visão que existe desse gasto — mantido como `despesa`
  categoria `compras`/Juliane em vez de `pagamento` (que o tornaria
  invisível, sem nenhum outro lugar contando o gasto de verdade).
- Cada rodada de classificação virou regra nova em `regras-classificacao.json`
  (cartão) ou `importar-extrato-itau.js` (extrato), pra próxima importação já
  classificar sozinha — exceto onde o mesmo texto de descrição cobre coisas
  diferentes (ex: "COLEGIO" bateu tanto mensalidade da Valentina quanto
  ballet; "Daniel" bateu tanto transporte do Luca quanto pizza), casos em que
  a classificação ficou manual, presa à transação exata, pra não contaminar
  a próxima ocorrência do mesmo nome com o motivo errado.

### Benetti UP: conta própria, margem real e entrelaçamento com dívida pessoal (30/08)
A Juliane mandou o extrato Nubank da Benetti UP (jan-ago/26, conta PJ separada,
CNPJ 64.020.863/0001-03) pra eu entender se a empresa se sustenta sozinha antes
de decidir se dava pra contar com ela pra ajudar na crise pessoal. **Essa conta
não está integrada na dashboard** (financeiro.json só vê o que vaza pro cartão/
extrato pessoal da Juliane) — a análise abaixo foi feita direto em cima do PDF,
não é dado gravado em lugar nenhum do sistema.

- **A empresa tem receita real e margem operacional positiva**: R$144.089,43 de
  receita (via processadoras SHPP e depois Maree — troca de processadora
  confirmada pela Juliane, não queda de venda) contra R$120.369,66 de despesa
  operacional real (fatura dos cartões 0442/3794, DAS-Simples Nacional, Receita
  Federal, contabilidade Stima) = **~R$2.965/mês de margem**. Não é um buraco.
- **Mas o saldo da conta fecha em R$0,00 todo santo mês**, sem exceção — a
  Juliane chegou a tentar guardar R$33.000 numa Aplicação RDB em 16/01 e
  resgatou tudo de volta em 11 dias (20 e 27/01). Nenhuma reserva própria
  sobrevive.
- **R$16.855,00 da margem da empresa foram usados pra pagar os empréstimos
  pessoais dela no Mercado Pago** (27/01, 21/02, 30/06) — confirmado pela
  Juliane. E, ao mesmo tempo, ela confirmou que **os próprios empréstimos do
  Mercado Pago foram tomados, em parte, pra pagar fatura da empresa** — ou
  seja, o dinheiro circula nos dois sentidos entre pessoa física e empresa,
  o que a deixou confusa sobre "de quem" é essa dívida. Conclusão dada a ela:
  pra decisão de **o que pagar agora**, tratar como uma dívida só, sem tentar
  separar pessoal de empresa — essa linha só vai ficar real quando a empresa
  tiver capital próprio pra não precisar de crédito pessoal.
- **Confirmado, não só suposto: os 2 cartões da Benetti UP (0442 e 3794) às
  vezes são pagos por Pix direto em vez de boleto**, pra liberar limite mais
  rápido — a Juliane reenviou as faturas dos dois cartões e o
  `conferir-fatura.js` bateu os 3 Pix "misteriosos" do extrato Nubank contra
  o campo "quita a fatura anterior" de cada uma:
  - R$737,15 (26/06) → fatura do 0442 vencendo 01/07/2026
  - R$6.200,00 (21/07) → fatura do 3794 vencendo 03/08/2026
  - R$5.000,00 (21/08) → fatura do 3794 vencendo 01/09/2026
  Nenhuma fatura reenviada gerou divergência ou dado novo — as 15 batiam
  exatamente com o que já estava gravado.
- **Achado à parte, via Registrato (CCS/Banco Central)**: duas relações
  bancárias novas, de 11/12/2025, sem explicação — **Nu Financeira S.A. CFI**
  (braço de crédito do Nubank, diferente da conta de pagamento "Nu Pagamentos"
  já rastreada) e **Banco Votorantim S.A.**. A Juliane não reconheceu a conta
  do Votorantim de cabeça. Módulo SCR do Registrato (que mostraria o valor de
  cada dívida) estava fora do ar na hora de puxar — pendência em aberto, não
  descartar a possibilidade de ser crédito real não mapeado nos 12 contratos.

### Estrutura
- 7 abas: Painel, Lançamentos, Para Onde Vai, Cartão & Faturas, Dívidas &
  Patrimônio, Fluxo de Caixa, Imposto de Renda. Importar / Configurações /
  Editor ficam no menu **⚡ Ferramentas**.
- Escopo: **somente 2026** (`ANO_DASHBOARD` em `public/index.html`).
- O mês usado em tudo é `mes_vencimento` (regime de caixa) — quando o dinheiro
  sai da conta, não quando a compra foi feita.

### Painel virou painel de caixa, e por que os números anteriores mentiam (31/08)
A Juliane disse que não confiava mais nos dados: "meu salário líquido é em
torno de 3k, como você mostra que minhas entradas serão de 6k?", "está usando
no planejamento só as saídas de cartão e eu tenho muita coisa pra pagar antes",
"falta incluir os novos cartões". As três reclamações estavam certas, e cada
uma era um erro diferente. Todos conferidos contra o JSON antes de mexer.

- **Provento bruto não é entrada.** O holerite lança o bruto como receita e
  cada desconto como lançamento próprio (é o desenho certo, documentado
  acima). O Painel somava só os proventos: Ago/26 dava R$ 6.064,76 quando o
  que cai na conta é **R$ 2.834,19** — INSS, IR, plano de saúde, previdência e
  os três consignados saem antes. Agora `folhaDoMes()` devolve
  `proventos − descontos`.
- **Desconto de folha não é vencimento.** O consignado descontado na folha
  (R$ 1.563,62/mês) já está abatido no líquido, e entrava *de novo* como
  parcela a pagar — o mesmo dinheiro saindo dos dois lados. Só o **quarto**
  consignado, debitado em conta (R$ 1.402,67), é saída de caixa. O
  discriminador é `origem` (`holerite_elektro` x `extrato_itau`), **não**
  `natureza` — as duas são `divida_parcelada`.
- **Nem toda fatura sai desta conta.** Em 2026 os cartões faturaram
  **R$ 249.708,46**, mas só **R$ 55.058,28** aparecem como `pagamento_fatura`
  no extrato pessoal: as faturas do 0442 e as grandes do 3794 são pagas pela
  conta PJ da Benetti UP no Nubank, que não está integrada. Somar o total de
  todas as faturas cobrava da Juliane o cartão que a empresa pagou — era o
  grosso do "rombo" que a tela acusava. A saída do cartão agora tem duas
  partes honestas: o pagamento que o extrato registra, mais o que segue em
  aberto nas faturas do mês.
- **Faltavam as saídas que não são cartão.** Condomínio, escola, van escolar,
  aluguel de vaga, utilidades, empréstimo da Cenira, locker, doação: R$
  4.233,63 só em Ago/26, invisíveis no Painel. Entraram, com data.
- **`ajuste` nem sempre lança os dois lados.** A função excluía a natureza
  inteira supondo simetria; em Ago/26 existe só a ponta de saída (Bradesco
  Odonto, acerto de 07/2026, R$ 3,52) e o líquido dava R$ 2.837,71 contra os
  R$ 2.834,19 do comprovante. Agora soma pelo sinal (`tipo`).
- **Prova de que a conta está certa:** o líquido calculado da folha bate **ao
  centavo com o crédito que o banco fez**, em todos os meses comparáveis — são
  fontes independentes (holerite de um lado, extrato do outro). Virou teste
  permanente, junto com duas guardas de regressão: o bruto nunca pode aparecer
  como entrada, e o consignado da folha nunca pode aparecer também como saída.

**O Painel deixou de aplicar o seletor de âmbito.** A conta corrente é uma só e
não sabe o que é gasto da casa e o que é da Benetti UP — a fatura chega inteira.
Filtrar as saídas por "pessoal" enquanto a fatura entrava inteira era comparar
universos diferentes. Em vez de esconder metade, o Painel mostra dentro do total
quanto é da empresa (`fracaoEmpresaDaFatura()`, lida dos próprios lançamentos).
Mesma decisão que a aba Cartão & Faturas já tinha, e pelo mesmo motivo.

### Os 3 cartões novos: cabeçalho sem lançamento (31/08)
Existem **6 cartões**, não 3: além do 4846 (Black), 0442 (Infinite) e 3794
(Azul), entraram **0013 (Amazon Mastercard, Bradescard)**, **3987** e **3711**
(dois Bradesco Visa Platinum).

- **12 faturas têm cabeçalho mas nenhum lançamento importado** — as 8 do 0013,
  as 3 do 3987 e a do 3711. O total aparece, mas nenhuma compra existe em
  Lançamentos nem em Para Onde Vai: a dashboard sabe *quanto*, não sabe *em
  quê*. Não há arquivo-fonte dessas faturas no repositório; **para preencher,
  a Juliane precisa enviar os arquivos**. A aba Cartões agora diz isso
  explicitamente, em vez de marcar as 12 com um selo vermelho de "não fecha".
- **Os 7 boletos "Cartão Amazon (Bradescard)" do extrato são o pagamento da
  fatura 0013** — batem centavo a centavo com o `cobrado` de cada mês. Com o
  cabeçalho da fatura existindo, contar os dois é dupla contagem; o boleto fica
  de fora do Painel. O de julho tinha escapado por vir com a descrição crua do
  banco (`PAG BOLETO BANCO BRADESCARD S A`). **Se um dia a fatura 0013 for
  importada itemizada, os 8 boletos têm de virar `natureza: pagamento`** — a
  premissa antiga ("o boleto é a única visão desse gasto") deixou de valer no
  momento em que os cabeçalhos foram criados.
- **O âmbito do cartão era chutado por `cartao !== '4846'`**, o que carimbava
  Amazon e os dois Bradesco (pessoais da Juliane) como Benetti UP. Agora sai
  dos próprios lançamentos; sem lançamento, a tela diz que não sabe (❔).
- **A fatura do 3711 estava com `mes: Ago/26` e vencimento 15/09** — única das
  39 em que o mês não vinha do vencimento. Aparecia nos vencimentos de agosto e
  sumia de setembro. Corrigida para Set/26.

### As faturas do Bradesco estavam nos uploads da sessão (31/08)
A Juliane disse que já tinha mandado as faturas do Bradesco. Tinha mesmo: os
PDFs estavam em `/root/.claude/uploads/<sessão>/` — 13 arquivos únicos, achados
procurando no transcript por mensagens dela com anexo. **Antes de dizer que um
dado não existe, procurar ali.** Os arquivos foram copiados para
`financeiro/faturas-bradesco/` e agora versionam junto com o resto.

- **119 lançamentos e 14 faturas importados** (`ler-faturas-bradesco.py`,
  `ler-extratos-abertos-bradesco.py`, `importar-faturas-bradesco.py`). Os 3
  cartões novos deixaram de ser cabeçalho vazio.
- **A fatura do Bradesco fecha por `total = saldo anterior + soma dos
  lançamentos`** — diferente da do Itaú, ela lança o pagamento da fatura
  anterior como linha negativa dentro dela mesma. O importador confere essa
  identidade em cada fatura e **recusa gravar** se alguma não fechar.
- **Quando o PDF não imprime "Saldo anterior"** (formato do 3987 e dos extratos
  em aberto do app), o valor é deduzido da fatura anterior do mesmo cartão e só
  é aceito se com ele a fatura fechar — nunca entra número inventado.
- **O extrato "EM ABERTO" do app traz mais de um cartão no mesmo PDF**, em
  blocos separados por `XXXX.XXXX.XXXX.NNNN`, cada um com seu subtotal. E a
  descrição às vezes quebra nas linhas de cima e de baixo da linha da data,
  deixando só o código `000` no meio — precisa ser remontada das vizinhas.
- **O que a fatura corrigiu no dado que estava gravado:** o `total_fatura` de
  0013 Ago/26 era 178,92 e o PDF diz **73,27** (o 178,92 vinha de somar o saldo
  anterior a compras que já o incluíam — era a divergência de R$ 2,03 que estava
  em aberto); 0013 Jul e Ago estavam como não pagas e as duas foram pagas (20/07
  e 17/08); 3987 Ago/26 foi paga por débito em conta em 17/08, o que só o
  extrato do app mostrava.
- **Os 8 boletos do cartão Amazon no extrato viraram `transferencia` /
  `pagamento_fatura`** — exatamente o que este arquivo já avisava que teria de
  acontecer no dia em que a fatura 0013 fosse importada itemizada. Regra
  permanente em `importar-extrato-itau.js`.

### Conta recorrente projetada pela mediana (31/08)
A Juliane pediu: "mesmo que você não saiba o valor que terei que pagar, aponte
um valor médio aproximado, pra eu poder me programar". Conta que se repete todo
mês só virava lançamento quando o extrato daquele mês era importado — num mês
futuro ela sumia, e o Painel dava a impressão de que só havia cartão a pagar.

- `perfilDasRecorrentes()` monta o perfil de cada conta que apareceu em **3
  meses ou mais**: quanto costuma custar e em que dia costuma cair.
  `recorrentesFaltandoEm(mes)` devolve as que faltam naquele mês.
- **Mediana, não média.** Uma conta de luz de verão ou uma van cobrada em dobro
  num mês puxam a média para cima e fazem a projeção prometer um gasto que não é
  o típico.
- Toda linha projetada aparece marcada **"previsto"**, dizendo de quanto a
  quanto variou e em quantos meses — nunca se confunde com lançamento real.
- Set/26 saiu de "só cartão" para **R$ 6.381,63** de conta recorrente com dia e
  valor aproximado.

### Conta recorrente cadastrada à mão, e a que a empresa paga (09/09)
A Juliane mandou o print da cobrança da **Stima Contábil** (R$ 405,00, boleto,
todo dia 5, Conta Azul, em nome da Benetti UP): "todo dia 05 eu tenho que pagar
essa conta da empresa, sempre esqueço, preciso que você me lembre e coloque nas
contas a pagar recorrentes".

**A projeção pela mediana nunca ia descobrir essa conta.** Ela exige 3 meses ou
mais no extrato pessoal, e a Stima aparece **uma única vez** lá (18/05/26,
R$ 414,53) — normalmente o boleto sai da conta da Benetti UP no Nubank, que não
está integrada. Conta que existe, que ela sabe que existe, e que a dashboard não
tinha como aprender por mais tempo que passasse.

- **`configuracoes.json` → `contas_recorrentes[]`**: `id`, `descricao`, `valor`,
  `dia`, `categoria`, `pessoa`, `forma`, `paga_por`, `ativa`, `observacao`.
  Fica na configuração, não no código, pelo mesmo motivo que o cadastro dos
  cartões saiu do `index.html`: valor e dia mudam com o tempo.
- `contasRecorrentesCadastradas()` alimenta `recorrentesFaltandoEm(mes)` junto
  com o histórico. **Deduplicação em duas frentes**, por `CHAVE_RECORRENTE`:
  contra o lançamento real do mês e contra a mesma conta já projetada pelo
  histórico — duas linhas da mesma conta somariam duas vezes.
- A linha vem marcada **"conta cadastrada, todo dia N por boleto"**, em vez do
  "média de N meses" das derivadas do histórico. São origens diferentes e a tela
  não pode fingir que são a mesma coisa.

**`paga_por` decide de qual caixa o dinheiro sai.** Com `paga_por` diferente de
`juliane`, a conta:
- **aparece** na lista de vencimentos — é para isso que ela existe, lembrar;
- **fica fora** do "sai da conta", do rodapé "ainda a pagar" e dos totais do
  plano do mês (`meuDinheiro`), com aviso próprio dizendo quanto e qual conta;
- **nunca é acusada** pelo fechamento do plano: não deixa rastro no extrato
  pessoal, então dizer que não foi paga seria acusação sem prova nenhuma.

Mesma decisão, e o mesmo motivo, do que já tirava do Painel a fatura que a
Benetti UP quita: somar aqui cobraria do salário dela um boleto da empresa.

4 testes de regressão, **verificados quebrando o código de propósito** (sem os
dois filtros, 11 testes falham): toda conta cadastrada aparece na lista, nenhuma
duplica uma já projetada, a paga por outro caixa vem marcada na tabela
(`data-fora-da-conta`), e o rodapé bate com a soma sem ela e não bate com ela.

**Lembrete mensal**: Routine `Contabilidade STIMA — boleto da Benetti UP (vence
dia 5)`, dias 3 e 5 às 8h de Brasília (`0 11 3,5 * *` em UTC), sessão nova a
cada disparo, com push e e-mail. Não tem conector de Gmail, então não busca o
boleto — só lembra, e o prompt proíbe inventar valor ou linha digitável.

### Dívida que existe mas não está sendo paga (31/08)
Depois de ver que as 3 parcelas do Mercado Pago somam **R$ 3.301,24/mês** contra
um líquido de R$ 2.834,19, a Juliane decidiu parar de pagar quase tudo por um
tempo. Decisão dela, registrada — não é esquecimento nem dado faltando.

**O que ela continua pagando** (perguntado e confirmado em 31/08):
os **4 consignados** (o que cai em conta e os 3 da folha), o **empréstimo da
mãe** (Cenira), as **duas escolas** (Valentina e Luca), os cartões **0442 e
3794** (que carregam o tráfego pago e são quitados pela conta da Benetti UP), e
as contas correntes do mês (condomínio, luz, água, van, vaga, Claro, locker).

**O que ficou parado:** os 3 empréstimos do Mercado Pago, o **IPTU**, a
**anuidade do CRC-SP**, e as faturas dos **4 cartões pessoais** (4846 Black,
0013 Amazon, 3987 e 3711).

- Os 3 contratos ganharam `em_pagamento: false`, `suspensa_desde` e
  `motivo_suspensao` em `financeiro.json`.
- **O contrato continua na lista** (a dívida existe e cresce), mas a parcela
  **sai do KPI "Parcelas por mês"** — esse número é o que ela usa pra se
  programar, e somar parcela que não vai ser paga prometeria um pagamento que
  não vai acontecer. O KPI caiu de R$ 8.885,26 para **R$ 5.584,02**, dizendo no
  subtítulo quanto está suspenso.
- Na tabela de Contratos a linha vem marcada **"não está sendo paga"**, com a
  parcela riscada e a previsão de quitação trocada por "suspensa" — projetar
  data de quitação de dívida que ninguém está pagando seria ficção.
- Um aviso abaixo da tabela lista os contratos suspensos e diz o que a tela
  **não** sabe: o saldo cadastrado é o do contrato original, não o saldo
  corrigido pelos encargos do atraso. Sem pagamento, o valor real cresce.
- 3 testes de regressão: o KPI soma só os contratos em dia, o total suspenso
  aparece na tela em vez de sumir em silêncio, e cada contrato suspenso é
  marcado como tal na tabela.

**Ao cadastrar dívida nova, checar se ela está sendo paga.** `em_pagamento`
ausente vale como `true` — o padrão é que se paga; só a exceção precisa de
marca.

### Cartão com pagamento parado, e o cadastro de cartões saindo do código (31/08)
Fatura de cartão parada é o mesmo princípio da dívida suspensa: continua sendo
cobrada, o saldo cresce, mas **o valor não sai da conta** — então não pode
entrar no número que ela usa pra se programar.

- **O cadastro dos cartões saiu do `index.html` e foi para
  `configuracoes.json`** (`cartoes[]`: `final`, `nome`, `descricao`, `cor`,
  `pagamento_suspenso`). Estava numa `const` no meio do código — e "parei de
  pagar esse cartão" é decisão que muda com o tempo, não pode exigir editar
  código. `CARTOES_PADRAO` continua no arquivo só como valor até a configuração
  carregar; `cadastroDoCartao()` lê da config e cai nele se não achar.
- `pagamentoSuspenso(cartao)` é o que o Painel consulta. A fatura parada sai do
  `cartaoAPagar`, sai do rodapé "ainda a pagar", sai da linha do tempo, e ganha
  o selo **"pagamento parado"** na tabela de vencimentos.
- Um aviso próprio mostra **quanto está parado e em quais cartões**, dizendo que
  a fatura segue sendo cobrada e o saldo cresce com juros de rotativo. O valor
  nunca some da tela — só sai da conta do que tem de pagar.
- Efeito em Ago/26: "sai da conta" caiu de R$ 17.332,08 para **R$ 8.702,37**, e
  a falta do mês de R$ 14.497,89 para **R$ 5.868,18**.
- 2 testes de regressão, **verificados quebrando o código de propósito** (sem o
  filtro, 4 testes falham): a soma bate com a tela sem o valor parado e não bate
  com ele, e o valor parado aparece na tela em vez de sumir.

### Plano de pagamento do mês, com fechamento (03/09)
A Juliane perguntou se daria para marcar, na lista de vencimentos, o que vai
conseguir pagar e o que fica em aberto — e pediu para pensar junto antes. A
lacuna era real: a dashboard só sabia de decisão **permanente** (`em_pagamento`,
`pagamento_suspenso`). O que ela decide de verdade todo mês é outra coisa —
destas contas, quais cabem no dinheiro deste mês — e pode ser diferente no mês
seguinte. Ela escolheu a versão com fechamento, não só o plano.

- **`dadosGlobais.plano_do_mes[mes]`** = `{ orcamento, itens: {chave: 'pagar'|'adiar'}, atualizado_em }`.
  Fica fora dos lançamentos de propósito: fatura de cartão não é lançamento, e
  conta recorrente projetada não existe como registro nenhum. A chave cobre os
  três casos: `fatura|<cartao>|<mes>`, `lanc|<id>`, `prev|<chave recorrente>`.
- **Só entra no plano o que ainda não aconteceu.** Lançamento já no extrato é
  fato, não decisão — marcar "vou pagar" nele não decidiria nada e faria o
  fechamento dizer sempre que deu certo.
- **O default vem do que a dashboard já sabe**: cartão suspenso entra como
  "deixo", o resto como "pago". São ~28 linhas por mês; ninguém marca 28 itens
  todo mês. A marca do mês **ganha do flag permanente** naquele mês, que é como
  ela retoma um cartão sem desfazer a decisão geral.
- **O valor disponível é digitado por ela.** A dashboard não sabe quanto vai
  ter: além do salário entra o que o Hugo passa e o que circula com a Benetti
  UP. Sem valor informado, cai no líquido da folha e diz que está fazendo isso.
- **O fechamento** (`conferirPlano`) compara o que foi marcado contra o que de
  fato saiu, e é o que impede o plano de virar intenção velha na tela.

**A parte difícil do fechamento foi não acusar errado.** A primeira versão dizia
que a Juliane não tinha pago a escola, o IPTU e a faxina de agosto — quando a
verdade é que o extrato de agosto está incompleto e a dashboard só não enxerga.
Duas defesas, nessa ordem:

1. **`extratoIncompletoNoMes(mes)`** — se o mês tem holerite com provento e o
   extrato daquele mês não traz o crédito do salário correspondente, falta
   arquivo, não falta pagamento. Não é heurística de volume: é contradição no
   dado, e salário ela recebeu. Enquanto isso for verdade, nada daquele mês é
   dado como não pago.
2. **`extratoCobreAte()`** — conta que vence depois da última linha do extrato
   importado também não pode ser julgada.

Fatura de cartão é julgada mesmo assim: o `em_aberto` dela não depende do
extrato. Em Ago/26 o fechamento passou de "10 acusações falsas" para **uma
acusação verdadeira** (a fatura do Black, R$ 10.667,16) e 10 itens em "não dá
para conferir".

**Bug pré-existente achado nesse processo:** 5 lançamentos de agosto
(R$ 2.669,00 — locker, empréstimo da mãe, van do Luca, PIX Instituto,
transferência) estavam com `status: 'agendado'` e data já passada. `agendado` é
verdade no dia da importação, não para sempre — passada a data, o PIX aconteceu,
tanto que o extrato o lista. A tabela de vencimentos vinha mostrando como
"venceu há 9 dias" coisa que já tinha sido paga, e o fechamento os acusaria.
Corrigido na leitura (`quitado` deixou de checar o status), não no dado: o
status era verdadeiro quando foi gravado, e a correção vale para toda importação
futura sem precisar reescrever nada.

### Alerta do que falta carregar, no topo da dashboard (05/09)
A Juliane pediu um alerta no topo com o que precisa carregar porque a data já
virou. A dashboard vale o que vale o arquivo mais velho que ela leu, e nada na
tela dizia isso — extrato atrasado não erra sozinho, ele faz o mês parecer mais
barato do que é e faz o fechamento do plano acusar conta que ela pagou.

`pendenciasDeDados()` / `renderizarAlertaDeDados()`, acima das abas para
aparecer de qualquer uma. Cada item diz três coisas: **o que carregar**, **por
que a dashboard sabe que falta** e **qual número fica torto enquanto não vier**
— sem a terceira, o alerta é só uma lista de tarefas.

O que ele checa, e o limiar de cada um:

| Checagem | Dispara quando | Nível |
|---|---|---|
| Extrato incompleto | mês tem holerite e o extrato dele não traz o crédito do salário | crítico |
| Extrato parado | última linha há mais de 7 dias (crítico acima de 20) | atenção |
| Fatura do ciclo seguinte | a última fatura do cartão já venceu e não há nenhuma depois | atenção |
| Holerite do mês | **só a partir do dia 26** | atenção |
| Fatura sem lançamento | cabeçalho com total e nenhuma compra importada | atenção |

**Duas regras que mantêm isso legível:**

1. **Só aparece quando há o que fazer.** Bloco que fica sempre aceso vira papel
   de parede e para de ser lido. Tem teste para o outro lado: com uma linha de
   extrato de hoje injetada, o aviso de "parado há N dias" tem de sumir.
2. **Nunca cobrar arquivo que ainda não existe.** O salário cai no dia 25, então
   o holerite só é cobrado a partir do dia 26 (`DIA_EM_QUE_O_HOLERITE_JA_SAIU`).
   Cobrar no dia 3 seria ruído, e ruído ensina a ignorar o alerta inteiro.

Em 05/09 dispara com 3 itens: extrato de Ago/26 incompleto (crítico), extrato
parado há 8 dias, e a fatura do ciclo seguinte do 0442 (venceu 01/09). O
holerite corretamente não aparece.

### Alerta de contas a vencer no celular (09/09)
A Juliane perguntou se dá para receber alerta das contas vencendo no celular.
Dá: Routine `Contas a vencer — alerta no celular (diário, 7h)`, todo dia às 7h
de Brasília (`0 10 * * *` em UTC), sessão nova a cada disparo, com push ligado e
e-mail desligado.

**O alerta não recalcula nada em prosa.** A rotina clona o repositório e roda
`financeiro/scripts/contas-a-vencer.js --dias 3` — o mesmo cálculo da tabela de
vencimentos do Painel, em linha de comando, só leitura. Pedir ao modelo que
some os vencimentos a olho no JSON seria convidar número inventado no lugar mais
caro possível: uma notificação que ela lê antes de decidir o que pagar.

- **Não lê o VPS.** `financeiro.descontoirresistivel.com.br` é bloqueado pela
  política de saída do ambiente; a fonte é o repositório, branch
  `claude/financial-dashboard-pbj1ts` (o `main` não tem a dashboard). O dado vale
  o último push, e o alerta diz até que data o extrato enxerga.
- **`AVISAR: SIM|NAO` na segunda linha da saída.** Sem conta na janela, a rotina
  responde uma linha e para. Alerta que chega todo dia com qualquer coisa vira
  papel de parede — a mesma regra do bloco de pendências no topo da tela.
- **"Já venceu e não apareceu no extrato", nunca "você não pagou".** As duas
  guardas do fechamento do plano valem aqui: mês com extrato incompleto e conta
  que vence depois da última linha importada não são julgados.
- **Teste de que as duas visões não divergem**: a suíte roda o script e compara
  item a item (data, título, valor) com a tabela de vencimentos renderizada. São
  dois códigos separados lendo o mesmo JSON; divergir faria o alerta prometer um
  mês diferente do que a tela mostra. Verificado quebrando o script de propósito.

**Bug real achado ao testar isso, em `extratoCobreAte()`:** o extrato traz PIX
agendado com data futura, e a função filtrava só por `data <= hoje`. Passado o
dia 8, o agendamento de 08/09 vira passado e o arquivo de 05/09 — cuja última
linha real é de **04/09** — passava a alegar cobertura até o dia 8. Quatro dias
de cobertura inventada, e dentro deles o fechamento do plano acusava de não paga
uma conta (`PAG TIT INT 299`, 06/09) que o extrato nunca teve como mostrar. Quem
responde "até onde este arquivo enxerga" é a linha que **já movimentou a conta**,
então o discriminador é `status !== 'agendado'`, não a data. Corrigido nos dois
lugares (dashboard e script), com 2 testes que falham sem a correção.

### Extrato em PDF, e o boleto do Amazon que voltava a ser despesa (13/09)
A Juliane mandou o extrato do Itaú em **PDF** (período 14/08 a 13/09, emitido
13/09). Até então o importador só lia o `.xls` do internet banking.

- **`importar-extrato-itau.js` aceita os dois formatos.** O PDF é lido com
  `pdftotext -layout`; a coluna do movimento é separada da coluna de saldo pela
  **posição do número na linha**, lida do próprio cabeçalho. Ler o saldo como
  movimento criaria uma despesa de milhares de reais do nada.
- **A descrição vem cortada na largura da coluna** (`DA CPFL PTA 1007780` em vez
  de `DA CPFL PTA 10077803899`). Não atrapalha: as regras casam pelo começo do
  texto, e `CHAVE_RECORRENTE` já descarta dígitos.
- **`conferirSaldos()` confere a leitura contra o próprio extrato**: o saldo de
  cada dia tem de ser o do dia anterior mais os movimentos entre os dois. Com
  diferença acima de **R$ 1,00 o importador recusa gravar** — valor lido errado
  não entra em silêncio.
- **O último saldo do extrato é o "saldo em conta" do topo e já abate o que está
  agendado**, então o intervalo final é conferido incluindo os agendados. Sem
  isso, a diferença acusada é do tamanho dos agendamentos.
- Sobra **R$ 0,05** sem explicação em 13/09, e é do banco: as 64 linhas com data
  do PDF foram todas lidas (43 movimentos + 21 saldos), e o Itaú não itemiza
  alguns centavos de rendimento da aplicação automática.

**A conferência de saldo achou um erro de leitura no primeiro teste.** Um
estorno de **R$ 1.300,00** (`DEV PIX JULIANE FER28/08`) sumia: a quebra de
página entra como `\f` colado no começo da linha, e exigir o dia no início
absoluto da linha descartava o lançamento sem avisar. O `\f` virou espaço (não
foi removido, para as colunas não andarem um caractere).

**Dois extratos do mesmo período não podem ser somados.** Casar linha a linha
não resolve: o que estava agendado num arquivo aparece no seguinte com outra
data e outro texto (o PIX da vaga de carro estava em 12/09 no extrato de 05/09 e
saiu em **14/09** no de 13/09). Quem manda no período que cobre é o **extrato
mais novo** (`emitidoEm`, lido do "Atualização:" do XLS e do "emitido em:" do
PDF); o mais antigo só contribui com o que está fora da janela do novo — o
começo do mês que o novo não alcança e os agendamentos mais distantes que ele
ainda não lista. Assim os agendados de 15/09, 25/09, 28/09 e 28/10 sobrevivem.

**Bug real, e ele se reintroduzia sozinho a cada importação:** o boleto do cartão
Amazon liquidado como `PAG TIT INT 237` voltava a ser `despesa`/`compras`. A
regra criada em 31/08 casa o texto normalizado (`BRADESCARD`, `Cartão Amazon`),
mas o Itaú também liquida o mesmo boleto pelo código do banco, e essa variação
caía na regra antiga — escrita quando a fatura do 0013 ainda não existia
itemizada. **R$ 197,95 apareciam ao mesmo tempo como gasto no extrato e como
fatura do 0013 a pagar** (R$ 73,27 em Ago/26 e R$ 124,68 em Set/26). Os 9
valores fora da faixa do condomínio batem um a um com o total de uma fatura do
0013, então a troca para `transferencia`/`pagamento_fatura` é segura.

Teste de regressão novo, verificado quebrando o dado de propósito: **nenhum
lançamento de extrato com `natureza: despesa` pode ter o valor exato de uma
fatura vencendo na mesma semana.** É a forma genérica do erro — vale para
qualquer cartão, não só o 0013.

Regra nova: **`PIX QRS TRANSURC`** → `transporte`/Juliane. A Juliane já tinha
definido isso em 23/08, mas `regras-classificacao.json` só vale para a fatura do
cartão; quando a mesma catraca é paga por Pix, a regra tem de existir no
importador do extrato também.

**Resolvido em 13/09:** o R$ 124,68 agendado para 15/09 era ela pagando a
fatura do 0013. O cartão saiu de `pagamento_suspenso` — o pagamento foi
retomado, confirmado por ela. Em Set/26 isso não mudou número nenhum, porque a
marca do mês já dizia "pago"; vale do mês seguinte em diante.

### O plano de setembro estava só no VPS, e dois lugares o ignoravam (13/09)
Depois do deploy, o `atualizar.sh` devolveu uma edição pendente que estava
guardada no VPS: era o **plano de Set/26 que a Juliane marcou na tela em 05/09**
— orçamento de R$ 3.600, as faturas do **0013, 3711 e 3987 marcadas "pago"**
(R$ 1.206,99) e treze contas marcadas "deixo" (condomínio, as duas escolas, o
IPTU, faxina, igreja, manicure, consignado em conta e outras).

Ela existia só no VPS. Trazida para o repositório, porque é decisão dela e
porque o alerta do celular lê do repositório, não do VPS.

**Isso respondeu sozinho a pergunta que estava em aberto sobre o 0013**: o
cartão segue com `pagamento_suspenso`, e ela retomou o pagamento *neste mês* —
que é exatamente o que a marca do mês existe para permitir. Não havia
contradição no dado, havia código que não lia o plano.

**Dois lugares ignoravam o plano, e os dois mentiam de formas diferentes:**

1. **O Painel discordava de si mesmo.** `cartaoAPagar`/`cartaoSuspenso` liam
   `pagamentoSuspenso(cartao)` direto, enquanto a tabela de vencimentos logo
   abaixo já usava `decisaoDoItem`. A tabela dizia que ela vai pagar
   R$ 1.206,99 de fatura; o bloco de cima dizia que esse dinheiro não sai da
   conta. Agora os dois passam por `faturaSaiDaConta(f)`, que é `decisaoDoItem`
   aplicado à fatura. O "sai da conta" de Set/26 foi de R$ 8.359,41 para
   **R$ 9.566,40**, e o "pagamento parado" de R$ 4.404,55 para **R$ 3.197,56**
   (só o Black).
2. **O alerta do celular cobrava decisão já tomada.** `contas-a-vencer.js` não
   lia `plano_do_mes`: mandava condomínio, escola e IPTU como "já venceu e não
   apareceu no extrato" — quando ela tinha marcado os três como "deixo" — e ao
   mesmo tempo listava como "pagamento parado" as três faturas que ela marcou
   para pagar. Agora o que foi adiado sai das listas de cobrança e vai para um
   bloco próprio (**"Você decidiu deixar para depois"**), que existe só para o
   valor não sumir da tela.

**A suíte de testes apagava o plano de verdade do arquivo.** A limpeza do bloco
do plano fazia `delete dadosGlobais.plano_do_mes` e **gravava no servidor** —
escrita quando `plano_do_mes` só tinha resíduo de teste. Rodar a suíte apagou o
plano da Juliane; foi preciso recolocá-lo à mão. Agora a suíte guarda o plano
original no começo, devolve no lugar de apagar, e **um teste no fim confere que
o arquivo terminou com o plano que tinha antes**.

Três testes novos, verificados revertendo a correção (sem ela, 2 falham):
a fatura retomada no mês não aparece como "pagamento parado", o "sai da conta"
conta ela, e a suíte devolve o plano como estava. Os testes que checavam o valor
parado passaram a distinguir as duas camadas: onde o alvo é o **default**, a
expectativa vem do flag permanente (a tela é renderizada com o plano limpo de
propósito); onde o alvo é o **mês**, vem da marca.

### Quatro lançamentos identificados, e a receita que não é renda (13/09)
A Juliane respondeu as quatro perguntas que estavam abertas depois da
importação do extrato de setembro.

- **Cartão Amazon (0013): pagamento retomado.** O R$ 124,68 agendado para 15/09
  era ela pagando a fatura. `pagamento_suspenso: false` em `configuracoes.json`,
  com a data e o motivo na `observacao`. Não mudou nenhum número de Set/26 — a
  marca do mês já dizia "pago" — e vale do mês seguinte em diante.
- **PIX de R$ 600 para Karina (14/09): mesma ajuda de custo** já confirmada em
  30/08 para o de R$ 2.500. A regra existente já classificava certo.
- **PIX de R$ 100 da Symara (08/09): desapego.** Ela vendeu roupas usadas dos
  filhos e a Symara pagou. Categoria nova **`venda_usados`**.
- **PIX de R$ 10 (10/09): um doce comprado de um amigo.** `alimentacao`/Juliane.

**`venda_usados` entra como receita e fica fora do rendimento tributável.**
Venda de bem pessoal usado abaixo do preço de compra não gera ganho de capital,
então contar aqui inflaria a base do IRPF dela. Somada à lista que já existia:
`CATEGORIAS_RECEITA_NAO_TRIBUTAVEL = ['restituicao_irpf', 'venda_usados']`.
Teste novo, verificado tirando a categoria da lista: a tela passa a mostrar
R$ 90.385,33 de rendimento tributável no lugar de R$ 90.285,33.

**Duas regras novas no importador do extrato, e as duas com o sentido travado.**
`PIX TRANSF Symara` só casa na **entrada** — se um dia ela mandar dinheiro *para*
a Symara é outra coisa, e a regra não pode carimbar o motivo errado. O Pix do
doce não tem nome, só um pedaço do documento do recebedor (`55.873`), então a
regra fica presa ao identificador e à **saída**.

Isso precisa ser regra, e não classificação manual: a mesclagem do importador
substitui todo lançamento de extrato dos meses relidos, então correção feita à
mão no lançamento some na importação seguinte.

**Confirmado depois (13/09):** o Pix de R$ 15,00 de 05/03 para o mesmo recebedor
`55.873` também era doce — *"sempre quando é feito pra esse recebedor é doce"*.
A ressalva saiu da regra.

**`PIX TRANSF INSTITU` é doação ao Instituto dos Cegos de Campinas**, R$ 20,00
todo dia 27 desde março. Regra nova, `doacao`/Juliane. Não deduz no IR: a lei só
permite doação a fundo da criança e do idoso, Rouanet, audiovisual, desporto e
PRONAS/PRONON. A regra não filtra valor — o Pix de 02/03 veio R$ 40,00 em vez
dos R$ 20,00 de sempre, e é o mesmo recebedor.

Sobrou **1 lançamento sem regra** nos meses relidos: `PIX TRANSF FERNAND`
(17/08, R$ 20,00).

### `--reclassificar`: regra nova alcançando o que já está gravado (13/09)
Regra nova só pega lançamento que passe pelo importador de novo, e a mesclagem
só substitui os meses dos arquivos informados. Quando a Juliane identifica um Pix
antigo — a doação ao Instituto dos Cegos, que vinha desde março — o arquivo
daquele mês muitas vezes não existe mais para reler, e corrigir o lançamento à
mão não resolve: na próxima importação daquele mês a correção some.

`node scripts/importar-extrato-itau.js --reclassificar [--aplicar]` reaplica as
regras ao que já está no `financeiro.json`, sem precisar de arquivo nenhum.

- **Só mexe no que está em `nao_classificado`.** Classificação que alguém
  decidiu e que nenhuma regra cobre não pode ser sobrescrita por este caminho.
- Imprime o que mudou, de → para, e lista o que continua sem regra.
- Na primeira rodada tirou **9 lançamentos** de "não classificado": as 6 doações
  ao Instituto (mar a ago), o doce de R$ 15,00 de março, e **duas vendas de
  desapego para a Symara que ninguém tinha notado** (R$ 100,00 em 11/06 e
  08/07, iguais à de setembro).

**Aviso novo na mesclagem, e a regra que ele não impõe.** Classificar à mão é
legítimo e às vezes é o único caminho certo — o mesmo texto pode significar
coisas diferentes, como "COLEGIO", que já foi mensalidade e ballet. O problema
nunca foi a prática, foi o silêncio: essa classificação vive só dentro do
lançamento e a mesclagem troca todos os do mês relido. Agora o importador conta
quantas vão se perder e lista as primeiras, para quem está importando decidir o
que vira regra.

Escrevi antes um teste exigindo que **todo** lançamento de extrato classificado
viesse de regra. Ele falhou com 61 casos e estava errado em existir: contradizia
uma decisão já documentada neste arquivo. Trocado pelo aviso, que informa em vez
de proibir.

**Restam 58 lançamentos de extrato sem regra em 2026** (jan a ago), a maioria Pix
com nome de pessoa. Dois deles se repetem todo mês e valem pergunta:
`PIX TRANSF ASSOCIA` (R$ 20,00, todo dia 25) e `PAG TIT INT 299` (valor varia de
R$ 20,00 a R$ 232,63) — este último é o que o alerta do celular vem acusando
como vencido.

### Conta recorrente encerrada: o histórico não sabe que algo acabou (13/09)
A Juliane listou quatro contas e disse: *"pode tirar das próximas contas, não
vou mais pagar essas despesas"* — **oferta à igreja** (R$ 50, dia 18),
**manicure** (R$ 100, dia 18), **PIX TRANSF ASSOCIA** (R$ 20, dia 25) e a
**doação ao Instituto dos Cegos** (R$ 20, dia 27).

`perfilDasRecorrentes()` olha só para trás, e o passado não avisa que algo
acabou: a oferta apareceu em 8 meses seguidos, então continuaria sendo prometida
para sempre. **Prometer gasto que não vai existir é o mesmo erro de prometer
renda que não vem** — só que ao contrário, e faz o mês parecer mais apertado do
que é.

**`configuracoes.json` → `recorrentes_encerradas[]`**: `chave` (a mesma
`CHAVE_RECORRENTE`), `descricao`, `encerrada_em`, `motivo`. Fica na configuração
pelo mesmo motivo dos cartões e das contas cadastradas: "parei de pagar isso" é
decisão que muda, não pode exigir editar código.

**Isto não é `pagamento_suspenso` nem `em_pagamento: false`, e a diferença
importa.** Lá a obrigação continua e o saldo cresce, por isso aquelas telas
mostram o valor à parte com aviso de juros. Aqui não há obrigação nenhuma:
oferta, manicure, associação e doação simplesmente deixam de acontecer. Por isso
a linha some do total e **o valor não aparece em lugar nenhum** — mostrar um
número inventaria uma dívida que não existe.

**O que aparece é o nome.** Uma linha discreta, sem valor, no Painel e no alerta
do celular: *"Não entram mais na previsão, porque você parou de pagar: ..."*. Sem
ela a linha sumiria e, daqui a três meses, ninguém lembraria por quê.

**`encerrada_em` não é decoração.** A projeção só para dali para frente; mês
anterior com extrato incompleto continua podendo projetar o que de fato existia
naquela época.

Efeito em Set/26: a conta recorrente prevista caiu de R$ 3.270,99 para
**R$ 3.080,99**, e o "sai da conta" de R$ 9.566,40 para **R$ 9.376,40** — os
R$ 190,00 exatos das quatro.

3 testes novos, verificados revertendo o filtro (sem ele, 4 falham): as quatro
saem da lista de vencimentos, **o histórico continua conhecendo as quatro** (o
que parou foi a projeção, não o dado), e a tela diz o nome de cada uma em vez de
só sumir com elas. O teste que recalcula o "sai da conta" por fora também
aprendeu a regra, senão ele passaria a divergir da tela.

### A quarta conta: corrente do Bradesco, e o limite que cobrava em silêncio (14/09)
A Juliane mandou o extrato de uma conta que a dashboard **não conhecia**:
**Bradesco, ag. 2389, c/c 555440-3**. Movimento baixíssimo — 6 lançamentos em
dois meses — mas é por ela que sai o **débito automático de alguns cartões
Bradesco**, e o saldo não cobria.

O que o extrato conta, em ordem:

| Data | O quê | Valor |
|---|---|---|
| 16/07 | saldo de abertura, já devendo | −R$ 4,31 |
| 04/08 · 05/08 | IOF e encargo do limite | −R$ 0,23 |
| 17/08 | **débito da fatura do 3987** | −R$ 259,49 |
| 02/09 · 08/09 | IOF e encargo do limite | −R$ 13,59 |
| 14/09 | Pix dela mesma, quitando | +R$ 278,00 |

**Os R$ 259,49 batem exatamente com a fatura 3987 de Ago/26**, que já estava
gravada como paga desde a importação das faturas do Bradesco — a dashboard sabia
que tinha sido paga, não sabia **de onde**. Entra como
`transferencia`/`pagamento_fatura`: as compras já estão lançadas uma a uma.

**O que era invisível são os R$ 13,82 de juros e IOF do limite.** Despesa de
verdade, `encargos_financeiros`, e cara: o encargo saltou de **7,73% para 8,00%
ao mês** entre agosto e setembro — na casa de 150% ao ano. A conta ficou negativa
por quase dois meses por causa de uma fatura de R$ 259,49.

`scripts/importar-extrato-bradesco-cc.js`, com a mesma disciplina dos outros:

- **O PDF imprime "Saldo" sem sinal**, e nesta conta o saldo fica negativo quase
  o tempo todo — cada débito faz o número impresso **subir**. Ler como positivo
  inverteria a conta inteira. Em vez de supor, o script **tenta os dois sinais
  para o saldo inicial e fica com o que reproduz todos os saldos impressos**;
  se nenhum fechar, não grava. Ele descobriu sozinho que a conta começa negativa.
- A descrição quebra em três linhas (`ENCARGOS LIMITE DE CRED` em cima,
  `ENCARGO - 08,00%` embaixo, só o número no meio) — remontada das vizinhas,
  como já era preciso fazer na fatura do Bradesco.

**O teste do boleto duplicado passou a valer para qualquer extrato de conta**
(`/^extrato_/`), não só o do Itaú. Era a mesma armadilha em outra conta:
verificado quebrando de propósito, ele acusa `2026-08-17 R$ 259,49 GASTOS CARTAO
DE CREDITO = fatura 3987 Ago/26`.

A conta entrou em `configuracoes.json` → `contas_origem`, com o que se sabe dela.

### Uma fatura, dois cartões — e a reimportação que somava em vez de substituir (15/09)
A Juliane mandou a **fatura fechada do Bradesco de 15/09**, e ela corrigiu um
número que estava R$ 188,66 barato demais.

O que estava gravado vinha do **extrato "EM ABERTO" de 30/08**: uma foto do
ciclo enquanto ele ainda enchia. A fatura fechada do mesmo ciclo traz as compras
do fim do período (31/08 e 01/09) e o total definitivo.

| | antes (foto de 30/08) | agora (fatura de 15/09) |
|---|---|---|
| 3987 Set/26 | R$ 767,41 · 22 lançamentos | **R$ 887,40 · 25** |
| 3711 Set/26 | R$ 314,90 · 5 lançamentos | **R$ 383,57 · 6** |

**O documento é um só e cobra dois cartões**: o do titular (3987) e o adicional
(3711), cada um com seu bloco e seu subtotal, somando o total da fatura de
R$ 1.270,97. O leitor lia tudo como um cartão só e jogava a compra do adicional
na conta do titular. Agora `ler-faturas-bradesco.py` devolve **uma fatura por
cartão cobrado**, e ganhou uma segunda conferência: **a soma dos subtotais tem
de dar o total impresso** — é o que garante que nenhum bloco ficou de fora.

Três detalhes de leitura que só apareceram com este PDF:

- **`Saldo anterior......... R$ 259,49`** — o resumo preenche o espaço com
  pontos até o valor, e a regex só aceitava espaço. Sem achar o saldo, a
  identidade da fatura não fechava e o importador recusava um PDF perfeito.
- **`Número do Cartão 4532 XXXX XXXX 3987` é cabeçalho de página**, não início
  de bloco. Casar nele abria um bloco vazio antes do primeiro cartão.
- **O pagamento da fatura passada vem impresso antes do primeiro marcador**, o
  que abre um bloco implícito do mesmo cartão. Blocos do mesmo número são
  juntados no fim.

**O subtotal impresso do titular já inclui o saldo anterior**: 259,49 + 627,91 =
887,40. Então a identidade de sempre (`total = saldo anterior + soma dos
lançamentos`) vale por cartão, e o saldo anterior fica com o cartão que carregava
a dívida — o bloco que traz o pagamento. Ratear entre os dois seria inventar um
número que a fatura não diz.

**Dois bugs de verdade no importador, e o segundo eu mesmo criei:**

1. **A reimportação somava as duas leituras.** O cabeçalho da fatura já era
   substituído; os lançamentos não. Com a fatura fechada chegando por cima da
   foto em aberto, o 3711 passou a somar **R$ 698,47 numa fatura de R$ 383,57**.
   Corrigido com a mesma regra do importador do extrato: o que é relido é
   substituído, não acrescentado.
2. **A purga na ordem errada esvaziou 9 faturas.** Na primeira tentativa ela
   rodava no fim, depois de `existentes` já ter sido montado — então todo id
   repetido era tratado como "já existe", o lançamento novo não chegava a ser
   gerado, e a purga apagava o antigo sem repor. O 0013 inteiro e três faturas do
   3987 ficaram com cabeçalho e **zero compra**. A purga passou para antes de
   `existentes`, que é onde a ordem faz sentido.

E **o extrato em aberto é descartado quando a fatura fechada do mesmo ciclo
chega** — com aviso dizendo de qual valor para qual. Sem isso, a foto de 30/08
continuaria mandando sobre a fatura de 15/09.

2 testes novos, verificados quebrando o dado dos dois jeitos (5 testes falham em
cada): a soma dos lançamentos de uma fatura nunca passa do que ela cobra, e
nenhuma fatura já importada fica sem lançamento depois de reimportar. São as
formas genéricas dos dois erros.

Efeito em Set/26: o "sai da conta" foi de R$ 9.376,40 para **R$ 9.578,65**.

### A chave da recorrente fundia boletos diferentes num só (17/09)
A Juliane cobrou o alerta: *"não existe nenhum título de 134,00, nem nada pago
em 06/09"*. Ela estava certa, e o erro era meu: **nunca existiu um boleto de
R$ 134,00 com o nome "PAG TIT INT 299"** — aquela linha era a fusão de três
boletos distintos.

`CHAVE_RECORRENTE` descartava **todo dígito** da descrição. Isso existe por um
motivo real: o Itaú cola a data no fim do texto (`PIX TRANSF ASSOCIA25/01`), e
sem descartá-la a mesma conta viraria uma chave nova todo mês. Só que o código
depois de `PAG TIT INT` **é dado, não ruído** — é o banco de liquidação, e este
arquivo já documentava que beneficiários diferentes usam códigos diferentes.
Descartando os dígitos, `PAG TIT INT 299`, `PAG TIT INT 364` e `PAG TIT INT 001`
viravam o perfil único `pag tit int`, com 9 lançamentos de 4 meses:

- a **mediana** dos 9 dava **R$ 134,00** — que é o valor do **364**, não do 299;
- o **rótulo** vinha do `exemplo`, o primeiro do grupo, que era o **299**;
- o **dia** vinha da mediana dos dias dos três, dando **06**.

Ou seja: nome de um boleto, valor de outro, dia de nenhum. A tela prometia todo
mês uma conta que não existe em lugar nenhum. Era um número inventado com
aparência de fato — exatamente o que a "regra de ouro dos dados" existe para
impedir, só que por um caminho que ela não previa.

A chave agora descarta **só a data colada no fim** (`\d{2}/\d{2}$`) e preserva o
resto dos dígitos. Corrigido nos três lugares que têm cópia própria da regra:
`public/index.html`, `scripts/contas-a-vencer.js` e a que o
`testar-dashboard.js` recalcula por fora.

Efeito: o 299 passou a projetar **R$ 68,55 no dia 5** (mediana só dele), o 364
caiu abaixo do piso de 3 meses e sumiu da projeção, e o "já venceu" de setembro
foi de R$ 1.529,65 para **R$ 1.464,20**.

Teste novo, na forma genérica do erro e **verificado revertendo a correção**
(sem ela, 4 testes falham e o novo nomeia as duas fusões): **duas descrições que
o extrato distingue não podem cair na mesma chave** — comparando o texto sem a
data, e sem caixa, para que variações como `PIX TRANSF Isabela` x
`PIX TRANSF ISABELA` continuem sendo a mesma conta de propósito.

**O que os três boletos são continua sem resposta**, e agora dá para perguntar
direito, um de cada vez:

| Código | Quando | Quanto |
|---|---|---|
| **299** | 05/02, 05/03, 06/04, 05/05 | R$ 232,63 · 20,00 · 78,80 · 58,29 — **R$ 389,72** |
| **364** | 30/03, 28/04 | R$ 134,00 · 134,00 — **R$ 268,00** |
| **001** (fora da faixa da escola) | 02/03, 31/03, 30/04 | R$ 139,40 · 139,40 · 154,73 — **R$ 433,53** |

**Os três pararam de aparecer, e o extrato cobre esse período inteiro** (jun,
jul e ago vão até o último dia do mês). O 299 não aparece desde 05/05. Isso é
forte indício de que acabaram — mas "acabou" é decisão dela, não dedução minha:
enquanto ela não confirmar, o 299 segue sendo projetado, e o caminho de tirá-lo
é `recorrentes_encerradas[]`, não apagar dado.

**Fica a pergunta de desenho, ainda em aberto:** conta que não aparece há 4
meses continuar sendo prometida é o mesmo erro de prometer renda que não vem.
`perfilDasRecorrentes()` só olha para trás e não tem noção de "parou". Um piso
de recência resolveria sozinho os casos como este — mas mexeria em toda conta
projetada, então precisa ser decidido com ela antes.

### Só é recorrente o que ela informa ou o que é reconhecidamente rotina (17/09)
Logo depois da correção acima, a Juliane fechou a regra: *"você só vai colocar
como recorrente o que eu informar ou as despesas que você entende que são gastos
de rotina"*.

Isso resolve a causa, não o sintoma. O critério até aqui era puramente
estatístico — **repetiu-se em 3 meses, vira conta a pagar** — e estatística não
sabe o que é conta. `PAG TIT INT 299` apareceu em 4 meses e virou cobrança
mensal de um boleto que ninguém identificou; `PIX TRANSF Isabela` (3 meses,
R$ 10 a R$ 40) virou outra. Nenhum dos dois é conta: são Pix que se repetiram.

**`PROJETAVEL(t)` = o lançamento tem categoria e ela não é `nao_classificado`.**
Lançamento em `nao_classificado` é, por definição, o que a dashboard **não sabe
o que é** — projetá-lo é palpite com cara de conta a pagar, no lugar mais caro
possível: o número que ela usa para decidir o que pagar no mês. Aplicado em
`perfilDasRecorrentes()` nos três lugares que têm cópia da regra (dashboard,
`contas-a-vencer.js`, e os dois recálculos independentes da suíte).

**Conta de rotina sem 3 meses de histórico não fica órfã**: o caminho é
`contas_recorrentes[]`, que é exatamente "ela informando" — foi assim que a
Stima entrou.

**O valor sai do total, o nome não sai da tela.** Linha nova, sem número, no
Painel e no alerta do celular: *"Não entram na previsão, porque a dashboard não
sabe o que são: PAG TIT INT 299 (4 meses) · PIX TRANSF Isabela08/01 (3 meses)"*.
Ela é útil nos dois sentidos — impede a conta de sumir em silêncio e é a lista
do que vale a pena identificar, porque **no dia em que ganhar categoria, passa a
contar sozinho**. Sem valor de propósito: mostrar um número seria exatamente o
palpite que a regra acabou de recusar. Conta já declarada em
`recorrentes_encerradas` não aparece aqui — tem bloco próprio, e estar nos dois
é ruído sobre a mesma linha.

3 testes novos, **verificados revertendo o filtro** (sem ele, 4 falham e o novo
nomeia os dois culpados): nenhuma recorrente sem classificação entra na
previsão, o que ficou de fora aparece pelo nome, e essa linha não mostra valor
em reais.

Efeito: o "já venceu" de setembro caiu para **R$ 1.395,65** (só as três faturas
de 15/09, todas fato), e o "sai da conta" de Set/26 de R$ 9.513,20 para
**R$ 9.433,20**.

### A fatura do Itaú em PDF, e a conferência que rodava tarde demais (21/09)
A Juliane passou a mandar a fatura pelo **PDF do app**, e só existia leitura do
XLSX do internet banking. `conferir-fatura.js` respondia "não é fatura", e o
3794 de Out/26 seguia gravado com **R$ 4.904,34 e 7 lançamentos** — a foto de um
ciclo ainda em aberto. A fatura fechada diz **R$ 15.128,18 com 28**.

`ler-fatura-itau-pdf.js`, com as duas disciplinas de sempre:

- **A coluna sai do próprio documento.** O PDF imprime duas tabelas lado a lado
  na mesma linha de texto; a linha de cabeçalho que traz **dois "DATA"** diz
  onde a segunda começa. Medir a olho numa linha de compra qualquer daria certo
  até a primeira fatura com outro desenho.
- **Desembaralhar é página por página.** Concatenar a esquerda do documento
  inteiro e só então a direita parece equivalente e não é: a seção aberta no fim
  da coluna direita da página 1 continua na esquerda da página 2, e com as
  páginas embaralhadas a continuação herda a seção errada — foi o que jogou a
  "Redução Mensalidade" de produtos e serviços para dentro de compras.
- **Duas conferências, e sem elas nada é devolvido:** a soma dos lançamentos
  tem de dar o `Total dos lançamentos atuais` impresso, e o resumo tem de fechar
  consigo mesmo (`anterior + pagamento + financiado + atuais = total`). A fatura
  de 01/10 fecha ao centavo, seção por seção.
- **"Compras parceladas - próximas faturas" fica de fora**: é parcela que ainda
  vai ser cobrada, e somá-la dobraria a fatura.
- **O repasse de IOF é a única linha de valor sem data** — sem tratá-la à parte,
  faltavam exatamente R$ 13,31 e a fatura não fechava.

`importar-fatura-itau-pdf.js` grava com a disciplina aprendida no Bradesco (o
relido é substituído; a purga vem antes do índice de ids) e **religa as parcelas
da mesma compra pela chave de `chaveDaCompra`** — sem isso a parcela 4/12 lida
do PDF vira uma compra própria e a numeração aparece com buraco.

**Bug real no importador do extrato, achado nesta importação:** `conferirSaldos()`
rodava **depois** do corte de sobreposição. O extrato mais antigo é podado das
linhas que o mais novo já cobre, então ele era conferido com os saldos impressos
contra uma fração dos movimentos: **14 de 20 intervalos "não fechavam"**, e a
guarda que recusa gravar teria barrado um arquivo perfeito. Pior: a guarda
deixava de distinguir leitura errada de corte legítimo. A conferência passou a
ser feita **sobre o arquivo como foi lido**, e voltou ao resíduo conhecido de
R$ 0,05.

Regra nova: **Tokio Marine** no extrato → `seguro`/Família. Mesmo caso do
Transurc — já era decisão dela (23/08), mas só existia em
`regras-classificacao.json`, que vale para a fatura.

### A conta da Benetti UP entrou, e ela é outro caixa (21/09)
Eu disse à Juliane que a Benetti UP não estava integrada, e ela corrigiu: *"a
Benetti up já está na Dashboard, como uma leitura separada, acredito que já
carreguei vários dados dela aqui"*. **Ela estava certa, e eu estava impreciso
de um jeito que importa.**

O que já existia: a Benetti UP como **leitura separada** — o seletor do topo, a
pessoa cadastrada, o campo `ambito` em **456 lançamentos de 2026, R$ 195.979**.
O que faltava era a **conta bancária**: todos esses 456 entraram pelo cartão
pessoal (439) e pelo extrato do Itaú (17), ou seja, só o que vaza para o lado
dela. O efeito era uma empresa que só aparecia **gastando** — R$ 173 mil de
tráfego pago e **nenhuma entrada**, porque a receita das processadoras (SHPP,
depois Maree) cai na conta PJ do Nubank, que não era lida.

E ela já tinha mandado esse extrato, em 30/08. Naquela vez ele foi analisado
direto do PDF e o resultado virou texto neste arquivo — **nunca virou dado**. A
memória dela estava certa: o arquivo passou e não deixou rastro.

`importar-extrato-nubank-pj.js` (ag. 0001, c/c 977727920-1). O risco desta
fonte é contar duas vezes, e é maior que em qualquer outra: quase todo movimento
grande tem a outra ponta já lançada.

| Movimento | Como entra | Por quê |
|---|---|---|
| Pix para o Itaú Holding | `transferencia`/`pagamento_fatura` | as compras já estão na fatura do 0442/3794, uma a uma |
| Empresa → Juliane | `despesa`/`pro_labore` | o extrato pessoal já lança a entrada como receita dela; marcar transferência dos dois lados daria ao consolidado uma receita que não existe |
| Juliane → empresa | `transferencia`/`aporte_na_empresa` | é capital, não venda — chamar de receita inventaria faturamento feito do bolso dela |
| Maree / SHPP | `receita`/`vendas` | **a receita de verdade da empresa**, que nunca tinha existido na base |

E a conferência de sempre: o saldo impresso tem de ser reproduzido pelos
movimentos lidos, dia a dia e no total. Fecha nos 12 movimentos.

**A consequência que quase passou batido: o Painel não filtra por âmbito.** Sem
mais nada, as saídas da empresa (DAS, contabilidade, retirada) entrariam no
"sai da conta" — **R$ 632,67 em Set/26, R$ 3.059,19 em Ago/26** cobrados do
salário da Juliane por um boleto que a empresa pagou. `ORIGENS_DE_OUTRO_CAIXA` /
`saiDoCaixaDela(t)`: a conta PJ sai do "sai da conta", da projeção de recorrente
e da lista do que falta identificar — **e continua inteira em Lançamentos, Para
Onde Vai e Fluxo de Caixa sob o âmbito Benetti UP.** É a mesma decisão, e o
mesmo motivo, que já tirava do Painel a fatura quitada pela Benetti UP e a conta
recorrente com `paga_por` diferente de `juliane`. O discriminador é a **conta de
onde o dinheiro saiu**, que é o que `origem` diz.

**Escrevi antes um teste que não testava nada** — a asserção era
`Math.abs(naTela − naTela) < 0.01`, sempre verdadeira. Refeito com prova dos
dois lados: a tela bate com a soma que exclui a conta da empresa e **não** bate
com a que a inclui, mais um teste de que o lançamento continua existindo em
Lançamentos (tirar do caixa dela não pode significar sumir com ele). Verificado
revertendo o filtro: sem ele, **6 testes falham**.

Primeiros números da empresa pela conta dela (jul–set/26): receita
**R$ 18.615,28**, despesa operacional **R$ 3.770,86**. Transferência fica fora
dos dois, de propósito — é dinheiro que a outra ponta já lança.

### O Black também foi refinanciado, em junho — e o contrato nunca foi cadastrado (21/09)
A Juliane perguntou se tinha negociado a fatura do Black, quando e como. Tinha:
**26/06/2026**, e o dado fecha sozinho.

| | |
|---|---|
| Fatura de Jun/26 | R$ 5.801,78 |
| Entrada paga no dia (`Pagamento Parcelamento Fatura`) | −R$ 551,17 |
| Saldo refinanciado | **R$ 5.250,61** ← é exatamente o `saldo_anterior` da fatura de Jul/26 |
| IOF (`Iof Refinanciamento De Fatura`) | + R$ 54,88 |
| Valor financiado (`Credito Por Parcelamento`) | **R$ 5.305,49** ← bate ao centavo |
| Parcelas | 4 × R$ 1.769,36, venc. Jul a Out/26 |

**Custo: R$ 1.826,83 por uma dívida de R$ 5.250,61** — CET de ~13,1% ao mês,
**~338,7% ao ano**. É a mesma taxa do parcelamento do 0442 (338,31%), o que é
uma boa checagem cruzada: mesmo produto, mesma taxa, lidos de fontes diferentes.

**O que aconteceu depois é o que importa hoje:** só a **1ª parcela** foi de fato
paga (a fatura de julho foi paga em parte, R$ 2.335,89 de R$ 6.917,01). A 2ª e a
3ª foram **cobradas** dentro das faturas de Ago/26 (R$ 10.667,16) e Set/26, que
seguem em aberto. E em 18/08 o Itaú cobrou **Multa R$ 136,67 + Juros de Mora
R$ 20,50 + Encargos Refinanciamento R$ 632,37 = R$ 789,54** num mês só, pelo
atraso da parcela.

**O contrato nunca foi cadastrado em Dívidas.** O parcelamento do 0442 (09/09)
foi registrado com os três passos que este arquivo manda fazer juntos; o do Black
(junho) só existia como lançamento. Corrigido —
`refin_fatura_4846_jun26`, `em_pagamento: false` (a parcela vem dentro da fatura
do Black, cujo pagamento está parado).

**O saldo cadastrado é só a 4ª parcela (R$ 1.769,36), e isso é de propósito.**
Aqui está a diferença entre este caso e o do 0442, que vale para o próximo:

- No **0442** o parcelamento aconteceu e **nenhuma parcela tinha sido cobrada
  ainda** — o dinheiro sairia do cartão e sumiria da tela. Por isso
  `financiado_em_parcelas` no cabeçalho e o contrato inteiro em Dívidas.
- No **Black**, 3 das 4 parcelas **já foram cobradas** e estão visíveis como
  lançamentos dentro de faturas em aberto. Nada está sumindo. Cadastrar o
  contrato inteiro (R$ 7.077,44) somaria ao saldo do cartão um dinheiro que já
  está lá dentro — **dupla contagem**. Por isso o `financiado_em_parcelas` da
  fatura de Jun/26 **não** foi preenchido retroativamente: ele existe para
  impedir dinheiro de evaporar, e aqui não há evaporação.

**Pendência que a dashboard não resolve sozinha:** a fatura de **Set/26 do Black
está com `saldo_anterior: 0`** apesar de a de Ago/26 (R$ 10.667,16) não ter sido
paga — é uma foto de ciclo em aberto, não a fatura fechada. O saldo real do Black
é maior do que a tela mostra, e só a fatura fechada de outubro resolve (ela traz
também a 4ª parcela do refinanciamento).

### Quatro faturas parceladas, não uma — e a descrição cortada que partia a compra (21/09)
A Juliane perguntou: *"eu parcelei a fatura de junho, foi isso, né? As próximas
faturas eu também parcelei? Ou eu te mandei um print da tela?"*. Duas perguntas
diferentes — o que aconteceu, e **de onde o dado veio**. As duas importam.

**Foram quatro parcelamentos, em três cartões:**

| Cartão | Quando | Financiado | Parcelas | Entrada | Custo |
|---|---|---|---|---|---|
| **4846 Black** | 26/06/2026 | R$ 5.305,49 | 4× R$ 1.769,36 | R$ 551,17 | R$ 1.771,95 |
| **3794 Azul** | 01/07/2026 | R$ 11.417,46 | 4× R$ 3.880,96 | — | R$ 4.106,38 |
| **3794 Azul** | 31/07/2026 | R$ 1.678,29 | 4× R$ 534,21 | R$ 8.000,00 | R$ 458,55 |
| **0442 Infinite** | 09/09/2026 | R$ 1.251,56 | 4× R$ 408,13 | R$ 131,38 | R$ 380,96 |

No Black foi **só a de junho**: julho, agosto e setembro não foram parceladas —
ficaram em aberto, que é outra coisa e mais cara.

**A procedência é diferente em cada caso, e isso nunca tinha sido dito:**
só o **0442** veio de um comprovante que ela mandou (09/09, conferido linha por
linha). Os **três outros** eu li da própria fatura — o Itaú imprime
`Credito Por Parcelamento` e `Parcela De Refinanciamento` como lançamentos. Ou
seja: **ela nunca confirmou os três**, e eles entraram na base sem passar por
ela. Não é erro — a fatura é fonte primária —, mas a tela nunca disse de onde
cada número veio, e a pergunta dela mostra que essa distinção faz falta.

**Defeito de verdade, achado ao responder isso, e eu mesmo tinha acabado de
introduzir metade dele:** o PDF da fatura **corta a descrição na largura da
coluna** e o XLSX não. `Parcela De Refinanciamento` vira `PARCELA DE REF`,
`Parc Fatura Seg` vira `PARC FATURA SE`. Como a descrição entra na chave que
agrupa as parcelas, a parcela lida do PDF ganhava `id_compra` próprio: **a mesma
compra virava duas**, a numeração aparecia com buraco e a previsão de quitação
saía errada.

**E o teste que eu escrevi para isso achou o mesmo defeito, já existente, no
Bradesco** — `importar-faturas-bradesco.py` fazia `id_compra = 'compra_' + id`,
um por lançamento, sem nunca ligar as parcelas entre faturas. As 2/4, 3/4 e 4/4
do mesmo aparelho comprado em 19/11 eram três compras distintas. **34 parcelas
religadas.**

Por que nenhum teste pegava: os de numeração checam **dentro** de cada grupo, e
um grupo com uma parcela só é trivialmente sequencial. A forma genérica do erro
é outra, e é essa que virou teste: **mesmo cartão, mesma data de compra, mesmo
número de parcelas e descrições em que uma é começo da outra = uma compra só.**
O teste de prefixo é o que impede fundir duas compras de verdade que apenas
coincidam em data e prazo. Verificado revertendo a correção: sem ela, 4 testes
falham.

### Parcelamento de fatura não autorizado: compilado para o Itaú (21/09)
A Juliane relatou: *"o Itaú está parcelando automaticamente as minhas faturas e
isso não foi autorizado por mim"*. Ela **reconhece o de 26/06 no Black** — o
primeiro, feito por ela — e **não se recorda** dos posteriores. Vai mandar as
faturas que faltam e pediu um compilado para pedir cancelamento e ressarcimento.

Isso muda a natureza do trabalho: deixa de ser registro contábil e passa a ser
**peça de reclamação**. Daí as regras deste bloco.

**O que ela sabe mora na configuração, não no código nem no relatório.**
`configuracoes.json` → `parcelamentos_fatura[]`, com `autorizado: true | false |
null`. O script **não decide** o que foi autorizado: `null` é "ela não se
recorda", e é diferente de `false`. Deduzir autorização a partir do documento
seria inventar o fato central da reclamação.

**`scripts/parcelamentos-de-fatura.js`** (só leitura) reúne, por evento:
a fatura parcelada, a entrada, a dívida refinanciada, o IOF, as parcelas, o
custo, a **taxa efetiva calculada das próprias parcelas** (não copiada), quais
parcelas já foram cobradas e em qual fatura, e quais ainda vêm — que é o que dá
para cancelar antes de ser lançado.

**A fatura é identificada pela aritmética, não pela data.** Se
`entrada + dívida refinanciada` dá o total de uma fatura ao centavo, é aquela — e
isso de quebra **prova que a fatura inteira foi parcelada**. Foi assim que o
parcelamento de 31/07 se revelou da fatura de **Ago/26** (venc. 03/08), não da
de julho: R$ 8.000,00 + R$ 1.661,17 = R$ 9.661,17, exato. Quando não fecha, o
relatório **diz que não fecha** em vez de escolher a mais próxima em silêncio —
a força da prova é diferente, e a peça tem de dizer qual das duas tem.

Os quatro, em ordem:

| Cartão | Data | Dívida | Parcelas | Custo | Taxa | Reconhecido? |
|---|---|---|---|---|---|---|
| Black 4846 | 26/06 | R$ 5.250,61 | 4× 1.769,36 | R$ 1.826,83 | 338,67% a.a. | **sim** |
| Azul 3794 | 01/07 | R$ 11.417,46 | 4× 3.880,96 | R$ 4.106,38 | **358,56% a.a.** | não |
| Azul 3794 | 31/07 | R$ 1.661,17 | 4× 534,21 | R$ 475,67 | 245,80% a.a. | não |
| Infinite 0442 | 09/09 | R$ 1.251,56 | 4× 408,13 | R$ 380,96 | 271,09% a.a. | sim (comprovante) |

**R$ 6.789,84 de custo total**, dos quais **R$ 4.582,05 nos dois que ela não
reconhece**, e **R$ 4.949,38 de parcelas não reconhecidas ainda não cobradas** —
esse último é o número que importa para o pedido de cancelamento, porque ainda
não virou cobrança.

Mais **R$ 791,87** de multa, mora e encargos de refinanciamento cobrados depois.
Ficam em bloco separado de propósito: não são o preço do crédito, são o preço de
ele ter atrasado.

**Dois cuidados que valem para a próxima vez:**

1. **O compilado não pode se contradizer.** A primeira versão listava como
   "fatura faltando" duas faturas que ela mesma tinha acabado de identificar pela
   aritmética — a checagem de pendência ainda exigia vencimento igual à data do
   parcelamento. Num relatório que vai para o banco, isso destrói a credibilidade
   do resto.
2. **Parcelamento sem lançamento nenhum também conta.** O do 0442 ainda não teve
   parcela cobrada (a fatura de outubro não chegou), então não existe
   `Credito Por Parcelamento` para achar. Ele entra pelo `financiado_em_parcelas`
   da fatura + o contrato em Dívidas. Sem isso o compilado diria "3
   parcelamentos" havendo 4 — e num pedido de ressarcimento, faltar um é pior que
   errar um valor.

**A procedência de cada número está na peça**, porque ela perguntou e a distinção
importa: só o 0442 veio de comprovante que ela mandou; os outros três foram lidos
das próprias faturas e **nunca tinham sido confirmados por ela**.

### "PARC AUTOMATIC": o parcelamento automático apareceu no dado (21/09)
A Juliane mandou as faturas de **Ago/26 e Set/26 do Black**, e a de setembro tem
o lançamento que dá nome ao problema:

```
05/09   PARC AUTOMATIC 01/12                    1.734,19
05/09   CREDITO PARC AUTOMATICO                -9.700,82
05/09   IOF REFINANCIAMENTO DE                    219,37
```

**R$ 9.481,45 de dívida + R$ 219,37 de IOF, em 12× R$ 1.734,19.** Desembolso de
**R$ 20.810,28** — custo de **R$ 11.328,83**, mais que a própria dívida. Taxa
efetiva de **14,80% ao mês, 423,93% ao ano**: o crédito mais caro de todos os
cinco parcelamentos, e o único em 12 parcelas. **R$ 19.076,09 ainda não foram
cobrados** — é o que dá para cancelar.

O nome do lançamento é literalmente "automático". A fatura ainda traz, à parte,
"Parcelamento de fatura · Contratação em 26/06/2026 - Parcela 3/4", confirmando
pelo próprio banco o parcelamento que ela reconhece.

**Quatro defeitos reais no leitor de PDF, e os dois primeiros escondiam dinheiro:**

1. **A identidade do resumo estava errada desde que foi escrita.** Eu usava
   `anterior + pagamento + financiado + atuais = total`. **O saldo financiado
   não é uma parcela a mais: ele É `anterior + pagamento`** — somá-lo de novo
   conta a dívida velha duas vezes. Passou na primeira fatura só porque lá o
   saldo financiado era zero. A identidade certa é
   **`saldo financiado + lançamentos atuais + encargos = total`**, e o saldo
   financiado ganhou conferência própria.
2. **O corte de coluna da página 2 vinha da página 1.** Só a página 1 tem a
   linha de cabeçalho com dois "DATA"; as outras herdavam o corte dela, o texto
   da direita entrava colado na linha da esquerda e o lançamento deixava de
   casar. **R$ 3.875,81 sumiam de uma fatura só — incluindo o parcelamento
   automático inteiro.** Agora, sem cabeçalho, a página descobre a **calha**: a
   faixa vertical em branco entre as duas tabelas, aceita a 98% (exigir 100%
   falha por causa de uma descrição longa que a atravessa).
3. **O corte era na borda esquerda da calha**, e um valor que encostava nela
   perdia o último dígito — `1.734,19` virava `1.734,1` e o lançamento sumia
   inteiro. O corte é o **fim** da calha: onde a coluna direita começa, que é o
   mesmo que o segundo "DATA" devolve.
4. **Os encargos do mês não eram lidos.** Juros do rotativo, mora, multa e IOF
   de financiamento têm seção própria e **ficam de fora** do "Total dos
   lançamentos atuais", mas entram no total a pagar: R$ 848,60 numa fatura e
   R$ 818,31 na outra ficariam invisíveis. Agora viram lançamento
   `encargos_financeiros`, com conferência contra o subtotal impresso.

**Duas armadilhas na seção de encargos**, e a segunda só apareceu porque a
primeira foi corrigida: ela **não termina sozinha** (depois vêm "Simulação de
compras", "Limite de crédito", tudo com número), e quando todos os encargos são
zero o Itaú **nem imprime o subtotal**, então não há onde parar. Resultado da
primeira versão: R$ 152 mil de "encargo" numa fatura que não tinha nenhum. Duas
guardas: a seção fecha no próprio subtotal, e **só vira encargo o que tem rótulo
conhecido**. Mais uma terceira: ler encargo sem que a fatura imprima o subtotal
**recusa a fatura** — não há contra o que conferir.

**O PDF de Ago/26 vem com a camada de texto degradada** — o `pdftotext` injeta
espaço dentro de palavras e números (`Lan çamen tos`, `10.66 7,16`, `28/ 07`,
`Car tã o`). O conserto (juntar espaço entre dígitos, e procurar rótulo num
texto sem espaço, lendo o valor do texto original para não colar o número da
coluna vizinha) recuperou o cabeçalho inteiro, que **fecha**: total
R$ 10.667,16, anterior R$ 6.917,01, pagamento R$ 2.252,37 em 04/08, saldo
financiado R$ 4.664,64, lançamentos R$ 5.184,21, encargos R$ 818,31.

**Mas a itemização não fecha — faltam R$ 627,07 — e por isso a fatura foi
recusada.** Está certo recusar: é peça de reclamação contra o banco, e um
número inventado ali custa mais caro do que a lacuna. `-raw` não resolve
(recupera as palavras mas funde as duas colunas na mesma linha). **Pedir essa
fatura em XLS**, ou um PDF baixado de novo.

**O que as duas faturas corrigiram no dado gravado:** a de Set/26 do Black
estava com **R$ 3.197,56** (foto de ciclo em aberto) e é **R$ 6.284,18**; e as
faturas de Ago e Set constavam como **não pagas**, quando houve pagamento de
**R$ 2.252,37 em 04/08** e **R$ 1.066,72 em 04/09**.

Passa a haver **5 parcelamentos**: R$ 29.062,25 de dívida refinanciada,
**R$ 18.118,67 de custo**, dos quais **R$ 15.910,88 nos quatro que ela não
reconhece**, e **R$ 24.025,47 de parcelas não reconhecidas ainda não cobradas**.

### As 4 faturas do Black em XLSX: o Itaú cancelou o parcelamento automático (21/09)
A Juliane mandou as faturas do Black (4846) de **jul, ago, set e out/26 em
XLSX** — formato nativo, que o importador já lia. Três resultados, em ordem de
importância.

**1. As três já gravadas BATERAM.** `conferir-fatura.js` respondeu "já gravada,
e o conteúdo bate" para jul, ago e set — o que **confirma por fonte
independente** a leitura do PDF feita horas antes, inclusive a de agosto que o
leitor tinha recusado por faltar R$ 627,07 na itemização. A recusa foi prudente,
não paranoia: o cabeçalho que eu tinha recuperado estava certo, e agora a
itemização veio do arquivo certo.

**2. Em 21/09 o próprio Itaú CANCELOU o parcelamento automático**, integralmente.
A fatura de Out/26 traz:

```
04/09   Parc Automatico 2/12 ... 12/12     +19.076,09   (antecipa as 11 restantes)
21/09   Canc Credito Parc Cp               + 9.700,82   (estorna o crédito que o criou)
21/09   Canc Parc De Ref Cp  1/12 ... 12/12 −20.810,28  (cancela as 12 parcelas)
21/09   Estorno Iof                        −   219,37
```

Soma das três pontas com o que foi lançado em Set/26: **exatamente zero**. O
principal, as 12 parcelas e o IOF voltaram todos. **R$ 11.328,83 de custo
revertidos** sem que ela pedisse — a cobrança existiu e vale citar na
reclamação, mas não há o que estornar aqui.

Para o compilado saber disso, `parcelamentos-de-fatura.js` passou a casar cada
parcelamento com o seu cancelamento **pelo valor do crédito**, não pela data (o
cancelamento vem meses depois, em outra fatura). E só chama de **reversão
integral** quando as **três pontas** voltaram — crédito, todas as parcelas e o
IOF. Parcial é outra coisa, e numa peça de reclamação confundir as duas seria
grave.

**3. Quatro defeitos que só apareceram porque o dado novo os expôs**, e três
deles estavam na tela, não no importador:

- **`Parc Automatico` caía como `despesa`.** A regex de dívida parcelada não
  conhecia esse nome, então as 12 parcelas entravam como consumo e inflavam o
  mês em **R$ 20.810,28** de gasto que não existe — as compras que geraram a
  dívida já foram contadas uma a uma.
- **O primeiro estorno POSITIVO da base.** `Canc Credito Parc Cp` é +R$ 9.700,82
  porque desfaz um crédito (negativo). Enquanto todo estorno era negativo,
  "separar por sinal" e "separar por natureza" davam o mesmo número. Passaram a
  divergir, e **duas visões de Para Onde Vai somavam esse estorno como se fosse
  compra** — `filter(t => t.valor > 0)` em vez de `natureza === 'despesa' &&
  valor > 0`. Corrigido nas duas (eram bases separadas; consertar uma não
  consertava a outra) e também nos recálculos da suíte, que tinham o mesmo
  critério frouxo.
- **O teste "estorno bate com os negativos" quebrou com razão**, e afrouxá-lo
  seria errado. Virou uma afirmação mais forte e verdadeira: **estorno positivo
  só existe para cancelar crédito de parcelamento** — qualquer outro é erro.
- **O teste "nenhum contrato com duas parcelas no mesmo mês" também quebrou com
  razão**: as 11 parcelas antecipadas caem juntas em Out/26. Não é duplicação, é
  a reversão. A exceção é explícita e estreita — só vale para parcela que tem
  cancelamento correspondente no **mesmo mês**, e elas somam zero com ele.

**O 0442 e o 3794 continuam sem confirmação dela**, e o compilado diz o que
falta: as parcelas do 3794 que ainda não foram cobradas, as 4 do 0442, e a
fatura que o parcelamento de 01/07 quitou (a aritmética não fecha com nenhuma
importada).

Números atuais: **5 parcelamentos**, R$ 29.062,25 de dívida refinanciada,
**R$ 6.789,84 de custo ainda vivo** (dos quais R$ 4.582,05 nos não
reconhecidos), **R$ 4.949,38 de parcelas não reconhecidas ainda não cobradas**,
e **R$ 11.328,83 já revertidos pelo próprio banco**.

### "Fatura Paga" não quer dizer quitada — e o saldo que rola contado 3 vezes (22/09)
A Juliane perguntou: *"os parcelamentos do cartão azul estão corretos, eu estou
reparcelando mesmo... mas no Black ficou algum parcelamento pra trás?"*.
Responder isso exigiu olhar o Black inteiro, e o que apareceu não foi
parcelamento pendente — foi **dívida escondida por um rótulo**.

**Os dois parcelamentos do 3794 são dela.** `autorizado: true` nos dois, com a
frase dela na `observacao`. O compilado para o banco mudou de figura: com o
automático do Black cancelado pelo próprio Itaú e o Azul reconhecido, o custo
"não reconhecido" caiu de R$ 15.910,88 para **R$ 0,00**. A peça continua
existindo como registro do que foi cobrado, não como pedido.

**No Black não ficou parcelamento nenhum para trás:** o refinanciamento de
26/06 fechou as 4 parcelas (Jul, Ago, Set e **Out/26**), e o `PARC AUTOMATIC`
de 04/09 foi cancelado integralmente em 21/09. O contrato
`refin_fatura_4846_jun26` foi **encerrado** (`montante: 0`): com a 4ª parcela
já cobrada, as quatro estão visíveis dentro das faturas, e manter saldo no
contrato contaria o mesmo dinheiro duas vezes. Era exatamente o que a
`observacao` dele já mandava fazer no dia em que a fatura de outubro chegasse.

**O rótulo do XLSX mentia, e o importador acreditava.** O cabeçalho escreve só
`"Fatura Paga - Agosto/2026"`, sem valor, e o importador traduzia isso como
`pago = total`. As faturas do Black provam o contrário:

| Fatura | rótulo dizia | foi pago de verdade | rolou |
|---|---|---|---|
| Jul/26 | R$ 6.917,01 | **R$ 2.252,37** | R$ 4.664,64 |
| Ago/26 | R$ 10.667,16 | **R$ 1.066,72** | R$ 9.600,44 |

"Fatura Paga" quer dizer **"esta já não é a atual"**, não "foi quitada".

- **Quem sabe quanto foi pago é a fatura seguinte**: `pago desta = total desta −
  saldo anterior da seguinte`. Confere ao centavo com o `Pagamento Debito
  Minimo` impresso dentro dela — duas leituras independentes do mesmo fato.
- **Só corrige para baixo.** O caminho contrário (a seguinte trazer menos saldo
  do que o rótulo sugeria) não prova pagamento: crédito, estorno e cancelamento
  de parcelamento também reduzem saldo. Fica anotado para conferir.
- **Três guardas, e uma delas evita um erro caro:** fatura quitada **por
  parcelamento** não ficou em aberto — o saldo que rola é a dívida refinanciada,
  que já é cobrada em parcelas do outro lado. O Itaú nomeia a linha
  (`Pagamento Parcelamento Fatura`, não `Pagamento Debito Minimo`), e é por esse
  nome que a correção se abstém. Sem isso a fatura de **Jun/26** abriria um
  buraco de R$ 5.250,61 que já está dentro das parcelas. É documento, não
  aritmética: as duas situações deixam saldo na fatura seguinte.
- A segunda guarda exige que as **duas leituras concordem**; a terceira, que
  `pago_fonte` diga de onde o número veio — e ele só diz "saldo anterior da
  seguinte" quando foi de lá mesmo.
- **`"Fatura Não Paga"` não tinha regra**, caía em `desconhecida` e aparecia
  cru na tela. Pior: sem a frase "Você pagou", `pago` virava o total — uma
  fatura literalmente rotulada "não paga" entrava como quitada. Agora **só o
  rótulo `Fatura Paga` sozinho na linha significa quitada**; qualquer outro sem
  a frase não afirma pagamento nenhum. Set/26 do Black virou `paga_parcial`,
  R$ 1.953,56 de R$ 6.284,18.

**O segundo bug só ficou visível porque o primeiro foi corrigido.** Fatura não
quitada não desaparece: o que sobra vira o `saldo_anterior` da seguinte e é
cobrado de novo, dentro do total dela. A aba Cartões somava o `em_aberto` de
**todas** as faturas do ano — e assim contava a mesma dívida uma vez por mês em
que ela rolou. No Black: R$ 4.664,64 + R$ 9.600,44 + R$ 4.330,62 + R$ 11.911,63
= **R$ 30.507,33** para uma dívida que é o saldo da última fatura. Enquanto
julho e agosto apareciam quitadas, a soma dava certo **por acidente**.

`emAbertoQueNaoRolou(f)` desconta o que a fatura seguinte já carregou — o
**mínimo** entre os dois, não o valor cheio: se a seguinte trouxe menos, a
diferença ainda é dívida e continua aparecendo em vez de sumir. O KPI "Em
aberto no cartão" foi de R$ 47.953,45 para **R$ 31.734,81**, e o aviso passou a
dizer, linha a linha, quanto já rolou — mais uma frase explicando que o total
não soma linha a linha de propósito.

**O Painel não estava errado**: ele já olhava só as faturas do mês selecionado,
onde não há o que rolar. O erro vivia nos dois totais do ano.

5 testes novos, **verificados revertendo a correção** (sem ela o primeiro
falha): o KPI bate com a soma que desconta o que rolou e não com a ingênua,
**existe saldo rolado para o teste ter o que provar** (senão as duas somas
seriam iguais e ele passaria sozinho, sem testar nada), e cada saldo dito
"rolado" reaparece mesmo como saldo anterior da fatura seguinte.

**O que sobrou em aberto no Black, e é isso que ela tem para resolver:**
R$ 11.911,63 na fatura de Out/26 (vence 26/10) mais R$ 2.377,06 de Set/26 que a
foto de ciclo aberto de outubro ainda não reflete — e **R$ 1.600,43 de multa,
mora e encargos de refinanciamento** cobrados em 18/08 e 19/09, que são o preço
do atraso, não do crédito.

### Consumo, taxa e parcela: a aba Cartões separando as três (22/09)
A Juliane pediu: *"acrescente na aba cartões uma coluna pra mostrar o que é
juros e multa, as taxas sabe, pra eu saber quanto foi consumo do cartão e
quanto é taxas"*. A coluna "Do período" existia desde sempre e não respondia
isso — ela junta tudo.

`composicaoDaFatura(f)` quebra a fatura em **três**, não duas, porque são três
coisas com significados diferentes:

| | O que é | É gasto novo? |
|---|---|---|
| **Consumo** | compra de verdade, líquida do estorno dela | sim |
| **Taxas** | juros do rotativo, mora, multa, IOF, anuidade, encargo de refinanciamento (`encargos_financeiros`) | sim, mas não foi escolha de compra |
| **Parcelas** | `divida_parcelada` — parcela de fatura refinanciada | **não**: as compras já foram contadas na fatura em que aconteceram |

Fazer só "consumo x taxas" daria errado: sobraria a parcela de refinanciamento
sem lugar, e ela é grande (R$ 6.197,27 negativos numa fatura do Black). As três
somam exatamente o `cobrado` do cabeçalho — **é essa identidade que protege o
recorte**, e é ela que vira teste: se não fechar, alguma natureza caiu na coluna
errada e a tela estaria chamando de consumo um dinheiro que foi juro.

- **Taxa é líquida também.** Estorno de anuidade e de IOF entram negativos —
  R$ −219,37 em Out/26 do Black, o IOF devolvido do parcelamento cancelado. É
  o que ficou cobrado de verdade, não o que foi lançado.
- **KPI novo, "Juros e taxas": R$ 1.832,01 em 2026** nas faturas importadas,
  R$ 1.721,29 só no Black. É o único número da aba que ela consegue baixar sem
  deixar de comprar nada.
- **Fatura sem taxa mostra "—", nunca R$ 0,00** — com teste próprio.
- **O clique usa `fatura_origem`, não o mês.** Lançamentos não tem select de
  cartão; filtrar por mês traria a fatura dos outros cartões e as linhas do
  extrato, e o clique mostraria mais do que o número que o originou — a regra
  de "explodir valor" deste arquivo. `consumoDaFatura()` / `taxasDaFatura()`
  são predicados presos a `cartao|mes`.

**O que não entra aqui:** juros do cheque especial do Itaú e encargo do limite
do Bradesco também são `encargos_financeiros`, mas vêm do extrato, não de
fatura. Esta aba é de cartão; o custo do limite aparece em Para Onde Vai.

Testes novos por fatura (identidade, consumo exibido, taxa exibida ou "—"),
mais **um que exige que exista fatura com taxa** — sem isso as asserções de
valor nunca rodariam e o bloco passaria sem provar nada. **Verificado tirando
o ramo de taxa do código**: a taxa vai para consumo e as duas colunas falham em
todas as faturas. Suíte em **466 testes**.

O scraper da suíte lia a tabela por posição de coluna e precisou ser atualizado
junto — 3 colunas novas deslocam todas as seguintes.

### Pendências de dado que a dashboard não tem como resolver sozinha (31/08)
1. **Extrato Itaú fechado de agosto/26** — o arquivo importado vai só até 28/08
   e não traz o crédito do salário nem ~6 débitos que existem em todos os meses
   anteriores (DAS do MEI, aluguel de garagem, escola da Valentina, escola do
   Luca, faxina). Todo número de agosto está apoiado num extrato parcial. A
   projeção pela mediana cobre isso na tela, mas marcada como previsão.
2. **Extrato do Mercado Pago** — R$ 15.310 liberados em 21/08 sem rastro de
   onde entraram (no mesmo dia saíram R$ 19.270,31 pagando o cartão 3794, o que
   bate com o que ela já tinha confirmado: os empréstimos foram tomados em parte
   pra pagar fatura da empresa). As 3 parcelas estão **suspensas por decisão
   dela** (ver acima), então não precisam virar lançamento agora — mas quando o
   pagamento voltar, o extrato do Mercado Pago é o que permite lançá-las.
3. **Extrato Nubank PJ da Benetti UP** — paga as faturas do 0442 e do 3794.

### Painel com cards fixos em "não cadastrado" (29/08)
A Juliane reportou "a aba Painel não está funcionando corretamente", sem
mais detalhe — mandei um agente investigar a fundo (rodar a suíte, abrir a
página de verdade com Playwright, recomputar os números direto do JSON)
antes de mexer em qualquer coisa, já que "não está certo" sozinho não diz
o que está errado.

- **Achado real**: os cards "Receitas do mês" e "Parcelas de dívida" em
  `renderizarPainel()` eram **texto fixo** ("não cadastrado"), nunca
  calculados — sobraram de antes de existir a importação de holerite
  (23/08) e a aba Dívidas ser populada (28/08). `receitas()` e a soma de
  `divida_parcelada` do mês já existiam e tinham dado real (ex: Jan/26,
  R$14.670,66 de receita e R$2.036,57 de parcela), mas o Painel nunca
  consultava nenhum dos dois. Corrigido pra usar os valores de verdade,
  caindo em "não cadastrado" só quando o mês realmente não tem holerite
  ou parcela lançada (ex: Out/26, mês ainda sem folha importada).
- O bloco "Resultado do mês" dizia "ainda não dá para calcular sobra ou
  falta" de forma fixa — falso desde que a receita passou a existir.
  Agora mostra de verdade **Receita − Gasto = sobrou/faltou** quando há
  receita do mês, e só mantém o aviso antigo nos meses sem holerite.
- De quebra, o card "Fatura do cartão" tinha nome errado: o `liquido` que
  ele mostra vem de `todasTransacoes()`, que já soma consumo de **todas**
  as origens (cartão, extrato, folha), não só cartão. Renomeado pra
  "Gasto do mês".
- **Mês padrão corrigido pra mês vigente (29/08)**: a tela abria no mês
  mais recente disponível, que podia ser um mês futuro com fatura ainda
  em aberto e quase sem lançamento (ex: Out/26, 4 lançamentos, R$489,17)
  — gerava um "vs. média anterior" tipo "-94%" em verde, parecendo boa
  notícia quando era só fatura incompleta. A Juliane pediu explicitamente
  que a aba abra sempre no mês vigente (`mesVigente()`, calculado por
  `new Date()`, não pelo último mês que aparecer na lista) — só cai de
  volta pro comportamento antigo (última fatura real) se o mês vigente
  ainda não tiver nenhum lançamento.
- **"Parcelas de dívida" também caía em "não cadastrado" por engano**: a
  checagem original era `soma > 0`, mas agosto teve um crédito de
  R$11.417,46 (**não é seguro cancelado** — é o lado "crédito" da mesma
  fatura renegociada do cartão Azul/3794 já documentada em "Fatura
  renegociada" mais abaixo: `Cred Parc Fat Seguro` estorna o valor
  integral pra ele ser cobrado em 4x como `Parc Fatura Seg`; "Seguro" aqui
  é o nome do produto de parcelamento de fatura do Itaú, não uma apólice
  cancelada) que deixa a soma líquida do mês **negativa** mesmo com
  parcela de verdade lançada. Trocado pra checar a **quantidade** de
  lançamentos daquela natureza no mês, não o sinal da soma — assim o
  card mostra o valor negativo de verdade em vez de esconder atrás de
  "não cadastrado".
- **Os 2 empréstimos do Mercado Pago tomados em agosto (R$6.310 e
  R$9.000) nunca tinham virado lançamento de verdade** — desde que
  mapeei as dívidas (28/08), eu só tinha registrado o resumo do contrato
  em `dividas` (saldo, parcela, prazo), sem nunca criar a transação real
  da liberação do dinheiro em `fluxo_mensal.transacoes`. Isso deixava os
  dois **invisíveis** em Painel, Lançamentos e Para Onde Vai — só
  apareciam na tabela de Contratos de Dívidas & Patrimônio. A Juliane
  notou isso ao ver "Parcelas de dívida: não cadastrado" em agosto e
  esperar ver os empréstimos que tinha acabado de tomar. Adicionadas as
  2 transações reais (`natureza: emprestimo`, `categoria:
  emprestimo_tomado`, `origem: mercado_pago`, novo — primeira vez que
  essa origem aparece, já que não existe importador pra essa conta) —
  igual já tinha sido feito pro empréstimo da Cenira. Isso não muda
  "Parcelas de dívida" (que é sobre pagar parcela, não sobre tomar
  empréstimo novo — são naturezas diferentes de propósito), mas faz os
  dois aparecerem em Lançamentos e Para Onde Vai quando ela procurar.
  As parcelas de pagamento desses dois (a partir de setembro) ainda não
  existem como lançamento — só serão lançadas quando de fato saírem da
  conta.
- **Painel ganhou clique explosivo pra Lançamentos (29/08)**, igual já
  existia em Para Onde Vai, Dívidas, Fluxo de Caixa e IRPF: os 3 cards
  com dado real (Receitas do mês, Gasto do mês, Parcelas de dívida — "vs.
  média anterior" ficou de fora por ser uma comparação, não um filtro) e
  as linhas da tabela "Resultado do mês" (Receita do mês, Compras do
  período, Estornos e cancelamentos).
- O teste "Painel informa o que não está cadastrado" só checava se a
  string aparecia em algum lugar da aba, no mês que abrisse por padrão —
  quebrou quando o padrão passou a ser o mês vigente (que pode ter tudo
  cadastrado). Corrigido para navegar explicitamente até um mês sem
  holerite antes de checar, em vez de depender de qual mês é "hoje".

### Abas fora de sincronia entre si (29/08)
A Juliane pediu para um agente validar que todas as 7 abas "estão se
conversando" — os mesmos dados, vistos de ângulos diferentes, deveriam
sempre bater. Mandei um agente comparar número a número entre abas antes
de mexer em qualquer coisa; ele achou 3 divergências reais, todas
corrigidas e reverificadas com Playwright depois.

- **Painel e Fluxo de Caixa discordavam do "gasto do mês"** — o Painel
  soma `gastos + estornos` (estorno tem valor negativo, então abate o
  gasto), mas `dadosFluxoDeCaixa()` filtrava só `t.valor > 0`, jogando
  fora o abatimento do estorno. Mesma conta, resultado diferente: Jan/26
  divergia em R$8.321,19. Corrigido pra `despesaDoMes` somar todo
  `ehConsumo(t)` sem filtrar o sinal, igual ao Painel já fazia.
- **Dívidas & Patrimônio nunca respeitava o seletor Pessoal/Benetti
  UP/Tudo somado** — nem `contratosDeDivida()` nem a tabela de Contratos
  (que lê `dadosGlobais.dividas` direto) tinham o equivalente de
  `noAmbito()`. Trocar de Pessoal pra Benetti UP nunca mudava os R$
  142.119,45 de dívidas nem os R$ 8.885,26 de parcela mensal, quebrando a
  aditividade (pessoal + empresa = tudo) que o resto do app respeita.
  Como `dívidas`/`investimentos` são registros declarativos sem campo
  `ambito` (só `pessoa`), a correção usa `ambitoDaPessoa(d.pessoa)`
  comparado ao seletor atual, com passagem livre em "tudo somado".
- **3 cliques do Imposto de Renda mostravam mais lançamentos do que o
  card representa** — violando a regra já documentada acima ("Explodir
  valor em Lançamentos") de que o clique tem que reproduzir exatamente o
  número que o originou:
  - "Rendimento tributável" filtrava só `natureza: receita`, sem excluir
    PLR/13º (que têm tributação exclusiva e ficam de fora desse total).
  - "Imposto já retido" filtrava só `categoria: imposto_renda`, sem
    excluir a rubrica `/405` (o IR retido sobre a PLR, que é separado).
  - As linhas por pessoa dentro de Saúde/Instrução (e das demais
    deduções) não respeitavam a exceção de não-dedutível (farmácia dentro
    de Saúde, papelaria dentro de Instrução) nem excluíam lançamentos com
    `natureza: ajuste` (achado ao testar o clique: um acerto retroativo de
    R$3,52 do plano odonto vazava pro filtro mesmo não entrando na conta
    do card).

  Os filtros de Lançamentos são só igualdade simples (um select por
  campo) — não davam conta de "exceto X" ou "campo Y diferente de Z".
  Em vez de inventar novos selects na tela só para esses casos raros,
  `irParaLancamentos()`/`irParaLancamentosPessoal()` ganharam um 2º
  argumento opcional: um predicado JS (`naoEhCategoria(...)`,
  `naoCasaDescricao(padrao)`, `naoTemRubrica(rubrica)`, `apenasPositivo`)
  aplicado depois dos filtros normais, guardado numa variável de módulo
  (`filtroExtra`) sem select correspondente. Ele nunca fica pendurado:
  toda chamada de `aplicarFiltros()` sem esse 2º argumento (botão
  "Filtrar", ou outro clique que não precise dele) volta a zerar
  `filtroExtra` — só vale para o clique que acabou de acontecer.

### Explodir valor em Lançamentos (23/08)
Clicar num valor em Para Onde Vai, Dívidas & Patrimônio ou Fluxo de Caixa pula
para a aba Lançamentos já filtrada pelos mesmos critérios que compuseram
aquele número (`irParaLancamentos()` em `public/index.html`).

- **Lançamentos deixou de ser só despesa/estorno.** Antes a aba usava
  `todasTransacoes()` (só consumo — exclui receita, dívida parcelada,
  transferência etc.), o que fazia qualquer clique vindo de Dívidas (tudo
  `divida_parcelada`) ou da coluna Receita do Fluxo de Caixa sempre devolver
  zero resultado. Agora usa `transacoesDoAno()`, que traz qualquer natureza —
  e por isso ganhou um filtro **Natureza** (antes só existia Tipo
  Entrada/Saída, que mistura receita com pagamento e estorno). Os cards de
  resumo (Total/Estornos) continuam somando só `despesa`/`estorno` de
  propósito, senão receita ou dívida inflaria um número que devia significar
  gasto.
- Categoria e pessoa exibidas em Para Onde Vai são só formatação
  (`rotuloCategoria`); o clique usa o valor cru gravado no lançamento, não o
  rótulo.
- Em Dívidas, o link usa `busca` com a descrição exata do contrato (mais
  `natureza: divida_parcelada`) — é o mesmo agrupamento por descrição que
  `contratosDeDivida()` já faz, então sempre bate com o que a tela mostra.
  Parcela **a vencer** não é clicável: é projeção, não existe como
  lançamento ainda — só a **paga** abre.
- Em "Fatura paga a menor", a linha inteira filtra a fatura (mês + conta,
  já que duas faturas de cartões diferentes podem cair no mesmo mês); a
  célula de custo tem o próprio clique, mais específico (mês seguinte +
  categoria `encargos_financeiros`) — por isso ela impede a propagação do
  clique da linha (`event.stopPropagation()`), senão o clique mais genérico
  sobrescreveria o filtro certo.
- **Imposto de Renda também ficou clicável (28/08)**: os dois cards
  (Rendimento tributável, Imposto já retido), cada linha de pessoa dentro
  de um grupo dedutível (Saúde, Instrução, Previdência) e cada linha de "O
  que não deduz" abrem em Lançamentos. Usa `irParaLancamentosPessoal()`,
  não `irParaLancamentos()` direto — o IRPF ignora o seletor de âmbito do
  topo (é sempre pessoal), então clicar um valor com "Benetti UP" ou "Tudo
  somado" selecionado força o seletor de volta para Pessoal antes de
  filtrar, senão o clique abriria um filtro que não bate com o número que
  o originou. "Deduções que aproveitam" e "Desconto simplificado" ficaram
  de fora: são somas com teto por pessoa aplicado, não um filtro único.

### Imposto devido x retido: falta pagar ou vai restituir? (28/08)
A Juliane perguntou se as deduções que já tinha lançado eram suficientes pra
restituir o imposto retido. A aba até então só mostrava as peças soltas
(rendimento, deduções, retido) sem nunca montar a conta final — foi
implementado em `apurarIrpf()`/`renderizarIrpf()` (`public/index.html`) e
`data/regras-irpf.json`.

- **PLR e 13º são tributação exclusiva/definitiva na fonte** — têm tabela
  própria (isenção até R$8.214,40/ano, bem mais alta que a do salário) e,
  uma vez retidos, esse imposto é final: não somam com o rendimento
  tributável normal, e não entram no ajuste (a pagar ou a restituir) da
  declaração anual, só aparecem como informação. Excluí-los do "rendimento
  tributável" foi a correção mais importante — contar tudo junto (como a
  aba fazia antes) inflava a base e fazia parecer que faltava muito mais
  imposto a pagar do que falta de verdade. Identificados por categoria
  (`plr`, `decimo_terceiro`) na receita, e por rubrica (`/405`) no imposto
  retido — `CATEGORIAS_TRIBUTACAO_EXCLUSIVA` no código.
- **Tabela progressiva anual em `regras-irpf.json`** (`tabela_progressiva_anual`):
  é a mesma tabela mensal usada pra reter na fonte, com cada faixa e cada
  parcela a deduzir multiplicada por 12 — é assim que a Receita monta a
  tabela anual, não é uma tabela calculada à parte.
- **A Lei 15.270/2025 mudou a tabela de 2026**: isenção subiu pra R$5.000/mês
  (R$60.000/ano), com redução parcial até R$7.350/mês (R$88.200/ano) — um
  redutor aplicado *depois* do cálculo normal pela tabela. Não implementado:
  o rendimento da Juliane já passa de R$88.200/ano bem antes de agosto, então
  esse redutor nunca chega a valer pro caso dela. Documentado no `_nota`
  do JSON para o dia em que isso deixar de ser verdade (licença, mudança de
  renda) — nesse caso o cálculo atual vai superestimar o imposto devido.
- **A modalidade usada pro cálculo (completa ou simplificada) é a que sobra
  menos a pagar** (ou restitui mais), comparando os dois saldos — mesmo
  critério que já decidia qual delas "rende mais" antes de existir esse
  bloco nas deduções.
- Isso é sempre **parcial**: só os meses já lançados. O aviso deixa isso
  explícito porque salário, dedução e retenção dos meses que faltam vão
  mudar a conta até dezembro.
- Tabelas (progressiva e da PLR) e o redutor da Lei 15.270/2025 verificados
  via busca na web em 28/08 — como não achei acesso direto ao gov.br a
  partir daqui, cheguei nos números cruzando várias fontes secundárias que
  concordavam entre si. Vale conferir contra a Receita Federal se um dia os
  valores mudarem de novo.

### Dependentes no IRPF (28/08)
A Juliane perguntou se os dependentes tinham entrado na conta de falta
pagar/restituir — não tinham: o bloco "Dependentes" sempre foi só
informativo, nunca somava em `somaDeducoes`, porque quem é dependente é
decisão dela e do contador, a dashboard não tem como adivinhar.

- Marcado com `dependente_irpf: true` na pessoa, em
  `data/configuracoes.json` — hoje só **Valentina e Luca**. `apurarIrpf()`
  soma R$2.275,08 por pessoa marcada, só na declaração completa (o
  desconto simplificado já é um substituto fixo de 20% da renda, não soma
  com dedução por dependente).
- **O Hugo ficou de fora de propósito, e a conta confirma que deve ficar
  assim.** Ela mencionou "3 dependentes, meus filhos e meu marido", mas
  declarar cônjuge como dependente obriga a somar a renda inteira dele na
  declaração dela. Ele é taxista, ~R$2.000/mês (~R$24.000/ano) — somando
  isso na faixa de 27,5% dela, o imposto extra (~R$6.600) fica bem maior
  que a economia da dedução por dependente (R$2.275,08 × 27,5% ≈ R$625):
  **perderia uns R$5.975 líquidos** se declarasse ele. Não marcado em
  `configuracoes.json` — e não deveria ser, a menos que a renda dele mude
  muito.

### Dívidas & Patrimônio cadastrada (28/08)
A aba `dividas` estava vazia desde o início — a Juliane mandou aos poucos
(prints do Itaú, Mercado Pago, portal do CRC-SP, boletos de escola) os
dados de tudo que está em aberto, e isso foi cadastrado de vez em
`financeiro.json` (`dividas`, 12 contratos).

- **Os 4 consignados do Itaú (débito em conta + 3 descontados na folha)
  não são dívida nova** — já apareciam todo mês como `divida_parcelada`
  vindos do extrato e do holerite. O que faltava era o **nível de
  contrato**: valor total, parcelas restantes, saldo devedor — que só um
  print do "Resumo de empréstimos contratados" do Itaú (não vem em
  lançamento nenhum) tem. Cruzado com sucesso: a parcela de cada um bate
  exatamente com a rubrica já lançada (1CT1, 1CT2, MCT0).
- **3 empréstimos do Mercado Pago são dívida nova de verdade**, tomados
  em 2026: R$14.000 (linha de crédito, 05/06), R$6.310 e R$9.000 (ambos
  21/08, mesmo dia — os dois últimos com CET de ~100-106% a.a., crédito
  caro). Conta pessoal, confirmado pela Juliane.
- **As taxas dos dois empréstimos de 21/08 vieram trocadas na primeira
  leitura** — o ID do empréstimo (#1414088008) da tela de "Condições"
  batia com o de R$14.000, não com o de R$6.310 como eu tinha assumido
  por terem chegado juntos na mesma mensagem. Corrigido depois que a
  Juliane mandou a tela de pagamento mostrando "Empréstimo pessoal,
  parcela 3 de 18" pro de R$14.000 — 18 parcelas de R$1.294,38, juros
  69% a.a., CET 105,62% a.a. O de R$6.310 fica com as taxas certas (juros
  91,82% a.a., CET 100,43% a.a., 12x R$752,29).
- **Empréstimo de pessoa física é da mãe da Juliane (Cenira Gomes
  Ferreira)**: ela tomou um "Crédito Parcelado" (R$10.000 liberados, 36x
  R$645,91, R$23.252,76 no total) pra emprestar pra filha, que paga de
  volta R$646/mês direto pra ela via Pix. Saldo cadastrado é estimado
  (total do contrato da mãe menos R$3.600 já pagos, confirmado por
  WhatsApp entre elas) — não vem de extrato oficial, por isso a nota no
  campo `observacao` avisando que pode estar impreciso.
- **Prints antigos podem contaminar o mapeamento** — a Juliane mandou
  duas telas do consignado de R$38.500 com "parcela 21 de 60" e
  "vencimento 01 jun 2025", números bem diferentes do que já estava
  cadastrado (parcela 35/60, saldo do resumo de 28/08/26). Ela confirmou
  que eram prints antigos e para confiar no extrato/resumo mais recente
  — o cadastro não mudou por causa deles. Fica registrado o alerta: ao
  receber print de empréstimo, checar a data antes de usar o número.
- **Contas fixas em atraso também entraram como "dívida"** mesmo sem ser
  financiamento de prazo longo: CRC-SP (anuidade, 2 parcelas), IPTU +
  lixo (4 parcelas), mensalidade de agosto da Escola Valentina e do Luca.
  Fazem o mesmo sentido na aba: são compromisso que falta pagar.
- **Bug real encontrado e corrigido nesse processo**: a tabela de
  Contratos usava `moeda(d.montante)` direto, que trata `null`/`undefined`
  como `0` — então os itens sem saldo conhecido (linha de crédito do
  Mercado Pago, Cenira) apareciam como "R$ 0,00", parecendo quitados.
  Violava a "regra de ouro dos dados" já documentada neste arquivo. Agora
  mostra "não cadastrado" nesses casos, e os KPIs de total (Dívidas,
  Patrimônio líquido) ganharam uma nota avisando que a soma é parcial
  quando algum contrato está sem saldo. `moeda()` em si não mudou — é
  função genérica usada em dezenas de lugares onde zero de verdade é
  legítimo; o fix foi só na tabela de Contratos.
- **Segundo bug, achado quando a Juliane conferiu o extrato de verdade
  (29/08)**: o depósito de R$10.000 da Cenira (12/05/26) estava
  classificado como `natureza: receita` no extrato — inflando a renda
  tributável dela em R$10 mil (chegava a afetar até o cálculo de IRPF).
  Corrigido pra `natureza: emprestimo` / categoria `emprestimo_tomado`,
  mesmo padrão já usado pro consignado. As 3 parcelas de R$646 já pagas
  (jun, jul, ago) também foram corrigidas de `despesa` pra
  `divida_parcelada` / categoria `emprestimo_familiar` — o saldo estimado
  por WhatsApp (R$3.600 pagos) estava errado por isso: o extrato mostra
  só R$1.938 pagos de verdade (3×R$646). Saldo corrigido pra R$21.314,76,
  faltam 33 de 36 parcelas. Regras persistentes adicionadas em
  `importar-extrato-itau.js` (`PIX.*CENIRA`, separadas por `entrada` e
  por `valorEntre` pra não confundir com os dois PIX antigos abaixo.
- **Os dois PIX antigos pra Cenira (R$300 em jan/26, R$500 em abr/26) são
  ajuda de custo**, não empréstimo — a Juliane confirmou que eram pra
  ajudar a mãe a pagar conta do mês, antes mesmo do empréstimo de R$10 mil
  existir. Categoria nova `ajuda_familiar` (`despesa`, não dedutível no
  IR — adicionada em `nao_dedutivel` de `regras-irpf.json`), com uma
  terceira regra em `importar-extrato-itau.js` pra qualquer Pix futuro
  pra Cenira fora da faixa de valor da parcela do empréstimo.
- **Duas visões da mesma dívida convivem de propósito**: a tabela
  "Contratos" (dados que a Juliane digitou/print) mostra o saldo devedor
  real (já descontando amortização) e quando quita; o bloco "Fluxo de
  caixa das dívidas", mais abaixo, é calculado ao vivo a partir dos
  lançamentos e mostra o fluxo de caixa mês a mês. Não é duplicação: os
  números de saldo diferem de propósito (um é o valor contábil real vindo
  do banco, o outro é a soma nominal das parcelas que faltam, sem
  desconto) — se ela estranhar dois números diferentes pro mesmo
  empréstimo, é por isso.
- **`observacao` de cada dívida nunca aparecia na tela (29/08)**: quando
  enriqueci os 4 consignados do Itaú com número de contrato, datas e
  custo total do financiamento, gravei tudo certinho no campo
  `observacao` do JSON — mas a tabela "Contratos" nunca lia esse campo em
  lugar nenhum, então a Juliane não via nada de novo mesmo com o dado já
  salvo e deployado. A Juliane perguntou "por que você não atualizou",
  quando na verdade tinha atualizado — só não estava aparecendo. Corrigido
  mostrando `observacao` como legenda pequena embaixo do nome de cada
  linha da tabela.

### `atualizar.sh` guarda e devolve edição pendente sozinho (29/08)
A Juliane notou que rodar só `deploy` tinha "parado de funcionar" — na
verdade nunca funcionou sozinho quando havia edição pendente da tela; o
que mudou foi a frequência: como ela mexe na dashboard entre um deploy e
outro quase toda vez, o `git pull --ff-only` recusava quase sempre,
exigindo `git stash -u` manual antes e `git stash pop` depois.

- `atualizar.sh` agora faz esse stash sozinho: guarda antes do pull (só se
  `git status --porcelain` não estiver vazio) e devolve depois que o
  deploy termina (reinício do PM2 e health check incluídos) — voltou a
  bastar rodar `deploy` puro.
- **Conflito de verdade não é escondido.** Se o `git stash pop` não
  conseguir mesclar sozinho (a mesma parte do arquivo mudou dos dois
  lados), o script avisa claramente e para (`exit 1`) sem tentar resolver
  — a edição fica guardada no stash (nunca descartada) e o arquivo de
  trabalho fica com os marcadores de conflito do próprio git, prontos pra
  alguém decidir à mão. Testado em repositório descartável nos dois
  caminhos (merge limpo e conflito de propósito) antes de valer pra valer
  — nos dois casos nada se perde.

### Edições na tela não estavam sendo salvas (24/08)
A Juliane relatou: editou a categoria de um lançamento, rodou `deploy` depois,
e a classificação tinha sumido. A causa real **não foi o deploy** — testei o
`git pull --ff-only` do `atualizar.sh` e confirmei que ele recusa sobrescrever
um arquivo com edição não commitada, não descarta silenciosamente.

A causa de verdade: `server.js` usava `bodyParser.json()` sem `limit`, que
por padrão aceita só **100kb** de corpo — e `financeiro.json` sozinho já
passa de **2MB**. Todo `POST /api/dados` (que manda o arquivo inteiro) vinha
voltando `413 Payload Too Large`, e `salvarDadosAutomatico()` só logava o
erro no console, sem nenhum aviso na tela. **Toda edição feita pela interface
nunca foi salva de verdade**, não só essa — o bug existe desde que o arquivo
passou de 100kb. Corrigido com `bodyParser.json({ limit: '20mb' })`.

Duas camadas a mais pra isso não voltar a acontecer em silêncio:
- `salvarDadosAutomatico()` agora mostra um aviso visual — "✓ Salvo" (some
  em 1,5s) ou, se falhar mesmo depois de uma tentativa automática de novo,
  um aviso vermelho que fica na tela até ser clicado ou 15s passarem.
- `atualizar.sh` agora faz backup de `financeiro.json` e dos outros arquivos
  de dados editáveis pela tela (`financeiro/data/backups-deploy/`, fora do
  git) antes de cada `git pull`, e imprime uma mensagem clara se o pull for
  recusado — rede de segurança extra, caso a causa de uma próxima perda seja
  outra.

**O nginx do VPS tinha o mesmo limite de tamanho, em duas camadas.** Mesmo
depois de corrigir o `server.js`, o 413 continuou vindo do nginx, que por
padrão só aceita 1MB de corpo (`client_max_body_size`) — bem menor que o
`financeiro.json`. E não bastou corrigir um bloco: o VPS tem **dois** blocos
de config servindo esse domínio na porta 443 (HTTPS, o que a Juliane usa de
verdade) — um dedicado em
`/etc/nginx/sites-available/financeiro.descontoirresistivel.com.br`, e outro
**combinado** dentro de `/etc/nginx/sites-available/descontoirresistivel.conf`
(`server_name descontoirresistivel.com.br www.descontoirresistivel.com.br
financeiro.descontoirresistivel.com.br;` numa linha só — esse é o que estava
realmente ativo). Os dois agora têm `client_max_body_size 20m;`. Documentado
em `DEPLOY_VPSFINANCEIRO.md`, mas só o arquivo dedicado — se o VPS for
reconstruído do zero, conferir se o bloco combinado em
`descontoirresistivel.conf` (compartilhado com os outros sites do domínio
`descontoirresistivel.com.br`) também precisa da diretiva.

### Edição em Lançamentos: seleção e replicação (24/08)
Categoria e Pessoa deixaram de ser `prompt()` de texto livre — agora abrem um
`<select>` (`editarCategoriaSelect()`, `editarPessoaSelect()`) com os valores
que já existem nos dados (mais "+ Outro..." pra criar um novo). Antes exigia
digitar o valor exato de cabeça, sem nenhuma lista.

Editar **categoria, pessoa ou Fixa/Variável** de um lançamento agora pergunta
se deve replicar a mudança pros outros lançamentos com a **mesma descrição**
(`aplicarEdicaoComReplicacao()`, comparação por descrição normalizada —
minúsculo, espaços colapsados). Fica sempre atrás de um `confirm()`: nunca
aplica em lote sem a Juliane autorizar antes, e o texto do diálogo já mostra
quantos lançamentos seriam afetados. Não vale para os outros campos editáveis
(data, valor, parcela etc.) — esses são fato de cada lançamento, replicar
seria errado.

**Editar a pessoa também tem que atualizar o âmbito junto.** `ambito`
(pessoal/empresa) é um campo gravado no lançamento, não recalculado a cada
render — `noAmbito()` confia nele. Trocar a pessoa para Benetti UP sem
recalcular `ambito` deixava o campo velho, e o lançamento vazava pro filtro
errado no seletor do topo (achado pela Juliane: despesa de
`educacao_profissional` da Benetti UP aparecendo sob o filtro Pessoal).
`aplicarEdicaoComReplicacao()` agora recalcula `ambito` pelo cadastro em
Configurações (`ambitoDaPessoa()`) sempre que o campo editado é `pessoa` —
tanto no lançamento clicado quanto nos replicados. Mesmo critério que os
scripts de importação e o `classificar.js` já usavam do lado do servidor.

### Classificação em lote (24/08)
Filtra (por descrição, categoria, o que for) e aplica Categoria, Pessoa ou
Fixa/Variável a todos os lançamentos que sobraram no filtro de uma vez
(`aplicarClassificacaoEmLote()`) — pra quando há muita coisa igual pra
reclassificar e não vale a pena clicar lançamento por lançamento.

- **Exige algum filtro ativo antes de aplicar.** Sem isso, "aplicar em lote"
  mudaria os 1912 lançamentos de uma vez sem querer — `algumFiltroDeLancamentosAtivo()`
  recusa com um aviso se nenhum campo de filtro estiver preenchido.
- Só uma confirmação para o lote inteiro (não uma por lançamento, ao
  contrário da replicação por descrição) — o texto do `confirm()` mostra o
  campo, o valor novo e a quantidade exata antes de aplicar, porque não dá
  pra revisar item por item quando são centenas.
- Editar pessoa em lote também recalcula `ambito` pra cada lançamento
  (mesma `ambitoDaPessoa()` da edição individual).

### Fixa x Variável e o mês expansível no Fluxo de Caixa (24/08)
Toda despesa (`natureza: despesa`) ganhou um campo editável `fixa_variavel`
(`fixa` ou `variavel`), coluna própria em Lançamentos — clicar no selo
alterna entre os dois (`alternarFixaVariavel()`).

- **O campo começa com um palpite, não fica em branco.** Sem valor gravado,
  `classificacaoFixaVariavel()` cai no mesmo critério que já existia
  (`ehFixa()`: categoria fixa — assinatura, moradia, educação, utilidades,
  serviços, ferramentas — ou parcelada) antes de perguntar à Juliane. O
  campo explícito sempre vence sobre o palpite assim que ela clica.
- **Compra parcelada conta como fixa** mesmo em categoria variável (ex:
  viagem parcelada) — o valor mensal é conhecido e se repete, que é o
  sentido de "fixa" aqui: previsibilidade de caixa, não necessidade do gasto.
- **A projeção do Fluxo de Caixa passou a usar essa classificação.** Antes a
  estimativa de mês futuro era uma média única do gasto avulso (não
  parcelado). Agora se divide em `estimativaFixa` e `estimativaVariavel`,
  cada uma com sua própria média histórica e seu próprio piso (`Math.max`
  contra o que já foi lançado numa fatura aberta) — separados, para um gasto
  variável alto no mês não satisfazer artificialmente o piso do fixo.
- **Clicar no mês, na aba Fluxo de Caixa, expande a composição do saldo**
  (`toggleFluxoDetalhe()`): mês realizado mostra receita e despesa agrupadas
  por categoria (despesa ainda separada em fixa/variável); mês previsto
  mostra o compromisso item a item (cada parcela de dívida/cartão a vencer)
  mais as duas estimativas. Linha "a vencer" no compromisso não abre em
  Lançamentos — é projeção, ainda não existe como lançamento.

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

### Fatura parcelada: a dívida muda de lugar, não some (09/09)
A Juliane parcelou a fatura de Set/26 do 0442 (R$ 1.382,94) direto no app do
Itaú: entrada de R$ 131,38 em 09/09 e **4x R$ 408,13** vencendo de 01/10/26 a
01/01/27. Conferido contra o comprovante, linha por linha — saldo a financiar,
IOF, juros e total batem todos.

**O custo:** desembolso de R$ 1.763,90 por uma dívida de R$ 1.382,94 — R$ 380,96
de juros e IOF. Juros de **12,4% ao mês (314,63% ao ano)**, **CET 338,31% ao
ano**. É o crédito mais caro de todos os contratos cadastrados: os três do
Mercado Pago, que já eram caros, ficam entre 100% e 106% de CET anual.

Três coisas mudaram no dado, e a terceira só apareceu porque um teste quebrou:

1. **A fatura de Set/26 saiu de "em aberto"** — `situacao: 'parcelada'` (selo
   novo), `pago: 131,38`, `em_aberto: 0`. Deixar em aberto faria o Painel cobrar
   em setembro um valor que ela já resolveu. O "sai da conta" de Set/26 caiu de
   R$ 8.845,54 para R$ 7.462,60, exatamente os R$ 1.382,94.
2. **A fatura de Out/26 perdeu o saldo anterior.** Ela tinha sido importada
   antes do parcelamento e trazia os R$ 1.382,94 como saldo rolado — o que só
   valeria se tivesse ido para o rotativo. Zerado, com observação; a parcela de
   R$ 408,13 entra quando a fatura real de outubro for importada.
3. **`financiado_em_parcelas` no cabeçalho da fatura.** O teste "saldo em aberto
   é a soma do que cada fatura deve" quebrou, e estava certo em quebrar: a
   identidade `em_aberto = total − pago` não fecha numa fatura parcelada, porque
   o resto **não evaporou, mudou de lugar**. O campo guarda para onde foi
   (R$ 1.251,56), a identidade virou `total − pago − financiado_em_parcelas`, e
   dois testes novos exigem que todo valor financiado tenha contrato
   correspondente em Dívidas e que esse contrato custe mais que o financiado —
   senão o dinheiro sai do cartão e some da tela.

**Ao registrar um parcelamento de fatura, fazer os três juntos.** Mexer só na
fatura esconde a dívida; mexer só em Dívidas deixa o cartão cobrando duas vezes.

O contrato ficou com `pessoa: Benetti UP`, seguindo o âmbito dos lançamentos do
0442 (a fatura era 82% gasto da empresa) — mas o parcelamento está no nome da
Juliane, e isso está anotado na observação.

### Fatura paga a menor (rotativo)
Pagar menos que o total é **tomar crédito**: o saldo rola para a fatura seguinte
e o banco cobra por carregar. Foram 5 faturas assim em 2026, R$ 15.267,11
financiados.

- **O principal que rola não é despesa** — são as mesmas compras sendo
  carregadas, já contadas quando aconteceram. Ele não vem linha a linha: só
  engorda o `total_fatura` da seguinte e reaparece como `saldo_anterior`.
- **O custo de carregar é despesa financeira**, categoria `encargos_financeiros`:
  juros, mora, multa, IOF e encargos de refinanciamento. Nunca despesa comum.
- **Anuidade e IOF de compra internacional também são despesa financeira**, mas
  não são custo do rotativo — seriam cobrados de qualquer jeito. Ficam fora do
  "custo desse crédito" da aba Dívidas, senão o crédito parece mais caro do que foi.
- O IOF que acompanha uma compra (`Iof Internacional - Hostinger`) herda a
  **pessoa** de quem comprou. Fixar Família jogaria para a casa o IOF de
  assinatura da Benetti UP.

### Fluxo de Caixa (previsto x realizado)
Um mês é **realizado** ou **previsto** pela data de calendário de verdade
(`new Date()` no momento do render comparado ao `mes_vencimento`), nunca por
ter ou não ter lançamento — uma fatura aberta de setembro já traz algumas
compras antes mesmo de setembro chegar, e isso não faz setembro virar passado.

- **Mês passado**: mostra receita e despesa reais, comparadas com a **média do
  próprio ano**. Não existe orçamento cadastrado para comparar — a média é a
  única referência honesta disponível.
- **Mês futuro** soma duas coisas que a tela nunca mistura:
  - `compromisso` — parcela de dívida (`divida_parcelada`) e de compra no
    cartão que **já se sabe o valor exato**, vencida ou projetada a partir da
    última parcela conhecida de cada contrato/compra.
  - `estimativa` — o resto do gasto (mercado, combustível, farmácia), que não
    está contratado mas se repete todo mês. Calculada pela média do gasto
    avulso (`!eh_parcelada`) dos meses já realizados.
- **Compromisso nunca é só o projetado.** Uma fatura pode fechar com
  vencimento num mês futuro trazendo uma parcela **já lançada de verdade**
  (`divida_parcelada` ou `despesa` parcelada com `mes_vencimento` à frente de
  hoje) — isso não é projeção, é fato, e entra no compromisso do mês em vez de
  ficar de fora. Ignorar isso subestimou o compromisso de setembro/2026 em
  R$ 6.184,53 na primeira versão.
- **O que já apareceu numa fatura aberta é piso, não substitui a estimativa**:
  `Math.max(mediaAvulsa, avulsaJaLancadaNoMes)` — a fatura aberta só reflete o
  que aconteceu até a data do arquivo, o mês continua enchendo.
- Receita futura é a média das receitas já realizadas — **inclui PLR e
  adiantamento**, que puxam a média para cima. É estimativa, não promessa; a
  tela avisa isso.
- Respeita o seletor de âmbito (Pessoal / Benetti UP / Tudo somado), ao
  contrário do Imposto de Renda, que é sempre pessoal.
- **A abertura de um mês futuro não repetia o resumo simples (29/08)**: a
  Juliane clicou pra expandir setembro e só viu "Compromisso" + "Estimativa
  fixa" + "Estimativa variável" soltos, sem nenhuma linha dizendo "recebe X,
  paga Y, falta/sobra Z" — que é a pergunta que essa aba existe pra
  responder. A linha fechada já mostrava isso, mas ao abrir o detalhe ela
  perdia essa âncora. `detalheFluxoPrevisto()` agora abre com um resumo em
  português simples repetindo recebe/paga/sobra-falta, e explicitando que
  compromisso + estimativa fixa + estimativa variável = despesa (a soma
  nunca era mostrada, só os três números separados, e ela tinha que somar
  de cabeça).

### Múltiplos cartões
Três cartões: **4846** (Itaú Black, pessoal), **0442** (Visa Infinite, quase
só tráfego pago) e **3794** (Azul). A chave de uma fatura é **cartão + mês** —
só o mês faria a fatura de um cartão sobrescrever a do outro.

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

### Holerite (Elektro)
A Juliane é analista na **Elektro Redes**. O salário cai no **Itaú, ag. 341700,
c/c 00806-4** — a conta vem lida do próprio comprovante, não fixada no código.

Entra o **provento bruto como receita** e **cada desconto como lançamento
próprio**. Guardar só o líquido esconderia que R$ 1.310/mês vão embora em
consignado antes de o dinheiro chegar, e que plano de saúde e previdência são
despesa recorrente.

- O mês é o da **data de crédito**, não o de referência (regime de caixa). A PLR
  caiu em 31/03 e conta em março.
- A classificação vem da **rubrica** (`M010`, `/314`, `1CT1`), não do texto da
  descrição — o código é estável entre os meses, o texto varia.
- **Tudo é da Juliane**, exceto o plano de saúde: Bradesco Saúde, Odonto e
  coparticipação médica descontam na folha dela mas cobrem a casa toda, então
  ficam com **Família**.
- **Consignado** (`1CT1`, `MCT0`) é `divida_parcelada`, não despesa: quita
  empréstimo, não é consumo novo.
- **Retificação de competência** (abril acerta março) fica como `ajuste`: lança
  o mesmo valor como provento e como desconto, e contar um lado só criaria
  receita ou despesa do nada.
- Cada comprovante é conferido contra o próprio líquido antes de gravar. Rubrica
  sem regra **para a importação** em vez de entrar sem classificação.

### Férias e adiantamento de PLR pelo holerite (28/08)
Julho/26 trouxe três comprovantes numa competência só: o **adiantamento de
férias** (10 dias, pago em 08/07, separado do salário), o **salário do mês**
(24/07) e um **adiantamento de PLR** (31/07). Cada um tem rubricas próprias,
novas em relação ao que já existia:

- **Férias** (`MZ00`/`MC03` + as médias `0AM1/0AM4/0AM7` no comprovante de
  férias e `1AM1/1AM4/1AM7` no salário do mês, mais `066N`/`M389`/`MCP0`) →
  `receita` / categoria nova **`ferias`**. O sistema de folha recalcula
  férias junto do fechamento mensal, então os dois comprovantes trazem
  proventos de verdade com valor coincidente — não é a mesma entrada
  duplicada, ambos batem contra o próprio líquido de cada comprovante.
- Os descontos sobre férias (`M388` INSS, `54AN` previdência, `548N` e
  `MCP1`) seguem a mesma lógica dos descontos normais de folha, só que
  calculados sobre o valor de férias em vez do salário do mês — `despesa`,
  nas categorias `inss`/`previdencia_privada`/`ferias`.
- **`/355` "Desc.adiant.férias c/trib"**, no salário de 24/07, é o mesmo
  mecanismo do `6F5N` (desconto do adiantamento da PLR, já documentado
  acima): o adiantamento de férias já entrou como receita real no
  comprovante de 08/07, e essa linha só fecha a competência contábil no
  salário do mês — `ajuste`, senão a mesma férias contaria como despesa ao
  contrário.
- **`10UN` "Adiantamento PLR"** → `receita` / categoria `plr` (mesma
  categoria de `/B10`). O desconto de imposto de renda que acompanha
  (`/405`) já tinha regra.
- Todos os três comprovantes de julho conferem contra o próprio líquido, e o
  extrato da conta confirma os créditos — a conciliação (`conciliar.js`)
  fechou sem nenhuma pendência.

### Extrato da conta (Itaú)
Terceira fonte, ao lado da fatura e do holerite. Traz o que as outras não veem:
boleto, débito automático, PIX e o custo do cheque especial. Conta corrente
**ag. 0642, c/c 00806-4** — a mesma em que o salário cai.

**O risco é contar duas vezes.** O extrato repete, como movimento de caixa,
coisas que já entraram linha a linha por outra fonte. Ficam com
`natureza: "transferencia"` — aparecem, mexem no saldo, e não entram em receita
nem em despesa:

- **crédito do salário**, que o holerite já lançou como provento e descontos;
- **pagamento da fatura**, cujas compras já estão lançadas uma a uma;
- **PIX entre contas próprias** da Juliane, nos dois sentidos.

Isso só vale se a outra fonte existir: **sem o holerite do mês, o crédito do
salário volta a contar como receita**, senão a renda daquele mês desaparece. O
script avisa quando faz isso — ao importar o holerite que faltava, reimporte o
extrato.

Decisões que a Juliane tomou (23/08):
- **PIX de/para "Juliane"** → conta dela em outro banco, transferência.
- **PIX da Benetti UP para ela** → `pro_labore`, receita pessoal.
- **PIX dela para a Benetti UP** → aporte na empresa, fora do consumo.
- **PIX do Hugo** → `contribuicao_casa`, receita.

Outros pontos:
- **"Credito Consignado N/60"** é um **quarto** empréstimo, além dos três da
  folha: R$ 1.402,67/mês debitados direto na conta.
- **"Credito Consignado" sem parcela e positivo** é liberação de empréstimo:
  `natureza: "emprestimo"`. Dinheiro entrando que é dívida, não renda.
- **Juros do limite e IOF** são `encargos_financeiros` — custo do cheque especial.
- **DAS do MEI** é imposto da empresa: âmbito **Benetti UP**.
- Lançamento com data futura é **PIX agendado**: fica com `status: "agendado"`,
  porque o dinheiro ainda não saiu.
- O `.xls` traz valor no padrão americano (`-1,402.67`) e texto latin-1 lido
  como utf-8 ("cartÃ£o"). As duas coisas são tratadas na leitura.

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
- **McDonald's, KFC, rodízio** → `alimentacao_fora` / **Família** — sai com a
  casa toda, é gasto da família mesmo fora de casa. Exceção: **Dona
  Terezinha**, que é almoço de trabalho da Juliane sozinha (ver acima), tem
  regra própria que vale antes desta.
- **Papelaria** → `educacao` (material escolar).
- **Facebook / Meta / Google Ads** → `trafego_pago` / **Benetti UP**.

- **Hostinger, OpenAI, Anthropic, Netlify, TurboScribe** → `ferramentas` /
  **Benetti UP** — hospedagem, IA, deploy e transcrição usados no trabalho.

- **PIX para igreja** → `doacao` / **Família** — oferta semanal. **Não deduz no IR**:
  a lei só permite doação a fundo da criança e do idoso, Rouanet, audiovisual,
  desporto e PRONAS/PRONON.

Confirmados depois: **Mundo Cores** é a escola da Valentina; **papelaria** é
material dos dois filhos, e por isso existe a pessoa **Filhos**.

Regras do guia de classificação compilado em 23/08 (conta corrente e fatura):
- **Dona Terezinha** → `alimentacao_fora` / **Juliane** — almoço de trabalho,
  não compra da casa. Antes caía junto com hortifruti/Família.
- **Marcia de Carla, Sumup Marcia de Car** → `alimentacao` / **Hugo**.
  **Zuleika** → `alimentacao` / **Família**. **Discampchoc** →
  `alimentacao` / **Hugo** — supermercado dele, antes ficava sem categoria.
- **Dramarinaortodonto** → `saude` / **Luca** — ortodontia dele.
- **iFood Club** → `assinatura`, não `alimentacao_fora` — é assinatura
  recorrente, não pedido avulso.
- **Kiwify\*MgdMentori** → `educacao_profissional` / **Benetti UP** — mentoria
  de negócio, não estudo pessoal da Juliane. **Kiwify Afiliados** e
  **Kiwify\*InstaMagic** → `ferramentas` / **Benetti UP** — ferramentas de
  trabalho, não curso.
- **Toda categoria `educacao_profissional` é da Benetti UP** (Juliane, 24/08)
  — não só o MgdMentori, generalizado pra qualquer curso/mentoria/treinamento
  (Kiwify, Hotmart, Udemy, Alura etc.): é investimento no negócio, nunca
  estudo pessoal dela. 48 lançamentos corrigidos de uma vez
  (`node scripts/classificar.js aplicar --aplicar`), 41 que ainda estavam em
  Juliane.
- **Uniaosocorro, EC\*2Produtoss** → roupas parceladas, mantido como estava
  (Juliane/pessoal e Família/compras_diversas) para não inventar pessoa que o
  guia não confirmou.
- **PIX TRANSF APE** (extrato) → `casa` / **Família**, locker de guarda-móveis.
  O Itaú emenda a data direto na descrição ("APE25/01"), sem separador — regra
  tinha `\b` no fim do padrão e isso não é fronteira de palavra entre letra e
  dígito, então só a linha mais recente (sem data emendada) batia.
- **PAG TIT INT 237** (R$600–650) → Condomínio; **PAG TIT INT 001** (R$500–600)
  → Escola do Luca; **PAG TIT INT 199060387000** → Escola da Valentina — o
  código depois de "PAG TIT INT" é o banco de liquidação (237=Bradesco,
  001=Banco do Brasil), não o beneficiário: mais de um boleto pode usar o
  mesmo código, por isso a faixa de valor entra como segundo filtro.
- **PIX MARCOS** → receita `aluguel_recebido` / Juliane. **PIX GUILHER** →
  van escolar do Luca, `transporte`/Luca. **PIX EDILEIA** → aluguel de vaga de
  carro, `moradia`/Família. **PIX Nilza** → faxina, `servicos`/Família.
  **PIX STIMA** → contabilidade, `contabilidade`/Benetti UP.
- **FATURA PAGA ITAU UNICLAS** (sem o "S" final) é o pagamento da fatura do
  0442 (Infinite, Benetti UP) — só essa vai para Benetti UP; as demais
  ("FATURAITAU UNICLASS M" etc.) continuam Família, porque compras já
  lançadas uma a uma não podem ser contadas de novo no pagamento.
- Perguntado e **mantido como já estava** (não confirmar de novo): Selva
  Urbana continua `pet`/Família (não saúde/Hugo), e combustível/seguro/
  manutenção do carro do Hugo (Posto das Amoreiras, Correntão, PostoAndrade,
  PostoRiviera, Tokio Marine, Rocha Auto Peças) continuam `transporte` e
  `seguro` / **Família** — o carro serve à casa toda, não é custo isolado do
  táxi dele.
- Descoberto nessa revisão: `classificar.js` aplicava as regras da fatura em
  cima de **todo** lançamento (extrato e holerite incluídos), e coincidências
  de substring corrompiam dado bom — "posto" casava dentro de "Imposto de
  renda retido", "aluguel" reclassificava aluguel recebido como despesa de
  moradia. Corrigido para só atingir `origem: "cartao_credito_itau"`, que é
  o que as regras deste arquivo foram escritas para ler.

### Regra por valor: Clube Azul (24/08)
A Juliane suspeitou de "Azul Linhas Aéreas" duplicada — parcelado e não
parcelado no mesmo dia — e pediu para rastrear contra o cartão de verdade.
Não era bug: são três cobranças reais distintas no cartão 3794 (Itaú
Infinite), todas com texto de descrição quase idêntico ("Azul Linhas
Aereas...", variando só o sufixo) mas significados diferentes —
- uma viagem parcelada de 2025 terminando a 12ª parcela (R$37,80/mês,
  final de cartão virtual 6642);
- a **assinatura do Clube Azul**, R$37,80/mês recorrente, no cartão
  virtual 8929 — confirmada pela Juliane;
- uma compra nova de passagem parcelada em 12x começando out/26 (R$309,60/
  parcela), no mesmo cartão virtual 8929 que a assinatura.

**Nada nesses lançamentos diferencia assinatura de passagem, exceto o
valor** — mesmo texto de descrição, mesmo cartão virtual em dois dos três
casos. `regras-classificacao.json` só comparava por texto até então, então
uma regra por padrão sempre pegaria as três juntas. Adicionado suporte a um
campo opcional `valor` na regra: quando presente, ela só casa se o valor do
lançamento bater (tolerância de 1 centavo) — implementado em `casar()`
(`classificar.js`) e `aplicarRegra()` (`importar-faturas-itau.js`), os dois
pontos que leem esse arquivo. A regra do Clube Azul usa `"padrao": "azul
linhas a"` (pega qualquer variação do texto) `+ "valor": 37.8` — assim só
a assinatura vira `assinatura`/Família; as duas compras de passagem de
verdade continuam `viagem`. Em `cmdExportar` (planilha de revisão em lote),
que agrupa por texto de descrição, o valor comparado é a média do grupo —
não há problema hoje porque cada texto exato do Itaú só aparece com um
valor na base atual.

### Ferramentas de manutenção (`financeiro/scripts/`)
- `conferir-fatura.js arquivo.xlsx [...]` — só leitura. Diz de que mês a fatura
  é de verdade (pelo vencimento), se já está gravada, se o conteúdo bate e qual
  fatura anterior ela quita. Serve para checar um envio antes de importar.
- `importar-faturas-itau.js` — reconstrói tudo a partir dos XLSX. Aceita
  `DIR_FATURAS` por variável de ambiente.
- `importar-holerites.js <pdf|pasta>` — lê os comprovantes de pagamento da
  Elektro. Confere cada um contra o próprio líquido e para se alguma rubrica não
  tiver regra.
- `importar-extrato-itau.js <arquivo.xls>` — lê o extrato da conta corrente.
  Marca como transferência o que outra fonte já lançou, para não contar duas vezes.
- `contas-a-vencer.js [--dias N] [--hoje AAAA-MM-DD]` — só leitura. O que vence
  na janela, com as mesmas regras da tabela de vencimentos do Painel (fatura
  parada e conta paga pela Benetti UP saem à parte, recorrente que falta entra
  pela mediana marcada como previsão, nada é dado como atrasado onde o extrato
  não alcança). É o que alimenta o alerta no celular. `--hoje` só serve para
  testar outra data.
- `importar-extrato-bradesco-cc.js <pdf> [...]` — lê o extrato da conta corrente
  do Bradesco (ag. 2389, c/c 555440-3). Confere a leitura contra o saldo impresso
  e **descobre o sinal do saldo inicial** em vez de supor; recusa gravar se não
  fechar.
- `conciliar.js` — só leitura. Audita as três fontes: o que falta, o que está
  contado duas vezes e o que não bate. Rode depois de cada importação.
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
