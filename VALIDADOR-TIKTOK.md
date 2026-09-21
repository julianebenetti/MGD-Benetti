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

### 1. Lembrete diário (é o principal)

Todo dia às 9h da manhã chega uma mensagem no Telegram com o caminho do app
escrito, pra não precisar lembrar de nada.

Ele não é burro: lê a tabela `tiktok_revisoes` e **fica calado se a revisão do
dia já foi feita**. Se estiver há 4 dias ou mais sem revisar, a mensagem muda de
tom. É o que impede o lembrete de virar paisagem.

| Arquivo | O que é |
|---|---|
| `tiktok-lembrete.py` | Monta e envia a mensagem |
| `.github/workflows/tiktok-lembrete.yml` | Dispara todo dia às 12:00 UTC (9h de Brasília) |
| `validador-tiktok.html` | Página com o passo a passo e o botão de marcar a revisão |
| `teste-tiktok-lembrete.py` | Testes do texto e da contagem de dias |

### 2. Vigia de estoque por produto (opcional, desligado)

Um robô que abre a página pública do produto e lê se esgotou. Serve como reforço
e funciona pra produto que ainda nem foi postado — mas **não sabe dizer qual
vídeo** está afetado, e não foi calibrado contra uma página real do TikTok Shop.

Está com o agendamento **desligado**. Roda só na mão: Actions → *Validador de
Estoque TikTok* → Run workflow. Pra religar o automático, descomente as linhas
de `schedule` em `.github/workflows/tiktok-estoque.yml`.

| Arquivo | O que é |
|---|---|
| `tiktok-estoque-sync.py` | O robô de checagem |
| `.github/workflows/tiktok-estoque.yml` | Agendamento (desligado) |
| `teste-tiktok-estoque.py` | 18 testes da detecção |

Tabelas no Supabase (já criadas): `tiktok_revisoes`, `tiktok_estoque_monitor`,
`tiktok_estoque_log`.

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

1. Chega o lembrete às 9h.
2. Abre o TikTok e segue o caminho (também está escrito na página, se esquecer).
3. Troca o produto nos vídeos com aviso vermelho.
4. Volta na página e clica em **Marcar revisão de hoje** — pode anotar quantos
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
