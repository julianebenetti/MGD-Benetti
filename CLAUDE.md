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

## Espião TikTok Shop — Moda Feminina
- Página `espiao-tiktok-moda.html` — publicar no mesmo VPS da Hostinger, junto com a
  AfiliDash e o `garimpo-shopee.html`. Lê o mesmo Supabase (`tkxkrbdvcctoajuigvvv`).
- É um módulo **do TikTok Shop**, separado do Garimpo (que é Shopee). A Juliane é
  afiliada do TikTok Shop e usa esse espião pra decidir que vídeo gravar.
- Tabelas: `tiktok_tendencias`, `tiktok_produtos`, `tiktok_videos`, `tiktok_roteiros`,
  `tiktok_criadores`. Namespace `tk*` no JS da página, nunca misturar com `garimpo*`.
- `tiktok_produtos.fonte`: `pesquisa` = veio da varredura automática (sem comissão/link,
  o nome é a categoria campeã); `affiliate_center` = a Juliane colou o produto real do
  Centro de Afiliados do TikTok Shop; `manual` = digitado à mão.
- Mesmo piso do Garimpo: comissão mínima de R$9,00. Mesma proibição de suplementos.
- **Nunca inventar** @ de criador, link de vídeo, nome de seller, número de vendas ou
  comissão. Sem dado verificado, o campo fica NULL.
- Rotina diária `Espião TikTok Shop — Moda Feminina (diário)`, 7h30 (Brasília). Se mudar
  critério de busca no futuro, atualizar o prompt dela também, não só fazer busca manual.

### Dados reais de venda (Kalodata)
- O TikTok não abre faturamento de outro vendedor, e a API oficial de afiliado só cobre a
  própria vitrine. Quem tem GMV por loja/produto é o **Kalodata** (estimativa a partir de
  sinais públicos, **não é dado oficial** — sempre deixar isso claro na tela).
- Fluxo: a Juliane exporta Lojas e Produtos do Kalodata → larga o arquivo em
  `dados-kalodata/` → o workflow `.github/workflows/tiktok-sync.yml` roda o
  `tiktok-sync.py` → grava em `tiktok_lojas` e `tiktok_ranking_produtos`.
- Cada import é um snapshot por `data_ref` + `periodo`. Nunca sobrescrever histórico:
  a página mostra só o snapshot mais recente, mas o passado fica pra comparar evolução.
- `tiktok-sync.py` casa as colunas por apelido (pt-BR e inglês) e aceita `R$ 1.234,56`,
  `987,4 mil`, `1.2M`. Coluna não reconhecida vai pra `colunas_ignoradas` em
  `tiktok_importacoes` — é lá que se descobre o que falta mapear. Use `--dry-run` antes.
- Secrets do GitHub Actions: `SUPABASE_URL` e `SUPABASE_KEY`.
- O `tiktok-sync.py` importa três tipos de export e descobre qual é pelas colunas:
  **Ranking de Produto** (`Informações do produto`, `Receita`, `Itens Vendidos`,
  `Taxa de comissão`…), **Marcas e Lojas**, e **Vídeo e Ads** (`Conteúdo de vídeo`,
  `Visualizações`, `Data de publicação`) — esse último vai pra `tiktok_videos`, e o
  script marca `anuncio = true` quando a legenda tem "AD".
- **A métrica que decide se vale gravar** é o split de receita do produto:
  `receita_live` / `receita_video` / `receita_cartao`. Produto com quase tudo em live
  não vende por vídeo gravado, por mais que o GMV total seja alto. A página mostra isso
  na coluna "Vídeo" (verde ≥30%, amarelo ≥10%, vermelho abaixo disso).
- Comissão do TikTok Shop costuma ser 10% nos campeões de moda feminina, o que em ticket
  de R$20 a R$65 fica **abaixo do piso de R$9**. Filtrar por `Taxa de comissão` e por
  ticket mais alto no Kalodata, senão o ranking vem cheio de produto que não paga.
