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

## Links do TikTok — revisão e estoque
- O **TikTok já detecta sozinho** produto esgotado/removido vinculado a vídeo:
  app → Vídeos → Gerenciar → filtro "Links de produtos ocultos" → botão Vincular.
  Ele só não avisa. Esse painel é melhor que qualquer robô externo porque diz
  **qual vídeo** está afetado — não substituir isso por scraping.
- Peça principal: **lembrete diário** (`tiktok-lembrete.py` +
  `.github/workflows/tiktok-lembrete.yml`, 9h de Brasília). Ele lê `tiktok_revisoes`
  e não envia nada se a revisão do dia já foi registrada.
- `validador-tiktok.html` (publicar no VPS junto com a AfiliDash): passo a passo do
  app, botão "Marcar revisão de hoje" e histórico das revisões.
- Peça secundária, **desligada**: `tiktok-estoque-sync.py` checa a página pública do
  produto. Roda só por workflow_dispatch. Nunca foi calibrado contra página real do
  TikTok Shop; se for religar, calibrar antes com `--url`.
- Tabelas: `tiktok_revisoes`, `tiktok_estoque_monitor`, `tiktok_estoque_log`.
- Ao mexer: rodar `teste-tiktok-lembrete.py` e `teste-tiktok-estoque.py`. Manter
  `CONFIRMACOES` (robô) igual a `TTV_CONFIRMACOES` (página), e a contagem de dias
  sempre no fuso de Brasília nos dois lados.
- Detalhes de instalação: `VALIDADOR-TIKTOK.md`.
