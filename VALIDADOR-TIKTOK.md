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

## Próximo passo em aberto — ler o painel do TikTok direto

O painel do app é o único lugar que enxerga **todos** os vídeos com link
quebrado, inclusive os produtos que nunca foram cadastrados aqui. Ler ele
automaticamente é o que fecharia o buraco de vez.

**Caminho descartado — automação no tablet Android.** Daria pra fazer com
MacroDroid ou Tasker + AutoInput (serviço de Acessibilidade). Dois problemas
mataram a ideia: o tablet da Juliane fica guardado e bloqueado, então um macro
agendado quase nunca rodaria; e o macro leria só o *número* de vídeos com
problema — pegar a lista item a item exigiria rolar e abrir vídeo por vídeo,
o que quebra a cada atualização do app.

**Caminho escolhido — versão web do painel.** A tela existe no navegador, em
`https://business.tiktokshop.com/us/creator?from=portal_v4` (TikTok Shop →
Vídeos → Gerenciar → Links de produtos ocultos → Ver detalhes → Vincular).
Um robô com o cookie de sessão dela pode ler a lista inteira e mandar no
Telegram, rodando no GitHub Actions sem depender de aparelho ligado.

Esse painel é um SPA: monta a tela chamando uma API interna. Ler a API é bem
mais robusto do que raspar o DOM. Duas ferramentas de navegador ajudam a
descobrir isso (ambas read-only, nada sai do navegador dela):

| Ferramenta | Pra que |
|---|---|
| `ferramentas/inspecionar-painel-tiktok.js` | Lista os textos e links da tela — confirma que a tela é a certa |
| `ferramentas/capturar-api-tiktok.js` | Escuta as chamadas da página e devolve o endpoint + a **estrutura** da resposta |

O capturador foi feito pra não vazar dado pessoal: guarda os nomes dos campos
e o tipo de cada um, e só preserva o valor de campos de status
(`status`, `reason`, `sold_out`, `stock`…), que são os que revelam como o
TikTok marca "esgotado". Valores de parâmetros da URL saem mascarados.
Testes: `cd ferramentas && node teste-ferramentas.mjs`.

Com o endpoint e a estrutura em mãos, falta montar:
1. tabela `tiktok_videos_quebrados` (link do vídeo, produto, motivo, detectado_em, resolvido_em);
2. robô que chama a API com o cookie guardado como secret, rodando no Actions;
3. alerta no Telegram com a lista, reaproveitando o formato de `texto_alerta`.

O cookie de sessão vence de tempos em tempos — ela precisará renová-lo. É o
custo real desse caminho, e ainda assim é o menor de todos.
