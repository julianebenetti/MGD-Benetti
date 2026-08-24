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
- 7 abas: Painel, Lançamentos, Para Onde Vai, Cartão & Faturas, Dívidas &
  Patrimônio, Fluxo de Caixa, Imposto de Renda. Importar / Configurações /
  Editor ficam no menu **⚡ Ferramentas**.
- Escopo: **somente 2026** (`ANO_DASHBOARD` em `public/index.html`).
- O mês usado em tudo é `mes_vencimento` (regime de caixa) — quando o dinheiro
  sai da conta, não quando a compra foi feita.

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
- **McDonald's, KFC, rodízio** → `alimentacao_fora`.
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
