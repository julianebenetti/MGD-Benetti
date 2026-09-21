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
- Peça 1 — **alerta com link** (`tiktok-estoque-sync.py`, de 2 em 2h): checa os
  produtos que a Juliane cadastrou e manda no Telegram o link do vídeo + o link do
  produto que quebrou, pra ela trocar direto. Só enxerga o que foi cadastrado.
- Peça 2 — **lembrete diário** (`tiktok-lembrete.py`, 9h de Brasília): rede de
  segurança pro que não foi cadastrado. Lê `tiktok_revisoes` e não envia nada se a
  revisão do dia já foi registrada.
- `validador-tiktok.html` (publicar no VPS junto com a AfiliDash): passo a passo do
  app, botão "Marcar revisão de hoje" e histórico das revisões.
- O robô de estoque **nunca foi calibrado contra uma página real** do TikTok Shop.
  Calibrar com `python3 tiktok-estoque-sync.py --url "<link>"` e ajustar
  `FRASES_ESGOTADO` / `RE_JSON_ESGOTADO_FORTE` conforme o HTML real.
- Tabelas: `tiktok_revisoes`, `tiktok_estoque_monitor`, `tiktok_estoque_log`.
- Ao mexer: rodar `teste-tiktok-lembrete.py` e `teste-tiktok-estoque.py`. Manter
  `CONFIRMACOES` (robô) igual a `TTV_CONFIRMACOES` (página), e a contagem de dias
  sempre no fuso de Brasília nos dois lados.
- Detalhes de instalação: `VALIDADOR-TIKTOK.md`.
