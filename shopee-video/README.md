# Postagens da Shopee Video

Automatiza a parte repetitiva do fluxo: pega o video no grupo do Telegram,
trata o video, monta a legenda e gera o link de afiliado. Entrega uma pasta
por video, pronta para subir.

## O que roda sozinho

| Passo | Como |
|---|---|
| Pegar o video no grupo do Telegram | Bot API, pareando cada video com o link da Shopee que veio junto |
| Enquadrar em 9:16 (1080x1920) | ffmpeg, com fundo desfocado para nao cortar o produto |
| Tirar o cartao "Criado com CapCut" | deteccao do ultimo corte de cena nos segundos finais |
| Marca d'agua | PNG seu, ou texto quando nao ha PNG |
| Descricao + 5 hashtags + 10 palavras de SEO | gerador proprio, sem repetir nenhuma palavra |
| Link de afiliado | `generateShortLink` da Affiliate API, com sub_id de rastreio |

## O que continua na mao

A Shopee nao abre API para isso, entao dois passos ficam com voce, com tudo
ja pronto na pasta de saida:

1. **Favoritar o produto** — o link original fica no `info.json` e na tela.
2. **Subir no Shopee Video e salvar como rascunho** — video em `video.mp4`,
   texto em `legenda.txt`, link de afiliado para colar no post.

## Instalacao

Precisa de Python 3 e ffmpeg com `drawtext` (o pacote normal do apt tem):

```bash
sudo apt install ffmpeg
cp config.example.env .env   # preencha as chaves
set -a; source .env; set +a
```

## Uso

```bash
# rodada normal: tudo que apareceu de novo no grupo
python3 pipeline.py --telegram --marca marca.png

# um video especifico, sem passar pelo Telegram
python3 pipeline.py --video flow.mp4 --link "https://shopee.com.br/...-i.123.456"
```

Saida:

```
saida/2026-09-09_vestido-longo-feminino/
├── video.mp4       9:16, sem o final do CapCut, com marca d'agua
├── legenda.txt     descricao + link + hashtags + SEO
└── info.json       produto, comissao, avisos, o que falta fazer
```

### Opcoes que costumam ser uteis

| Opcao | Para que |
|---|---|
| `--modo cover` | corta as bordas em vez de usar fundo desfocado |
| `--cortar-fim 3.5` | corta um tempo fixo do final, ignorando a deteccao |
| `--sem-auto-outro` | nao mexe no final do video |
| `--posicao superior-direito` | move a marca d'agua |
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

## Testes

```bash
python3 testes.py
```
