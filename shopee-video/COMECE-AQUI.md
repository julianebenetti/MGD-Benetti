# Comece aqui

Tres etapas, uma de cada vez. Faca so a **Etapa 1** agora. Ela nao precisa
de chave, nem de celular, nem de Telegram, e leva uns dois minutos.

---

## Etapa 1 — ver o fluxo funcionando

Abra o terminal do seu VPS pelo painel da Hostinger e cole isto, uma linha
de cada vez:

```bash
cd ~
git clone -b claude/shopee-video-posts-4j236o https://github.com/julianebenetti/MGD-Benetti.git
cd MGD-Benetti/shopee-video
bash instalar.sh
```

Se ja tiver clonado antes, troque as duas primeiras linhas por:

```bash
cd ~/MGD-Benetti && git pull origin claude/shopee-video-posts-4j236o
cd shopee-video && bash instalar.sh
```

**O que voce deve ver no fim:** uma lista com `capa.jpg`, `video.mp4`,
`legenda-shopee-video.txt` e `roteiro.txt`, e a legenda impressa na tela
com a frase "nenhuma palavra repetida".

O `instalar.sh` cria um video de teste sozinho, com um cartao branco no
final imitando o do CapCut. Se ele cortar esse cartao e montar a capa, o
motor esta funcionando.

**Para ver a fila no celular**, ainda na Etapa 1:

```bash
cd demo/saida && python3 -m http.server 8080
```

Abra `http://SEU-IP:8080/app-postagens.html` no celular. Troque `SEU-IP`
pelo IP do VPS. Para fechar o servidor, aperte `ctrl+c`.

**Se der erro:** copie a tela inteira e me mande. Se o erro foi nos testes,
me mande tambem o arquivo `/tmp/testes-shopee.log`.

---

## Etapa 2 — ligar as suas chaves

So depois que a Etapa 1 funcionar.

```bash
cp config.example.env .env
nano .env
```

Preencha:

- `SHOPEE_APP_ID` e `SHOPEE_SECRET` — sao as mesmas que o `shopee-sync.py`
  ja usa. Estao salvas nos secrets do GitHub do seu repositorio.
- `TELEGRAM_BOT_TOKEN` — crie um bot no `@BotFather`, ele devolve o token.
- `TELEGRAM_GRUPO_ID` — o id do grupo dos videos, com o sinal de menos.

Para salvar no nano: `ctrl+o`, `enter`, `ctrl+x`.

Depois adicione o bot ao grupo, desligue o privacy mode dele no `@BotFather`
com `/setprivacy`, e rode:

```bash
set -a; source .env; set +a
python3 pipeline.py --telegram --entregar-telegram --limite 1
```

**O que voce deve ver:** ele pega **um** video novo do grupo, monta a pasta
com os dados reais do produto, preco e comissao, e devolve o video tratado
no chat para voce salvar na galeria.

---

## Etapa 3 — automatizar o app do celular

So depois que a Etapa 2 funcionar.

No celular: ative as **Opcoes do desenvolvedor**, ligue a **Depuracao USB**,
conecte o cabo no computador e aceite o aviso que aparece na tela.

No computador:

```bash
sudo apt install -y adb
adb devices
```

O aparelho tem que aparecer na lista como `device`. Se aparecer
`unauthorized`, desbloqueie a tela e aceite o aviso.

Primeiro rode sem tocar em nada, so para ver o plano:

```bash
python3 automacao_android.py --post demo/saida/*/info.json --simular
```

Depois, valendo, pausando a cada passo:

```bash
python3 automacao_android.py --post saida/PASTA-DO-POST/info.json --confirmar
```

Ele para no rascunho, nao posta sozinho.

**Se ele parar dizendo que nao achou um botao:** e o esperado na primeira
vez. Ele salva um print na pasta `evidencias/` e lista os textos que estavam
na tela. Me mande essa saida e o print, que eu acerto o mapa dos botoes.

---

## Resumo

| Etapa | Precisa de | Prova que |
|---|---|---|
| 1 | nada | o corte, a capa e a legenda funcionam |
| 2 | chaves da Shopee e do Telegram | os dados reais e a entrega chegam |
| 3 | celular com depuracao USB | o app e operado sozinho |

Faca a Etapa 1 e me diga o que apareceu.
