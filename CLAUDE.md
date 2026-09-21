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

## Validador de Estoque do TikTok Shop
- `validador-tiktok.html` é a página onde a Juliane cadastra os links de produto que
  ela divulga no TikTok; precisa ser publicada no mesmo VPS da AfiliDash.
- Quem checa o estoque é o robô `tiktok-estoque-sync.py`, agendado de 2 em 2 horas
  pelo workflow `.github/workflows/tiktok-estoque.yml`. A página **não** checa nada
  sozinha (CORS + bloqueio do TikTok) — ela só lê o resultado no Supabase.
- Tabelas: `tiktok_estoque_monitor` (o que vigiar + último status) e `tiktok_estoque_log`.
- Alerta de esgotamento vai pro Telegram, e só depois de **duas** leituras seguidas
  dando esgotado. Status `indefinido` (TikTok barrou a leitura) nunca dispara alerta.
- Ao mexer na detecção, rodar `python3 teste-tiktok-estoque.py` e manter
  `CONFIRMACOES` (robô) igual a `TTV_CONFIRMACOES` (página).
- Detalhes de instalação e calibração: `VALIDADOR-TIKTOK.md`.
