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

## Padrões gerais
- **Datas sempre no formato ddMmmaa** com mês abreviado em português: `18Nov26`, `05Out26`
  (Jan Fev Mar Abr Mai Jun Jul Ago Set Out Nov Dez). Com hora: `18Nov26 20:30`. Vale para telas,
  mensagens de WhatsApp/Telegram, Sub IDs da Shopee e nomes de arquivos/campanhas — em todos os apps
  (AfiliDash, PostZap, robô do Shopee Vídeo).

## PostZap (posts.descontoirresistivel.com.br/zap)
- App separado da AfiliDash (pasta `postzap/`), no mesmo VPS, para postar ofertas nos grupos de WhatsApp
  com aprovação. Não mexer em tabelas da AfiliDash nem no robô do Shopee Vídeo (só leitura).
- Links postados sempre convertidos para o link de afiliado da Juliane e rastreáveis (Sub IDs).
- **Horários de pico de venda** (estudo do robô do Shopee Vídeo, 05Nov26): **13h–15h, 18h e 20h–21h**; compras por
  impulso; beleza/cabelo = maior parte dos pedidos. Agendar os melhores posts nesses horários.
- **Divulgador do PostZap** (aba 🤖): minera ofertas na Shopee nos horários configurados e manda ao grupo
  FILA POST ZAP (para aprovar ou já aprovadas). Segue as mesmas regras do Garimpo: comissão ≥ R$ 9, nunca
  suplementos/vitaminas/colágeno/whey. Ao mudar critérios de curadoria, ajustar também as palavras/filtros dele.
- **Black Friday 2026: sexta 27Nov26.** Aquecimento dos grupos começou em 18Nov26 (6 posts/dia por grupo, +2/dia, até 20).
