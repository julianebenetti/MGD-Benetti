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
