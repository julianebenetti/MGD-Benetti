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

## O que continua na mao

A Shopee nao abre API para isso, entao dois passos ficam com voce, com tudo
ja pronto na pasta de saida:

1. **Favoritar o produto** — o link original fica no `info.json` e na tela.
2. **Subir no Shopee Video e salvar como rascunho** — video em `video.mp4`,
   capa em `capa.jpg`, texto em `legenda.txt`.

## Instalacao

```bash
sudo apt install ffmpeg
pip install -r requisitos.txt
cp config.example.env .env   # preencha as chaves
set -a; source .env; set +a
```

## Uso

```bash
# rodada normal: tudo que apareceu de novo no grupo
python3 pipeline.py --telegram

# um video especifico, sem passar pelo Telegram
python3 pipeline.py --video flow.mp4 --link "https://shopee.com.br/...-i.123.456"
```

Saida:

```
saida/2026-09-20_vestido-longo-feminino/
├── video.mp4       9:16, sem o final do CapCut, realcado, com marca d'agua e capa embutida
├── capa.jpg        1080x1920, pronta para usar como capa do post
├── marca.png       a marca d'agua daquele video
├── legenda.txt     descricao + link + hashtags + SEO
└── info.json       produto, comissao, conferencia da resolucao, o que falta fazer
```

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
