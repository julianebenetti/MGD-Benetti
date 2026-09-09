"""
Gerador de legenda para Shopee Video.

Regra dura: nenhuma palavra pode se repetir em TODO o texto
(descricao + hashtags + palavras de SEO). URLs e numeros nao contam
como palavra. Hashtags compostas sao quebradas nas palavras que as
formam antes da checagem, entao #modafeminina ocupa "moda" e "feminina".
"""
import json
import re
import unicodedata

TOKEN = re.compile(r"[A-Za-zÀ-ÿ]{2,}")
URL = re.compile(r"https?://\S+|\b\S+\.(?:com|br|net|me)\b\S*")

# Produtos que a Juliane nao anuncia (regra do CLAUDE.md).
BLOQUEIO = ("suplement", "vitamin", "colageno", "whey", "creatina",
            "termogenico", "proteina", "bcaa", "glutamina")

LIXO_NOME = {"frete", "gratis", "promocao", "envio", "rapido", "kit", "un",
             "unidade", "cod", "pronta", "entrega", "brasil", "oferta",
             "novo", "nova", "original", "importado", "atacado", "top",
             "barato", "qualidade", "produto", "linha", "modelo", "tipo",
             "com", "sem", "para", "por", "the", "and"}


def normalizar(palavra):
    base = unicodedata.normalize("NFD", palavra.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def radical(palavra):
    """Corta plural e vogal final para que "feminino" e "feminina" colidam.

    A checagem de repeticao roda no radical, nao na palavra crua: a Juliane
    le "vestido/vestida" como a mesma palavra aparecendo duas vezes.
    """
    base = normalizar(palavra)
    if len(base) > 4 and base.endswith("s"):
        base = base[:-1]
    if len(base) > 4 and base[-1] in "aoe":
        base = base[:-1]
    return base


def separar_hashtag(tag):
    """#modafeminina -> ['moda','feminina'] quando as partes sao conhecidas."""
    return [p for p in re.split(r"[#_\s]+", tag) if p]


def palavras_de(texto):
    """Palavras do texto ja reduzidas a radical, sem URLs nem numeros."""
    return [radical(t) for t in TOKEN.findall(URL.sub(" ", texto))]


def palavras_cruas(texto):
    return TOKEN.findall(URL.sub(" ", texto))


class Banco:
    """Controla quais palavras ja foram gastas no texto."""

    def __init__(self):
        self.usadas = set()

    def livre(self, *pecas):
        novas = []
        for peca in pecas:
            for palavra in palavras_de(str(peca)):
                if palavra in self.usadas or palavra in novas:
                    return False
                novas.append(palavra)
        return True

    def gastar(self, *pecas):
        for peca in pecas:
            self.usadas.update(palavras_de(str(peca)))

    def pegar(self, pool, quantidade):
        """Retorna as primeiras `quantidade` opcoes ainda livres do pool."""
        escolhidas = []
        for item in pool:
            if len(escolhidas) == quantidade:
                break
            if self.livre(item):
                self.gastar(item)
                escolhidas.append(item)
        return escolhidas


# ── Vocabulario por categoria ────────────────────────────────────
CATEGORIAS = {
    "moda": {
        "gatilhos": ["vestido", "blusa", "calca", "saia", "camisa", "short",
                     "conjunto", "cropped", "macacao", "jaqueta", "body",
                     "sapatilha", "tenis", "sandalia", "bolsa", "biquini",
                     "lingerie", "pijama", "legging", "casaco", "regata"],
        "adjetivos": ["leve", "macia", "elegante", "versatil", "fluida",
                      "estilosa", "delicada", "confortavel", "moderna"],
        "hashtags": ["moda", "feminina", "look", "estilo", "achadinhos",
                     "tendencia", "guardaroupa", "outfit"],
        "seo": ["roupa", "casual", "verao", "trabalho", "festa", "basica",
                "elastico", "tecido", "caimento", "cintura", "manga",
                "tamanho", "cor", "combinar", "dia"],
    },
    "casa": {
        "gatilhos": ["organizador", "cesto", "cortina", "tapete", "almofada",
                     "luminaria", "prateleira", "suporte", "cabide", "toalha",
                     "lencol", "edredom", "vaso", "jogo"],
        "adjetivos": ["pratico", "resistente", "compacto", "charmoso",
                      "funcional", "duravel", "moderno", "discreto"],
        "hashtags": ["casa", "organizacao", "decoracao", "lar", "achadinhos",
                     "utilidades", "aconchego"],
        "seo": ["ambiente", "quarto", "sala", "cozinha", "banheiro", "espaco",
                "arrumar", "guardar", "otimizar", "gaveta", "armario",
                "limpeza", "rotina", "instalacao"],
    },
    "beleza": {
        "gatilhos": ["batom", "base", "gloss", "mascara", "pincel", "esponja",
                     "perfume", "hidratante", "serum", "shampoo", "escova",
                     "secador", "chapinha", "esmalte", "protetor"],
        "adjetivos": ["cremoso", "duradouro", "suave", "pigmentado",
                      "aveludado", "leve", "profissional", "delicado"],
        "hashtags": ["beleza", "maquiagem", "skincare", "autocuidado",
                     "achadinhos", "makeup", "cabelo"],
        "seo": ["pele", "rosto", "boca", "olhos", "textura", "cobertura",
                "aplicacao", "hidratacao", "brilho", "rotina", "vaidade",
                "resultado", "cheiro", "fixacao"],
    },
    "eletronico": {
        "gatilhos": ["fone", "carregador", "cabo", "caixa", "smartwatch",
                     "mouse", "teclado", "webcam", "power", "adaptador",
                     "ring", "microfone", "suporte", "hub"],
        "adjetivos": ["rapido", "potente", "compacto", "resistente", "leve",
                      "silencioso", "eficiente", "portatil"],
        "hashtags": ["tecnologia", "gadgets", "acessorios", "eletronicos",
                     "achadinhos", "setup", "gamer"],
        "seo": ["bateria", "conexao", "bluetooth", "som", "carga", "usb",
                "celular", "notebook", "sinal", "alcance", "duracao",
                "compatibilidade", "recarga", "cabo"],
    },
    "infantil": {
        "gatilhos": ["bebe", "infantil", "crianca", "menina", "menino",
                     "fralda", "mamadeira", "chupeta", "brinquedo", "berco",
                     "carrinho", "papinha"],
        "adjetivos": ["fofo", "seguro", "macio", "colorido", "lavavel",
                      "resistente", "pratico", "educativo"],
        "hashtags": ["maternidade", "bebe", "infantil", "enxoval",
                     "achadinhos", "criancas", "maes"],
        "seo": ["filho", "idade", "meses", "brincar", "aprender", "seguranca",
                "conforto", "higiene", "sono", "passeio", "presente",
                "material", "atoxico", "cuidado"],
    },
    "pet": {
        "gatilhos": ["pet", "cachorro", "gato", "coleira", "comedouro",
                     "bebedouro", "arranhador", "caminha", "guia", "racao"],
        "adjetivos": ["resistente", "confortavel", "lavavel", "seguro",
                      "macio", "pratico", "ajustavel"],
        "hashtags": ["pets", "cachorros", "gatos", "petshop", "achadinhos",
                     "vidadepet"],
        "seo": ["animal", "passeio", "brincadeira", "alimentacao", "higiene",
                "porte", "tamanho", "material", "limpeza", "descanso",
                "adestramento", "saude", "rotina", "tutor"],
    },
    "cozinha": {
        "gatilhos": ["panela", "airfryer", "liquidificador", "faca", "forma",
                     "tabua", "pote", "garrafa", "copo", "talher", "frigideira",
                     "espremedor", "batedeira"],
        "adjetivos": ["antiaderente", "resistente", "pratico", "facil",
                      "duravel", "compacto", "seguro"],
        "hashtags": ["cozinha", "receitas", "utensilios", "gastronomia",
                     "achadinhos", "chef"],
        "seo": ["preparo", "comida", "fogao", "limpeza", "material", "aco",
                "capacidade", "litros", "tempo", "praticidade", "almoco",
                "jantar", "lavar", "temperatura"],
    },
}

GENERICO = {
    "adjetivos": ["otimo", "bonito", "util", "caprichado", "esperto",
                  "simples", "bacana", "certeiro"],
    "hashtags": ["achadinhos", "shopee", "dica", "promocao", "compras",
                 "oferta", "desejo", "queridinho"],
    "seo": ["comprar", "preco", "avaliacao", "entrega", "desconto",
            "qualidade", "vantagem", "escolha", "novidade", "beneficio",
            "custo", "opcao", "uso", "durabilidade", "presente", "valor"],
}


# Categorias mais especificas primeiro: "body bebe" e infantil, nao moda.
ORDEM = ["infantil", "pet", "beleza", "eletronico", "cozinha", "casa", "moda"]


def detectar_categoria(nome):
    raizes = set(palavras_de(nome))
    for chave in ORDEM:
        dados = CATEGORIAS[chave]
        if any(radical(g) in raizes for g in dados["gatilhos"]):
            return chave
    return None


def eh_bloqueado(nome):
    texto = " ".join(normalizar(t) for t in TOKEN.findall(nome))
    return any(b in texto for b in BLOQUEIO)


def nome_curto(nome, banco, maximo=4):
    """Reduz o titulo gigante da Shopee a poucas palavras uteis."""
    escolhidas = []
    for bruto in TOKEN.findall(nome):
        if len(escolhidas) == maximo:
            break
        limpa = normalizar(bruto)
        if limpa in LIXO_NOME or len(limpa) < 3:
            continue
        if banco.livre(limpa):
            banco.gastar(limpa)
            escolhidas.append(bruto.lower())
    return " ".join(escolhidas)


def _numero(valor):
    if valor is None:
        return None
    if isinstance(valor, float):
        return f"{valor:.1f}".replace(".", ",")
    return f"{valor}"


def montar(produto, link, extras=None):
    """
    produto: dict com nome, preco, nota, vendas, categoria (opcionais).
    link: link de afiliado ja encurtado.
    Retorna dict com descricao, hashtags, seo, texto_final.
    """
    nome = produto.get("nome", "")
    if eh_bloqueado(nome):
        raise ValueError(
            "Produto de suplementacao — a Juliane nao anuncia essa categoria."
        )

    banco = Banco()
    banco.gastar(*(extras or []))

    categoria = produto.get("categoria") or detectar_categoria(nome) or "generico"
    vocab = CATEGORIAS.get(categoria, {})
    adjetivos = vocab.get("adjetivos", []) + GENERICO["adjetivos"]
    pool_tags = vocab.get("hashtags", []) + GENERICO["hashtags"]
    pool_seo = vocab.get("seo", []) + GENERICO["seo"]

    curto = nome_curto(nome, banco)

    linhas = []
    artigo = "essa" if curto.split(" ")[0].endswith("a") else "esse"
    for abertura in ("Achei", "Encontrei", "Descobri", "Olha"):
        if banco.livre(abertura, artigo):
            banco.gastar(abertura, artigo)
            linhas.append(f"{abertura} {artigo} {curto} ✨")
            break
    else:
        linhas.append(f"{curto} ✨")

    tres = banco.pegar(adjetivos, 3)
    if len(tres) == 3 and banco.livre("e"):
        banco.gastar("e")
        linhas.append(f"{tres[0].capitalize()}, {tres[1]} e {tres[2]}.")
    elif tres:
        linhas.append(f"{tres[0].capitalize()}.")

    nota, vendas = _numero(produto.get("nota")), _numero(produto.get("vendas"))
    if nota and vendas and banco.livre("nota", "com", "vendidos"):
        banco.gastar("nota", "com", "vendidos")
        linhas.append(f"Nota {nota} com {vendas} vendidos.")
    elif vendas and banco.livre("mais", "pessoas", "levaram"):
        banco.gastar("mais", "pessoas", "levaram")
        linhas.append(f"Mais de {vendas} pessoas ja levaram.")

    preco = produto.get("preco")
    if preco and banco.livre("sai", "por"):
        banco.gastar("sai", "por")
        linhas.append(f"Sai por R$ {preco}.")

    for fecho in (("Corre", "no", "abaixo"), ("Aproveita", "no", "abaixo"),
                  ("Garante", "pelo", "aqui")):
        if banco.livre(*fecho, "link"):
            banco.gastar(*fecho, "link")
            linhas.append(f"{fecho[0]} {fecho[1]} link {fecho[2]} 👇")
            break

    hashtags = banco.pegar(pool_tags, 5)
    seo = banco.pegar(pool_seo, 10)

    descricao = "\n".join(linhas)
    texto = "\n".join([
        descricao,
        "",
        f"🔗 {link}",
        "",
        " ".join(f"#{h}" for h in hashtags),
        "",
        " · ".join(seo),
    ])
    return {
        "categoria": categoria,
        "descricao": descricao,
        "hashtags": hashtags,
        "seo": seo,
        "texto": texto,
        "conferencia": conferir(texto),
    }


def conferir(texto):
    """Devolve as palavras repetidas. Vazio = legenda dentro da regra."""
    vistas, repetidas = {}, []
    for crua in palavras_cruas(texto):
        raiz = radical(crua)
        if raiz in vistas:
            repetidas.append(f"{crua} (ja usada como {vistas[raiz]})")
        else:
            vistas[raiz] = crua
    return repetidas


if __name__ == "__main__":
    import sys
    produto = json.loads(sys.argv[1])
    print(montar(produto, sys.argv[2])["texto"])
