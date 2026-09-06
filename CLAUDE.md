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
- **O Kalodata tem API oficial** (Centro Aberto): `POST https://www.kalodata.com/openapi/v1/…`,
  JSON, chave secreta no cabeçalho, limite de 100 chamadas a cada 10 segundos, e é **paga por
  chamada** (a conta tem saldo de créditos). Aceita `region: BR`, `language: pt-BR`,
  `currency: BRL` e `date_range: last7Day`. O cliente é o `kalodata-api.py`.
  Padrão dos caminhos: `/tiktok/<familia>/detail` e `/tiktok/<familia>/rank`, para as
  famílias video, product, shop, creator, category e live. Confirmados na doc:
  `video/detail`, `video/rank`, `shop/detail`, `shop/rank` e `product/detail`; os demais
  seguem o padrão mas ainda não foram vistos, e estão marcados como "provável" no
  dicionário ENDPOINTS.
- `product/detail` já entrega `video_revenue` e `live_revenue` separados, então o split
  que decide se vale gravar vem pronto da fonte, sem precisar calcular.
- Para filtrar por categoria (`category_ids`) é preciso descobrir o id de "Roupas
  femininas e roupas íntimas femininas". Esse id vem dos endpoints de `category`, que
  ainda não foram documentados aqui.
- **Limite de taxa é por endpoint**: os `/detail` aceitam 100 chamadas a cada 10 segundos,
  os `/rank` só 10. O cliente controla isso por caminho, com 20% de folga.
- **A API separa a receita da loja por canal**: `affiliate_revenue`, `self_account_revenue`
  e `shoppingmall_revenue`. A fatia de afiliado é o filtro que importa — loja que fatura
  com afiliado é loja acostumada a trabalhar com criador, e é onde a Juliane consegue
  entrar. Dá pra ordenar o ranking direto por `affiliate_revenue`. A página mostra isso
  na coluna "Afiliado" (verde ≥40%, amarelo ≥15%, vermelho abaixo).
- `shop/detail` ainda traz `top3_product_ids`, `creator_number` (quantos criadores já
  disputam a loja), `video_number`, `live_number` e `seller_type` (BRAND ou RETAILER).
- O `/tiktok/video/rank` limita a janela a 30 dias e traz até 100 linhas por chamada.
  Aceita filtrar por `product_id` (é o equivalente à aba Vídeo e Ads da interface),
  `shop_id`, `creator_id`, `category_ids`, `keyword`, faixa de receita, faixa de
  seguidores, faixa de ROAS e `is_ai_video`. Ordena por qualquer campo numérico da
  resposta via `sort_field`.
- Nunca fazer uma chamada por produto — sempre usar os endpoints de lista, senão o crédito
  evapora. `--testar` gasta exatamente 1 chamada.
- O campo `video_gpm` da API é a receita por mil visualizações já calculada. É o número que
  substitui a conta manual de quanto vale o alcance.
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
- **Cauda longa**: nos 8 vídeos que mais faturaram a Calça Pantalona entre 30/08 e 05/09,
  nenhum foi postado dentro dessa janela — o mais novo tinha 18 dias, o mais velho 66,
  média de 38. Vídeo de moda continua vendendo por semanas, então a estratégia é acumular
  volume, não caçar viral. Isso está registrado como tendência no banco.
- **Referência de conversão** medida no top 8 de vídeos da Calça Pantalona (30/08~05/09):
  261.830 visualizações geraram 252 vendas, ou seja **0,096%, ~1 venda a cada 1.000 views**,
  e isso variou pouquíssimo entre vídeos (0,088% a 0,104%). Serve de régua: alcance é o que
  muda o resultado, não a conversão. Quem decide o quanto sobra é a comissão — a R$5,65 por
  venda dá ~R$5,44 por 1.000 views; com 20% de comissão o mesmo alcance dobra pra ~R$10,88.
