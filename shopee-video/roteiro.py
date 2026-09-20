"""
Roteiro de publicacao, na ordem em que o app da Shopee pede.

Os quatro primeiros itens ja saem prontos da Lia. Os catorze seguintes sao
os passos do app, com os dados do post preenchidos: qual produto abrir, o
que digitar na busca do "Adicionar Produto" e qual legenda colar.
"""

PREPARO = "preparo"
APP = "app"


def termo_busca(nome, palavras=4):
    """O que digitar para achar o produto na lista do Adicionar Produto."""
    import legenda

    escolhidas = []
    for bruto in legenda.TOKEN.findall(nome or ""):
        limpa = legenda.normalizar(bruto)
        if limpa in legenda.LIXO_NOME or len(limpa) < 3:
            continue
        escolhidas.append(bruto)
        if len(escolhidas) == palavras:
            break
    return " ".join(escolhidas) or (nome or "")


def montar(resumo):
    """Devolve os passos do post, ja com nome de produto, arquivos e textos."""
    produto = resumo.get("produto") or {}
    nome = produto.get("nome", "produto")
    loja = produto.get("loja")
    capa = "capa.jpg" if resumo.get("capa") else None
    video = resumo["video"]["saida"].split("/")[-1]
    busca = termo_busca(nome)

    passos = [
        {"etapa": PREPARO, "titulo": "Video tratado",
         "detalhe": f"{video} em 9:16, sem o final do CapCut, com marca d'agua"},
        {"etapa": PREPARO, "titulo": "Capa montada",
         "detalhe": capa or "sem capa nesta rodada"},
        {"etapa": PREPARO, "titulo": "Legenda escrita",
         "detalhe": "legenda-shopee-video.txt, sem palavra repetida"},
        {"etapa": PREPARO, "titulo": "Produto identificado",
         "detalhe": f"{nome}" + (f" — {loja}" if loja else "")},

        {"etapa": APP, "n": 0, "titulo": "Salvar o video na galeria",
         "detalhe": "abra o video que a Lia mandou no Telegram e salve no celular"},
        {"etapa": APP, "n": 1, "titulo": "Abrir o aplicativo da Shopee",
         "detalhe": ""},
        {"etapa": APP, "n": 2, "titulo": "Acessar o produto que vai divulgar",
         "detalhe": resumo.get("link_original", "")},
        {"etapa": APP, "n": 2.5, "titulo": "Favoritar o produto",
         "detalhe": "e o que faz ele aparecer depois em Adicionar Produto"},
        {"etapa": APP, "n": 3, "titulo": "Entrar na area de video",
         "detalhe": "a partir da pagina do produto"},
        {"etapa": APP, "n": 4, "titulo": "Selecionar um video da galeria",
         "detalhe": f"escolha o {video}, que e o tratado"},
        {"etapa": APP, "n": 5, "titulo": "Escolher o video",
         "detalhe": "ele abre no editor da Shopee"},
        {"etapa": APP, "n": 6, "titulo": "Adicionar legenda",
         "detalhe": "cole o texto de legenda-shopee-video.txt"},
        {"etapa": APP, "n": 7, "titulo": "Ativar as opcoes do conteudo",
         "detalhe": "as chavinhas da tela de edicao"},
        {"etapa": APP, "n": 8, "titulo": "Tocar em Adicionar Produto",
         "detalhe": "abre a lista de produtos"},
        {"etapa": APP, "n": 9, "titulo": "Localizar o produto na lista",
         "detalhe": f'busque por "{busca}"'},
        {"etapa": APP, "n": 10, "titulo": "Tocar em Adicionar",
         "detalhe": "o produto passa a aparecer nas informacoes do conteudo"},
        {"etapa": APP, "n": 11, "titulo": "Conferir as informacoes do produto",
         "detalhe": "secao Editar informacoes do produto, no rodape"},
        {"etapa": APP, "n": 12, "titulo": "Tocar em Feito",
         "detalhe": "conclui a vinculacao"},
        {"etapa": APP, "n": 13, "titulo": "Voltar para a tela de publicacao",
         "detalhe": "o produto continua vinculado"},
        {"etapa": APP, "n": 14, "titulo": "Postar ou salvar rascunho",
         "detalhe": "botao vermelho Postar; para validar antes, salve o rascunho"},
    ]
    return {"passos": passos, "termo_busca": busca, "texto": texto(resumo, passos)}


def texto(resumo, passos):
    linhas = [f"ROTEIRO — {(resumo.get('produto') or {}).get('nome', 'produto')}", ""]
    linhas.append("JA PRONTO PELA LIA")
    for passo in [p for p in passos if p["etapa"] == PREPARO]:
        detalhe = f" — {passo['detalhe']}" if passo["detalhe"] else ""
        linhas.append(f"  [x] {passo['titulo']}{detalhe}")
    linhas += ["", "NO APP DA SHOPEE"]
    for passo in [p for p in passos if p["etapa"] == APP]:
        detalhe = f"\n         {passo['detalhe']}" if passo["detalhe"] else ""
        linhas.append(f"  [ ] {passo['titulo']}{detalhe}")
    return "\n".join(linhas) + "\n"
