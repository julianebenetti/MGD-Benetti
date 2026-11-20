# Contexto do projeto (MGD-Benetti)

## Nomenclatura
- O dashboard principal se chama **AfiliDash** — não usar mais o nome "BenettiDash".
  `BenettiDash.html` é um arquivo antigo/legado no repositório; não é mais usado.

## Sincronização AfiliDash → Supabase
- A AfiliDash (repo `julianebenetti/afilidash`) foi feita para a Netlify: grava no Supabase pelas funções
  `/.netlify/functions/*`. No VPS elas rodam pelo pacote `afilidash-vps/` deste repositório (serviço
  `afilidash-funcoes`, porta 8791, Nginx do site da AfiliDash). Sem ele, a sincronização para (parou em 25Jul26).

## Hospedagem
- A AfiliDash roda no **VPS da Hostinger** (não é hospedagem compartilhada via hPanel
  File Manager comum — é um VPS). É essa a única hospedagem em uso atualmente.
- `garimpo-shopee.html` (página standalone do Garimpo de Produtos, que conecta no
  mesmo Supabase da aba Garimpo da AfiliDash) precisa ser publicado nesse mesmo VPS,
  não em hospedagem compartilhada separada.

## Garimpo de Produtos — regras de curadoria
- **Nunca buscar/inserir suplementos, vitaminas, colágeno, whey** ou qualquer produto
  de suplementação alimentar/nutricional — a Juliane não anuncia esse tipo de produto,
  mesmo que passe nos critérios de comissão/nota/vendas.
- Piso mínimo de comissão pra um produto entrar no garimpo: R$9,00 (CPA máximo/comissão
  em reais). Abaixo disso nem inserir. **Exceção: 👗 Moda (roupas, calçados, bolsas, acessórios, moda praia,
  fitness, plus size) = R$4,00** (decisão da Juliane em 18Nov26; vale no Garimpo e no PostZap).
- Existe uma rotina diária automática (Routine `Garimpo de Produtos — Curadoria diária`)
  que roda essa curadoria sozinha todo dia às 7h (Brasília). Se precisar ajustar critérios
  de busca no futuro, atualizar o prompt dessa rotina também, não só fazer buscas manuais.
- Essa rotina busca em duas frentes todo dia: categorias gerais (evergreen) e, sempre que
  houver data/temporada comemorativa nos próximos ~90 dias, também busca produtos ligados
  a ela (big_sazonal/microsazonal) — assim o "Top 7 priorizados" não fica só com evergreen.

## Padrões gerais
- **Datas sempre no formato ddMmmaa** com mês abreviado em português: `18Nov26`, `05Out26`
  (Jan Fev Mar Abr Mai Jun Jul Ago Set Out Nov Dez). Com hora: `18Nov26 20:30`. Vale para telas,
  mensagens de WhatsApp/Telegram, Sub IDs da Shopee e nomes de arquivos/campanhas — em todos os apps
  (AfiliDash, PostZap, robô do Shopee Vídeo).

## PostZap (posts.descontoirresistivel.com.br/zap)
- App separado da AfiliDash (pasta `postzap/`), no mesmo VPS, para postar ofertas nos grupos de WhatsApp
  com aprovação. Não mexer em tabelas da AfiliDash nem no robô do Shopee Vídeo (só leitura).
- Links postados sempre convertidos para o link de afiliado da Juliane e rastreáveis (Sub IDs). Formato por grupo: `postzap-grupo07` — SEM data (decisão da Juliane, 20Nov26, pra não ter um link por dia); número tirado do nome do grupo "#07…" (sem número: `g<id>`). Pedidos no privado: `postzap-inbox`.
- **Horários de pico de venda** (estudo do robô do Shopee Vídeo, 05Nov26): **13h–15h, 18h e 20h–21h**; compras por
  impulso; beleza/cabelo = maior parte dos pedidos. Agendar os melhores posts nesses horários.
