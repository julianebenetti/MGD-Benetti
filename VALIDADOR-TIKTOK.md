# Links do TikTok — revisão e estoque

## O problema real

O TikTok **já detecta sozinho** quando um produto vinculado a um vídeo esgota ou
é removido. No app:

> TikTok → **Vídeos** → **Gerenciar** → filtro **“Links de produtos ocultos”**

Lá aparece o aviso vermelho *“1 links do produto precisam de atenção”*, o motivo
(esgotado ou removido) e o botão **Vincular** pra trocar o produto.

O TikTok só não **avisa**. A Juliane precisa lembrar de entrar lá. É esse o
buraco que este projeto tapa — e, de quebra, aquele painel é melhor do que
qualquer robô externo, porque ele sabe **qual vídeo** está afetado.

## As duas peças

### 1. Alerta com o link (é o que resolve na hora)

Você cadastra na página o **link do produto** e o **link do vídeo** onde ele está
vinculado. De 2 em 2 horas o robô checa esses produtos e, quando um esgota,
chega no Telegram:

```
🔴 PRODUTO ESGOTADO

Calça wide leg bege
O TikTok Shop está mostrando esse produto como esgotado.

🎬 Trocar neste vídeo:
https://www.tiktok.com/@julianebenetti/video/7412345678901234567
📍 vídeo de 18/09

🛒 Produto que quebrou:
https://shop.tiktok.com/view/product/1729419574822508544

🔎 Como detectei: JSON-LD availability=OutOfStock
```

Toca no link do vídeo e já troca o produto. Se você não cadastrar o link do
vídeo, o alerta ensina o caminho no app no lugar dele.

**O limite:** ele só sabe dos produtos que você cadastrar. Ele não descobre
sozinho o que você postou — isso só existe dentro da sua conta logada do TikTok.

| Arquivo | O que é |
|---|---|
| `tiktok-estoque-sync.py` | O robô de checagem |
| `.github/workflows/tiktok-estoque.yml` | Roda de 2 em 2 horas |
| `validador-tiktok.html` | Cadastro dos links e painel de status |
| `teste-tiktok-estoque.py` | Testes da detecção e do texto do alerta |

### 2. Lembrete diário (a rede de segurança)

Cobre o que ficou de fora do cadastro. Todo dia às 9h chega o empurrão pra você
abrir o painel do TikTok, que é quem enxerga **todos** os vídeos com link
quebrado — inclusive os que você nunca cadastrou.

Ele fica calado se a revisão do dia já foi registrada na página, e muda de tom a
partir de 4 dias sem revisão. Quando o robô já confirmou algum produto esgotado,
o lembrete lista esses produtos com os links junto.

| Arquivo | O que é |
|---|---|
| `tiktok-lembrete.py` | Monta e envia a mensagem |
| `.github/workflows/tiktok-lembrete.yml` | Todo dia às 12:00 UTC (9h de Brasília) |
| `teste-tiktok-lembrete.py` | Testes do texto e da contagem de dias |

Tabelas no Supabase (já criadas): `tiktok_estoque_monitor`, `tiktok_estoque_log`,
`tiktok_revisoes`.

## Instalação

### 1. Criar o bot do Telegram (uns 2 minutos)

1. No Telegram, abra **@BotFather** → `/newbot` → escolha um nome.
   Ele devolve um token tipo `7123456789:AAE...`.
2. Mande qualquer mensagem pro seu bot novo (ele só pode te escrever depois disso).
3. Abra **@userinfobot** e mande `/start` — ele devolve seu `Id`, que é o chat id.

### 2. Cadastrar os secrets no GitHub

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor | Obrigatório |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | o token do BotFather | sim |
| `TELEGRAM_CHAT_ID` | o número do @userinfobot | sim |
| `PAGINA_VALIDADOR_URL` | endereço da página no VPS | não — põe o link clicável na mensagem |
| `SUPABASE_URL` / `SUPABASE_KEY` | projeto e chave | não — já vem o certo por padrão |

### 3. Publicar a página no VPS

Sobe `validador-tiktok.html` pro mesmo VPS da Hostinger onde está a AfiliDash,
igual ao `garimpo-shopee.html`.

### 4. Testar sem esperar até amanhã

Actions → *Lembrete Links TikTok* → **Run workflow** (marque `forcar` se você já
registrou a revisão de hoje). Ou, na sua máquina:

```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 tiktok-lembrete.py --teste
```

`--teste` mostra o texto sem enviar.

## O dia a dia

0. **Cada produto que você for divulgar, cadastre na página** — nome, link do
   produto e link do vídeo. É isso que faz o alerta chegar com link.
1. Se algum esgotar, chega o alerta com os dois links. Toca e troca.
2. Uma vez por dia chega o lembrete às 9h (rede de segurança).
3. Abre o TikTok e segue o caminho (também está escrito na página, se esquecer).
4. Troca o produto nos vídeos com aviso vermelho.
5. Volta na página e clica em **Marcar revisão de hoje** — pode anotar quantos
   vídeos corrigiu. Isso silencia o lembrete de hoje e alimenta o histórico.

A página mostra há quantos dias foi a última revisão, quantas revisões e quantos
vídeos você corrigiu nos últimos 30 dias.

## Mudar o horário do lembrete

No `.github/workflows/tiktok-lembrete.yml`, o cron é **sempre em UTC**: some 3
horas ao horário de Brasília. 9h BRT = `0 12 * * *`; 20h BRT = `0 23 * * *`.

## Depois de mexer no código

```bash
python3 teste-tiktok-lembrete.py    # lembrete
python3 teste-tiktok-estoque.py     # robô de estoque
```

Se mudar `CONFIRMACOES` no robô, mude também `TTV_CONFIRMACOES` no
`validador-tiktok.html`.

## Possível melhoria futura

Se aquela tela de “Links de produtos ocultos” existir também no navegador
(Affiliate Creator Center / Seller Center), dá pra um robô logado ler a lista
exata de vídeos com problema e mandar isso no Telegram — em vez de um lembrete
genérico. Precisaria guardar o cookie de sessão como secret e renovar de tempos
em tempos. Vale conferir primeiro se a tela existe no desktop.
