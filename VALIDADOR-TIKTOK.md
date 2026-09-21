# Validador de Estoque — TikTok Shop

Avisa no Telegram quando um produto que você está divulgando no TikTok esgota
ou sai do ar, pra você não continuar mandando tráfego pra link morto.

## Como funciona

```
  você cadastra o link         robô roda de 2 em 2h            se esgotou
  na página do validador  ──►  no GitHub Actions:        ──►   manda alerta
         │                     abre a página do produto        no Telegram
         │                     e lê o estoque                        │
         ▼                             │                             ▼
   Supabase (tiktok_estoque_monitor) ◄──┘                    você tira o link
         │                                                       do ar
         └──► a página mostra o status de cada produto
```

A página **não** consegue checar o TikTok sozinha: o navegador bloqueia leitura
de outro site (CORS) e o TikTok bloqueia acesso automatizado. Por isso quem
checa é o robô, e a página só mostra o resultado.

## Arquivos

| Arquivo | O que é |
|---|---|
| `validador-tiktok.html` | A página. Cadastra links e mostra o status. Publicar no VPS. |
| `tiktok-estoque-sync.py` | O robô que checa os produtos. |
| `.github/workflows/tiktok-estoque.yml` | Agenda o robô de 2 em 2 horas. |
| `teste-tiktok-estoque.py` | Testes da lógica de detecção. Rode depois de mexer no robô. |

Tabelas no Supabase: `tiktok_estoque_monitor` (o que vigiar + último status) e
`tiktok_estoque_log` (histórico de cada checagem). Já estão criadas.

## Instalação — 3 passos

### 1. Criar o bot do Telegram (uns 2 minutos)

1. No Telegram, abra **@BotFather** → `/newbot` → escolha um nome.
   Ele devolve um token tipo `7123456789:AAE...`.
2. Mande qualquer mensagem pro seu bot novo (ele só pode te escrever depois disso).
3. Abra **@userinfobot** e mande `/start` — ele devolve seu `Id`, que é o chat id.

### 2. Cadastrar os secrets no GitHub

Em **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | o token do BotFather |
| `TELEGRAM_CHAT_ID` | o número do @userinfobot |
| `SUPABASE_URL` | `https://tkxkrbdvcctoajuigvvv.supabase.co` |
| `SUPABASE_KEY` | a chave anon (a mesma que já está nas páginas) ou a service_role |

Sem os dois primeiros o robô roda igual e marca tudo no painel — só não manda
mensagem. `SUPABASE_URL` e `SUPABASE_KEY` também são opcionais: o script já vem
com o projeto certo por padrão.

### 3. Publicar a página no VPS

Sobe `validador-tiktok.html` pro mesmo VPS da Hostinger onde está a AfiliDash,
do mesmo jeito que o `garimpo-shopee.html`.

## Usando

1. Abre a página, cola o **nome** e o **link** do produto (o link curto de
   afiliado, `vt.tiktok.com/...`, funciona — o robô segue o redirecionamento).
2. Preenche "onde postei" se quiser — isso aparece no alerta do Telegram, pra
   você saber qual vídeo precisa mexer.
3. Pronto. O robô checa na próxima rodada.

Botão **"Checar já"** põe o produto na frente da fila da próxima rodada. Pra
checar na hora mesmo: GitHub → Actions → *Validador de Estoque TikTok* →
**Run workflow**.

### O que cada situação quer dizer

| Situação | Significado |
|---|---|
| 🟢 disponível | Achou sinal claro de que dá pra comprar. |
| ⚠ suspeita (1/2) | Leu "esgotado" **uma vez**. Ainda não te avisei — confirmo na próxima rodada. |
| 🔴 esgotado | Confirmado em duas checagens seguidas. Alerta enviado. |
| 🚫 saiu do ar | O link não existe mais (404) ou joga pra outra página. |
| ⚪ sem leitura | O TikTok não entregou a página (bloqueio/captcha). **Nunca dispara alerta.** |

A regra das duas confirmações existe pra você não receber alerta falso por uma
leitura ruim. Se um produto voltar ao estoque depois de confirmado como
esgotado, o robô também te avisa.

## Calibração (importante)

Não consegui testar o robô contra uma página real do TikTok Shop — o ambiente
onde ele foi escrito não tem acesso de saída pro TikTok. A lógica de detecção
está testada contra páginas sintéticas (`teste-tiktok-estoque.py`, 18 casos),
mas o TikTok pode escrever "esgotado" de um jeito que ainda não está na lista.

**Faça isso com o primeiro produto que você cadastrar:**

```bash
python3 tiktok-estoque-sync.py --url "https://vt.tiktok.com/SEU-LINK/"
```

Ele imprime o diagnóstico completo e salva o HTML lido em `/tmp`. Se der
`indefinido`, abre esse HTML, procura como a página escreve que o produto
acabou, e acrescenta a frase na lista `FRASES_ESGOTADO` (ou o campo JSON em
`RE_JSON_ESGOTADO_FORTE`) lá no topo do script.

Vale testar com **um produto disponível e um esgotado**, pra confirmar que ele
distingue os dois.

## Se aparecer muito "sem leitura"

Significa que o TikTok está barrando o robô — o IP do GitHub Actions é de
datacenter e às vezes cai no captcha. Nessa situação nenhum alerta falso é
disparado, mas você também não é avisada de nada. Opções, da mais simples pra
mais trabalhosa:

1. **Rodar no VPS** em vez do Actions. O IP da Hostinger costuma passar mais
   fácil. Basta um cron:
   `0 */2 * * * cd /caminho/do/repo && /usr/bin/python3 tiktok-estoque-sync.py >> /var/log/tiktok-estoque.log 2>&1`
   (o robô já usa o Playwright quando ele está instalado; sem ele, funciona só
   com a leitura simples).
2. **Usar um serviço de proxy de scraping** (ScraperAPI, ScrapingBee e afins).
3. **Pedir acesso à API oficial** do TikTok Shop Partner Center. É o caminho
   100% confiável, mas depende de aprovação deles.

## Mexendo no robô

Depois de qualquer alteração, roda os testes:

```bash
python3 teste-tiktok-estoque.py
```

Variáveis de ambiente que dá pra ajustar: `CONFIRMACOES` (padrão 2),
`TIMEOUT` (25s), `MAX_POR_RODADA` (60 produtos por rodada).
Se mudar `CONFIRMACOES`, mude também `TTV_CONFIRMACOES` no
`validador-tiktok.html` pra página continuar contando igual.
