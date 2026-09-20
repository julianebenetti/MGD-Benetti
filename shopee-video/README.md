# Postagens da Shopee Video

Automatiza a parte repetitiva do fluxo: pega o video no grupo do Telegram,
edita, aplica a sua identidade, monta a legenda e gera o link de afiliado.
Entrega uma pasta por video, pronta para subir.

## O que roda sozinho

| Passo | Como |
|---|---|
| Pegar o video no grupo do Telegram | Bot API, pareando cada video com o link da Shopee que veio junto |
| Enquadrar em 9:16 (1080x1920) | ffmpeg, com fundo desfocado para nao cortar o produto |
| Tirar o cartao "Criado com CapCut" | deteccao do ultimo corte de cena nos segundos finais |
| Realce de imagem e som | leve ajuste de contraste e saturacao, volume normalizado |
| Marca d'agua | PNG gerado da sua identidade, ou o seu proprio arquivo |
| Capa do post | escolhe o melhor quadro do video e monta a arte com selo, titulo, preco e nota |
| Conferir a resolucao | valida resolucao, duracao, tamanho e faixa de audio antes de voce subir |
| Descricao + 5 hashtags + 10 palavras de SEO | gerador proprio, sem repetir nenhuma palavra |
| Link de afiliado | `generateShortLink` da Affiliate API, com sub_id de rastreio |

## O fluxo, na ordem do app

O roteiro segue exatamente a sequencia do aplicativo. Os quatro primeiros
itens ja saem prontos; os demais sao os passos do app, com os dados do post
preenchidos.

**Ja pronto pela Lia:** video tratado · capa montada · legenda escrita ·
produto identificado.

**No app da Shopee:**

1. Salvar o video na galeria (ele chega pelo Telegram)
2. Abrir o aplicativo da Shopee
3. Acessar o produto que vai divulgar
4. Favoritar o produto, que e o que o faz aparecer em Adicionar Produto
5. Entrar na area de video
6. Selecionar um video da galeria
7. Escolher o video
8. Adicionar legenda
9. Ativar as opcoes do conteudo
10. Tocar em Adicionar Produto
11. Localizar o produto na lista, com o termo de busca que o roteiro sugere
12. Tocar em Adicionar
13. Conferir as informacoes do produto
14. Tocar em Feito
15. Voltar para a tela de publicacao
16. Postar, ou salvar o rascunho para validar antes

Cada post sai com esse roteiro em `roteiro.txt` e no app de postagens, com
caixinha para marcar o que ja foi feito.

## Automacao do app (ADB)

`automacao_android.py` executa os passos dentro do app da Shopee. Ele roda
no computador e comanda o celular por ADB, procurando cada botao pelo texto
que aparece na tela.

```bash
python3 automacao_android.py --post saida/2026-09-20_vestido/info.json --simular
python3 automacao_android.py --post saida/2026-09-20_vestido/info.json --confirmar
```

Por padrao ele para no rascunho. `--postar` publica de verdade.

### Rodar tudo dentro do tablet, sem computador

Com Android 11 ou mais novo o aparelho liga o adb nele mesmo, entao o
tablet trata o video e opera o app sozinho. Instale o Termux pelo F-Droid e
rode `bash instalar-termux.sh`, depois `bash conectar-adb.sh` para o
pareamento. O passo a passo detalhado esta em COMECE-AQUI.md.

Duas coisas importantes nesse modo: ligue o `termux-wake-lock` antes, para
o Termux nao dormir quando o app da Shopee vier para a frente, e nao toque
na tela enquanto a automacao roda.

### Preparar o celular pelo computador, uma vez so

1. Ative **Opcoes do desenvolvedor** e a **Depuracao USB**.
2. Ligue o cabo e aceite o aviso de depuracao que aparece na tela.
3. No computador, instale o ADB (`sudo apt install adb`) e confira com
   `adb devices`, que deve listar o aparelho como `device`.
4. Instale o **ADBKeyBoard** no celular. Sem ele o Android so aceita ASCII,
   entao a legenda perde acento e emoji.

### Calibracao

Os rotulos que o script procura estao em `mapa-telas.json`, um por tela. Se
o app mudar um texto, a automacao para, salva um print em `evidencias/` e
lista o que estava visivel. Basta acrescentar o rotulo novo no arquivo.

Rode a primeira vez com `--confirmar`, que pausa antes de cada passo. Assim
da para acompanhar e parar no meio sem estrago.

### O que ele decide sozinho

Na galeria as miniaturas nao tem texto, entao ele pega a primeira, que e o
video recem-enviado, e salva um print para voce conferir. Se preferir
escolher na mao, toque no video e rode com `--continuar`, que ele segue da
legenda em diante.

## App de postagens

`app-postagens.html` e a fila no celular. Ele le o `posts.json` que o
pipeline gera e mostra, para cada post: a capa, o botao de baixar o video,
o botao de copiar a legenda, o link do produto e os passos do app em forma
de checklist. O que voce marca fica salvo no proprio aparelho.

O arquivo e copiado para a pasta de saida a cada rodada, entao basta servir
essa pasta no VPS e abrir o endereco no celular. Da para adicionar a tela de
inicio como os outros apps.

## Instalacao

