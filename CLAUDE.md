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
- A rotina diária deve sempre incluir busca por **moda plus size** (nicho "Moda Plus Size",
  tipo evergreen) como uma das categorias gerais, todo dia — não é opcional nem pontual.
- Classificação fixa de `tipo` sazonal (usar sempre esta tabela, não inferir na hora):
  - **big_sazonal** (temporada ampla, afeta vários nichos ao mesmo tempo, período mais longo):
    Verão (out-fev), Inverno (jun-ago), Black Friday (última sexta de novembro), Natal (25/dez).
  - **microsazonal** (data específica, afeta um nicho por vez, janela mais curta):
    Carnaval (fev-mar, móvel), Páscoa (mar-abr, móvel), Dia da Mulher (8/mar),
    Dia das Mães (2º domingo de maio), Dia dos Namorados (12/jun), Festa Junina (jun),
    Volta às Aulas (jan-fev e jul), Dia dos Pais (2º domingo de agosto),
    Dia do Cliente (15/set), Dia das Crianças (12/out), Halloween (31/out), Ano Novo (31/dez).
  - Não é raro passar dias/semanas sem nenhum produto big_sazonal novo — só existe
    big_sazonal na janela de ~90 dias quando uma dessas 4 datas amplas está próxima.
    Isso é esperado, não é erro nem falha da rotina.
