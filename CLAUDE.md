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

## Card da Central de Post (campanhas de anúncio)
- Formato do card:
  ```
  VEA
  Sub_id: <subid>
  Link: <link completo do produto>
  ID:
  Data campanha: <dd/mm>
  Orçamento: 16,44
  ```
- A primeira linha é sempre **VEA** (nome da página do Instagram onde o anúncio roda).
- O orçamento é sempre **16,44**.
- Regras de lançamento: seguir sempre o artifact **Plano de Lançamentos**
  (https://claude.ai/artifact/Rap9A29zk1wK59LhXMGgrc), com a régua do Sherman, os dias bons
  e o piso de comissão (R$ 15+ por venda com orçamento de 16,44; ideal R$ 20+).
- No campo Sub_id vai só o nome curto do produto: o Central Post acrescenta data + conta
  sozinho (ex.: 05Nov26VEAvestidobabado).

## Busca de produtos para a Juliane
- Sempre listar o link da Shopee de cada produto encontrado (inclusive alternativas e
  parecidos), para ela verificar no app.