```bash
sudo apt install ffmpeg
pip install -r requisitos.txt
cp config.example.env .env   # preencha as chaves
set -a; source .env; set +a
```

## Uso

```bash
# rodada normal: tudo que apareceu de novo no grupo, com o video de volta no chat
python3 pipeline.py --telegram --entregar-telegram

# um video especifico, sem passar pelo Telegram
python3 pipeline.py --video flow.mp4 --link "https://shopee.com.br/...-i.123.456"
```

Saida:

```
saida/
├── app-postagens.html          a fila para abrir no celular
├── posts.json                  o que o app le
└── 2026-09-20_vestido-longo-feminino/
    ├── video.mp4               9:16, sem o final do CapCut, realcado, com marca e capa
    ├── capa.jpg                1080x1920, pronta para usar como capa do post
    ├── marca.png               a marca d'agua daquele video
    ├── legenda-shopee-video.txt  a que voce cola no app, sem link colado
    ├── legenda.txt             a versao com link, para TikTok e Instagram
    ├── roteiro.txt             o passo a passo com os dados deste post
    └── info.json               produto, comissao, conferencia da resolucao
```

Sao duas legendas de proposito. No Shopee Video o produto entra pela
etiqueta do botao Adicionar Produto, entao a chamada aponta para ela e nao
para um link colado. A versao com link fica para as outras redes. As duas
passam pela mesma regra de nao repetir palavra.

## Personalizacao

Tudo que define a sua cara esta em `identidade.json`, e vale para a capa e
para a marca d'agua ao mesmo tempo:

| Campo | Para que |
|---|---|
| `handle` | o @ que assina a capa e o video |
| `cor_principal` / `cor_secundaria` | selo, estrela da nota e caixa do preco |
| `fonte` | caminho de um `.ttf` da sua marca; vazio usa uma fonte do sistema |
| `logo` | PNG que entra na capa e na marca d'agua |
| `marca` | posicao, tamanho, opacidade e a caixinha de fundo |
| `capa` | modelo, texto do selo, quantas palavras e linhas no titulo |
| `video` | forca do realce e se o audio e normalizado |
| `specs` | o que a conferencia final exige do arquivo |

A capa tem tres modelos: `faixa` (degrade no rodape), `cartao` (bloco
arredondado atras do texto) e `minimo` (so titulo e assinatura, sem selos).

O quadro da capa e escolhido automaticamente: o script testa dez quadros
espalhados pelo video e fica com o mais nitido e colorido, ignorando o
trecho que foi cortado no final. `--capa-em 4.5` manda usar um segundo
especifico. A arte ainda entra embutida no mp4 como poster.

### Opcoes que costumam ser uteis

| Opcao | Para que |
|---|---|
| `--modelo-capa cartao` | troca o layout da capa nessa rodada |
| `--capa-em 4.5` | escolhe o quadro da capa na mao |
| `--selo ""` | tira o selo da capa |
| `--sem-capa` | nao gera capa |
| `--logo logo.png` | usa o seu logo na capa e na marca |
| `--marca marca.png` | usa um PNG pronto no lugar da marca gerada |
| `--posicao superior-direito` | move a marca d'agua |
| `--modo cover` | corta as bordas em vez de usar fundo desfocado |
| `--cortar-fim 3.5` | corta um tempo fixo do final |
| `--sem-auto-outro` | nao mexe no final do video |
| `--sem-realce` | mantem cor e volume originais |
| `--nome "..."` | nome do produto quando a API nao responde |
| `--limite 5` | processa so os 5 primeiros da rodada |
| `--entregar-telegram` | devolve o video tratado e a legenda no chat, para salvar na galeria |

E na automacao do app:

| Opcao | Para que |
|---|---|
| `--simular` | mostra o plano sem tocar no celular |
| `--confirmar` | pausa antes de cada passo |
| `--continuar` | segue do editor, com o video ja escolhido na tela |
| `--postar` | publica em vez de salvar rascunho |
| `--serial` | escolhe o aparelho, se houver mais de um |

## A regra de nao repetir palavra

A checagem roda sobre o texto inteiro — descricao, hashtags e SEO juntos — e
compara **radicais**, entao "feminino" e "feminina" contam como a mesma
palavra. Hashtags compostas sao quebradas antes: `#modafeminina` ocupa
"moda" e "feminina". URLs e numeros ficam de fora da conta.

Quando um termo ja foi gasto, o gerador pula para o proximo do vocabulario da
categoria. `info.json` guarda o resultado da conferencia; `[]` quer dizer que
nao sobrou repeticao.

## Regras de curadoria

O gerador recusa produto de suplementacao e avisa quando a comissao fica
abaixo de R$ 9,00, seguindo o que ja vale para o Garimpo.

## Limites conhecidos

- O Bot API do Telegram so baixa arquivos ate 20 MB. Video maior precisa vir
  comprimido ou passar por um Bot API local.
- O bot so enxerga as mensagens do grupo com o privacy mode desligado.
- A deteccao do outro do CapCut assume um cartao final de 1 a 5 segundos. Fora
  disso ela desiste e corta 3 s; use `--cortar-fim` para mandar no tempo.
- Os limites em `specs` sao um palpite conservador do que a Shopee aceita. Se o
  app reclamar de algo diferente, ajuste o arquivo em vez do codigo.

## Testes

```bash
python3 testes.py
```
