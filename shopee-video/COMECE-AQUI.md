# Comece aqui

Escolha por onde rodar:

- **So com o tablet Android, sem notebook** → va para a [Etapa 1-T](#etapa-1-t--tudo-dentro-do-tablet).
  E o caminho mais curto, e o unico que automatiza o app de verdade.
- **No VPS da Hostinger** → comece pela Etapa 1 abaixo. O VPS trata os
  videos sozinho todo dia, mas nao consegue tocar na tela do tablet.

O ideal, no fim, e os dois: o VPS preparando os videos e o tablet postando.

---

## Etapa 1-T — tudo dentro do tablet

O tablet faz tudo: corta o video, monta a capa, escreve a legenda e depois
opera o app da Shopee sozinho. Precisa de Android 11 ou mais novo.

### 1. Instalar o Termux

Baixe pelo **F-Droid**, nao pela Play Store. A versao da Play Store esta
parada ha anos e nao instala os pacotes certos.

- F-Droid: `https://f-droid.org/packages/com.termux/`

### 2. Colar isto no Termux

```bash
pkg install -y git
cd ~
git clone -b claude/shopee-video-posts-4j236o https://github.com/julianebenetti/MGD-Benetti.git
cd MGD-Benetti/shopee-video
bash instalar-termux.sh
```

Demora uns minutos na primeira vez. No meio ele pede acesso ao
armazenamento: toque em **Permitir**.

**O que voce deve ver no fim:** a lista com `capa.jpg`, `video.mp4`,
`legenda-shopee-video.txt` e `roteiro.txt`, e a legenda na tela com a frase
"nenhuma palavra repetida".

Para ver a capa e o video na galeria:

```bash
cp demo/saida/*/capa.jpg demo/saida/*/video.mp4 ~/storage/movies/
```

### 3. Ligar o adb do tablet nele mesmo

E o que permite a automacao tocar na tela.

```bash
bash conectar-adb.sh
```

O script conduz o pareamento. Antes de rodar, deixe pronto no tablet:
Ajustes → Sobre o tablet → sete toques em "Numero da versao", depois
Ajustes → Sistema → Opcoes do desenvolvedor → ligar a **Depuracao sem fio**.

Atencao a um detalhe que confunde todo mundo: sao **dois enderecos
diferentes**. O do pareamento aparece na janelinha do codigo de 6 digitos.
O da conexao aparece na tela principal da depuracao sem fio. O script pede
um de cada vez.

### 4. Rodar a automacao

```bash
termux-wake-lock
python3 automacao_android.py --post demo/saida/*/info.json --confirmar
```

O `--confirmar` pausa antes de cada passo, entao da para acompanhar e parar
no meio. Ele para no rascunho, nao posta sozinho.

Enquanto roda, **nao toque na tela**. Quem esta tocando e o script, e um
toque seu no meio atrapalha.

**Se ele parar dizendo que nao achou um botao:** e o esperado na primeira
vez, porque eu nao tenho um tablet aqui para conferir os nomes reais dos
botoes. Ele salva um print em `evidencias/` e lista os textos que estavam na
tela. Me mande isso que eu acerto o mapa.

---

## Etapa 1 — ver o fluxo funcionando (no VPS)

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

## Etapa 3 — automatizar o app pelo notebook

Este caminho e para quando voce estiver com o notebook. Rodando tudo no
tablet, a Etapa 1-T ja cobre isso.

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
| 1-T | so o tablet, com Termux | tudo junto, do corte ate o app |
| 1 | so o VPS | o corte, a capa e a legenda funcionam |
| 2 | chaves da Shopee e do Telegram | os dados reais e a entrega chegam |
| 3 | notebook com o cabo | o app e operado a partir do computador |

Sem notebook agora, faca a **Etapa 1-T** e me diga o que apareceu.