- **Divulgador do PostZap** (aba 🤖): minera ofertas na Shopee nos horários configurados e manda ao grupo
  FILA POST ZAP (para aprovar ou já aprovadas). Segue as mesmas regras do Garimpo: comissão ≥ R$ 9, nunca
  suplementos/vitaminas/colágeno/whey. Ao mudar critérios de curadoria, ajustar também as palavras/filtros dele.
  **Exceção (decisão da Juliane, 18Nov26): 👗 Moda tem piso de R$ 4** no PostZap (Divulgador e lista de produtos) —
  o público do WhatsApp gosta de produto barato. Os demais nichos continuam com piso de R$ 9.
- **Nichos que mais vendem** (shopee_pedidos, Ago25–Jul26, pedidos concluídos/pendentes): Moda lidera de longe
  (23 mil pedidos, R$ 75,7 mil de comissão — vestido, conjunto e calça são os campeões; calça tem a maior comissão média,
  R$ 6,52), depois Infantil, Beleza, Casa/decoração, Cozinha, Pet, Móveis (ticket R$ 86, comissão média R$ 3,22),
  Eletrônicos e Eletrodomésticos (ticket R$ 91). Horários: Moda e Beleza 20–22h e 10–11h; Eletro 11–14h e 17h;
  Móveis 21h e 13–14h; Casa/decoração espalhado, com 21–22h e 13–17h. Comissão média por pedido é baixa (R$ 1,5–6,5):
  o piso de R$ 9 por produto deixa de fora a maior parte da moda — produtos de moda acima do piso são raros e valiosos.
- **Público dos grupos de WhatsApp:** a maioria foi formada para **moda plus size**; ela também quer mandar **moda evangélica**
  e **itens de Natal**. No PostZap isso é organizado como **temas da mineração** (focos) por cima do nicho (👗 Moda, 🏠 Casa…),
  cada um com liga/desliga e palavras próprias no Divulgador: prontos ➕ Plus Size, ✝️ Evangélica, 🎄 Natal (ligados),
  🎆 Réveillon, ☀️ Verão e praia, 🎒 Volta às aulas, 👙 Moda íntima, 👟 Calçados, 👜 Bolsas e acessórios, 🏋️ Fitness,
  🎁 Presentes, 🧔 Masculino (desligados); ela pode criar outros. Temas ligados a uma categoria usam a cor dela e aparecem
  embaixo dela na grade de horários (Plus Size, Evangélica, Réveillon, Verão, Moda íntima, Calçados, Bolsas, Fitness,
  Masculino → Moda; Natal → Casa; Volta às aulas → Infantil; Presentes = várias categorias). Plus Size e Evangélica são
  independentes (plus size não é só roupa evangélica).
- **💬 Engajamento do PostZap:** mensagem do dia (texto + imagem pela IA da OpenAI, chave do robô do Shopee Vídeo),
  enquete diária "o que querem ver" (votos dão prioridade no Divulgador), "me chama no privado" (quem pede um produto
  recebe as 3 melhores ofertas com Sub ID `inbox`; só responde mensagem que começa com a palavra-gatilho "QUERO", só nos chips
  escolhidos (o chip1 NÃO é o WhatsApp pessoal dela — corrigido em 18Nov26) e fica quieto com quem ela conversou nas últimas 12h) e monitor de grupos de WhatsApp/canais públicos do Telegram (links
  da Shopee viram post com o link dela; cupons viram aviso para revisar). Desde 19Nov26 o engajamento (bom dia, noite, enquete, convites) sai DIRETO pros grupos na hora marcada, sem esperar rajada nem aprovação, e não conta no limite diário de posts; o FILA POST ZAP só recebe aviso.
- **Black Friday 2026: sexta 27Nov26.** Aquecimento dos grupos começou em 18Nov26 (6 posts/dia por grupo, +2/dia, até 20); em 20Nov26 a Juliane subiu o limite para 30 posts/dia por grupo na reta da Black Friday (decisão dela). Acompanhar as saídas de membros no Histórico.
