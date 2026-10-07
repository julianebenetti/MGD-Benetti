"""
Glossário da Juliane (Método UGC): headlines, hashtags e chamadas do link,
e as regras pra escolher cada uma a partir do nome do produto do TikTok.

Pra editar: troque/adicione linhas nas listas abaixo e reinicie o robô.

Marcadores nas headlines:
  {produto}  termo curto do produto ("cropped", "calça", "vestido"...)
  {esse} {desse} {nesse} {o} {um} {do} {no}  concordam com o gênero do produto
  {o} também serve de terminação: "perfeit{o}" vira perfeito/perfeita ({O} maiúsculo)
  {preco}    preço exato   ("39,90")
  {menos}    preço arredondado pra cima ("40") — usado em "menos de X reais"
"""
import random
import re
import unicodedata
from datetime import date

# ------------------------------------------------------------------ headlines
# (ângulo, texto, precisa_preco, so_roupa)
HEADLINES = [
    # Descrença no preço — preço é o argumento mais forte
    ("preco", "SEM ACREDITAR na beleza {desse} {produto} e o quanto tá custando", False, False),
    ("preco", "Ainda sem acreditar que eu paguei menos de {menos} reais {nesse} {produto}", True, False),
    ("preco", "sem ACREDITAR no valor que eu paguei {nesse} {produto}", False, False),
    ("preco", "IMPACTADA com o valor que eu paguei {nesse} {produto} lind{o}", False, False),
    ("preco", "NINGUÉM acredita quando eu falo que paguei apenas {preco} reais {nesse} {produto}", True, False),
    ("preco", "eu JURO que achei que {esse} {produto} seria muito mais car{o}", False, False),
    ("preco", "impossível acreditar no preço {desse} {produto}", False, False),
    # POV: você encontrou — peça que todo mundo procura
    ("pov", "POV: você encontrou {o} {produto} perfeit{o} quase de graça", False, False),
    ("pov", "POV: você encontrou {o} {produto} mais famos{o} do TikTok praticamente de graça", False, False),
    ("pov", "POV: você encontrou {o} {produto} das blogueiras por menos de {menos} reais", True, False),
    ("pov", "POV: você comprou {o} {produto} perfeit{o} por menos de {menos} reais", True, False),
    ("pov", "POV: você finalmente encontrou {um} {produto} bonit{o} e barat{o}", False, False),
    ("pov", "POV: você encontrou {o} {produto} perfeit{o} no TikTok Shop", False, False),
    # Vale mais do que custa — produto que parece caro
    ("valor", "o TikTok Shop acertou MUITO {nesse} {produto}", False, False),
    ("valor", "{esse} {produto} parece MUITO mais car{o} do que realmente é", False, False),
    ("valor", "o valor {desse} {produto} simplesmente não faz sentido", False, False),
    ("valor", "{esse} {produto} tá com cara de marca cara", False, False),
    ("valor", "sinceramente? {esse} {produto} vale MUITO mais do que custa", False, False),
    ("valor", "{esse} {produto} entrega MUITO mais do que promete", False, False),
    ("valor", "o tipo de compra que vale CADA centavo", False, False),
    # Choque e descoberta — produto pouco conhecido
    ("choque", "SIMM, {esse} {produto} está por menos de {menos} reais", True, False),
    ("choque", "SIMM, {esse} {produto} tá quase de graça", False, False),
    ("choque", "NÃO COMPRE {esse} {produto} se você não quiser ficar extremamente gst0s@", False, True),
    ("choque", "COMO ASSIM {esse} {produto} perfeit{o} por esse preço??", False, False),
    ("choque", "COMO ASSIM ninguém tá falando {desse} {produto}?", False, False),
    ("choque", "eu não tava preparada pra qualidade {desse} {produto}", False, False),
    # Beleza e obsessão — peça bonita que se vende sozinha
    ("beleza", "ainda sem acreditar na beleza {desse} {produto}", False, False),
    ("beleza", "{esse} é oficialmente {o} {produto} mais lind{o} que comprei esse mês", False, False),
    ("beleza", "simplesmente OBCECADA {nesse} {produto}", False, False),
    ("beleza", "sem condições pra beleza {desse} {produto}", False, False),
    ("beleza", "eu comprei sem expectativa e me surpreendi MUITO com {esse} {produto}", False, False),
    ("beleza", "eu finalmente achei {um} {produto} bonit{o}, barat{o} e estilos{o}", False, False),
    # Caimento no corpo — só roupa
    ("caimento", "{esse} {produto} tá deixando qualquer look MUITO mais bonito", False, True),
    ("caimento", "{esse} {produto} veste PERFEITAMENTE", False, True),
    ("caimento", "{esse} {produto} ficou ABSURD{O} no corpo", False, True),
]

# ------------------------------------------------------------------ produtos
# (palavras-chave sem acento, termo usado na headline, gênero m/f, categoria, é roupa)
# A ordem importa: o primeiro que bater ganha.
PRODUTOS = [
    (["biquini"], "biquíni", "m", "praia", True),
    (["maio"], "maiô", "m", "praia", True),
    (["saida de praia"], "saída de praia", "f", "praia", True),
    (["legging", "calca fitness"], "legging", "f", "baixo", True),
    (["conjunto fitness", "top fitness", "conjunto academia"], "conjunto fitness", "m", "fitness", True),
    (["macaquinho"], "macaquinho", "m", "conjunto", True),
    (["macacao"], "macacão", "m", "conjunto", True),
    (["conjunto", "conjuntinho"], "conjuntinho", "m", "conjunto", True),
    (["vestido"], "vestido", "m", "vestido", True),
    (["saia"], "saia", "f", "vestido", True),
    (["cropped"], "cropped", "m", "cima", True),
    (["body"], "body", "m", "cima", True),
    (["corset", "corselet", "corpete"], "corset", "m", "cima", True),
    (["regata"], "regata", "f", "cima", True),
    (["camiseta", "t-shirt", "tshirt"], "camiseta", "f", "cima", True),
    (["camisa"], "camisa", "f", "cima", True),
    (["jaqueta"], "jaqueta", "f", "cima", True),
    (["casaco", "sobretudo"], "casaco", "m", "cima", True),
    (["cardigan", "cardiga"], "cardigã", "m", "cima", True),
    (["moletom"], "moletom", "m", "cima", True),
    (["blazer"], "blazer", "m", "cima", True),
    (["colete"], "colete", "m", "cima", True),
    (["blusa", "blusinha"], "blusinha", "f", "cima", True),
    (["top"], "top", "m", "cima", True),
    (["calca"], "calça", "f", "baixo", True),
    (["bermuda"], "bermuda", "f", "baixo", True),
    (["short"], "short", "m", "baixo", True),
    (["rasteirinha", "rasteira"], "rasteirinha", "f", "calcado", False),
    (["sandalia"], "sandália", "f", "calcado", False),
    (["tenis"], "tênis", "m", "calcado", False),
    (["bota", "coturno"], "bota", "f", "calcado", False),
    (["sapatilha"], "sapatilha", "f", "calcado", False),
    (["scarpin", "salto"], "scarpin", "m", "calcado", False),
    (["chinelo"], "chinelo", "m", "calcado", False),
    (["mochila"], "mochila", "f", "bolsa", False),
    (["bolsa"], "bolsa", "f", "bolsa", False),
    (["colar"], "colar", "m", "acessorio", False),
    (["brinco"], "brinco", "m", "acessorio", False),
    (["pulseira"], "pulseira", "f", "acessorio", False),
    (["oculos"], "óculos", "m", "acessorio", False),
    (["cinto"], "cinto", "m", "acessorio", False),
    (["relogio"], "relógio", "m", "acessorio", False),
]
GENERICO = ("achadinho", "m", "geral", False)

# ------------------------------------------------------------------ hashtags
# Conjuntos de 4 do glossário. (palavras-chave que puxam esse conjunto, hashtags)
# Conjuntos sem palavra-chave são usados quando nenhum específico bate.
HASHTAGS = {
    "cima": [
        (["blusa", "blusinha", "camisa", "camiseta", "regata", "jaqueta", "casaco"],
         "#blusafeminina #modafeminina #tiktokshop #achadinhos"),
        (["cropped", "top"], "#cropped #modafeminina #achadinhostiktok #lookdodia"),
        (["body"], "#bodyfeminino #modafeminina #tiktokshop #lookdodia"),
        (["corset", "corselet", "corpete"], "#corset #modafeminina #achadinhostiktok #achadinhos"),
        ([], "#blusafeminina #modafeminina #tiktokshop #achadinhos"),
    ],
    "vestido": [
        (["longo"], "#vestidolongo #modafeminina #achadinhostiktok #lookdodia"),
        (["saia"], "#saiafeminina #modafeminina #tiktokshop #achadinhos"),
        ([], "#vestidofeminino #modafeminina #tiktokshop #lookdodia"),
    ],
    "baixo": [
        (["legging"], "#legging #modafitness #tiktokshop #achadinhos"),
        (["short"], "#shortjeans #modafeminina #achadinhostiktok #lookdodia"),
        ([], "#calcafeminina #modafeminina #tiktokshop #lookdodia"),
    ],
    "conjunto": [
        (["macacao", "macaquinho"], "#macacao #modafeminina #achadinhostiktok #achadinhos"),
        (["look"], "#lookcompleto #modafeminina #tiktokshop #lookdodia"),
        ([], "#conjuntofeminino #modafeminina #tiktokshop #lookdodia"),
    ],
    "plussize": [
        (["vestido"], "#vestidoplussize #modaplussize #tiktokshop #lookdodia"),
        ([], "#modaplussize #plussize #tiktokshop #achadinhos"),
        ([], "#plussizefashion #modaplussize #achadinhostiktok #lookdodia"),
    ],
    "calcado": [
        (["rasteirinha", "rasteira"], "#rasteirinha #modafeminina #achadinhostiktok #achadinhos"),
        (["sandalia"], "#sandalia #modafeminina #tiktokshop #achadinhos"),
        (["tenis"], "#tenisfeminino #modafeminina #achadinhostiktok #lookdodia"),
        (["bota", "coturno"], "#botafeminina #modafeminina #tiktokshop #lookdodia"),
        ([], "#sandalia #modafeminina #tiktokshop #achadinhos"),
    ],
    "bolsa": [
        (["ombro"], "#bolsadeombro #modafeminina #achadinhostiktok #lookdodia"),
        ([], "#bolsafeminina #modafeminina #tiktokshop #achadinhos"),
    ],
    "acessorio": [
        ([], "#acessorios #modafeminina #tiktokshop #achadinhos"),
    ],
    "praia": [
        (["biquini"], "#biquini #modapraia #achadinhostiktok #lookdeverao"),
        ([], "#modapraia #verao #tiktokshop #achadinhos"),
    ],
    "fitness": [
        ([], "#modafitness #fitnessfeminino #tiktokshop #lookdodia"),
    ],
    "geral": [
        ([], "#achadinhostiktok #tiktokshop #modafeminina #achadinhos"),
        ([], "#tiktokshop #achadinhos #modafeminina #lookdodia"),
        ([], "#achadinhosdatiktokshop #modafeminina #tiktokshop #dicasdemoda"),
    ],
}
# 5ª hashtag fora de temporada (a primeira que ainda não estiver no conjunto)
QUINTA_GENERICA = ["#achadinhosdatiktokshop", "#dicasdemoda", "#achadinhostiktok", "#lookdodia"]

# ------------------------------------------------------------------ chamadas
CHAMADA_ESPECIAL = {
    "conjuntinho": "Loja • PROMO CONJUNTO FEMININO",
    "blusinha": "Loja • PROMO BLUSA FEMININA",
    "calça": "Loja • PROMO CALÇA FEMININA",
    "vestido": "Loja • PROMO VESTIDO FEMININO",
    "tênis": "Loja • PROMO TÊNIS FEMININO",
    "bolsa": "Loja • PROMO BOLSA FEMININA",
}
CHAMADA_GENERICA = "Loja • PROMO DO VÍDEO"


# ------------------------------------------------------------------ lógica
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def tem(n, chaves):
    """Alguma palavra-chave aparece como palavra (aceita plural)?"""
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(s|es)?(?![a-z])", n) for k in chaves)


def identificar(nome):
    """Nome do produto do TikTok → dict com termo, gênero, categoria, roupa."""
    n = " " + sem_acento(nome) + " "
    termo, genero, categoria, roupa = GENERICO
    for chaves, t, g, cat, r in PRODUTOS:
        if tem(n, chaves):
            termo, genero, categoria, roupa = t, g, cat, r
            break
    if "plus size" in n or "plussize" in n or " plus " in n:
        categoria = "plussize"
    return {"termo": termo, "genero": genero, "categoria": categoria, "roupa": roupa, "nome_norm": n}


def temporada(hoje=None):
    """Hashtag de data comemorativa, se houver uma agora (5ª hashtag e chamada)."""
    hoje = hoje or date.today()
    m, d, a = hoje.month, hoje.day, hoje.year
    if m == 11:
        return "#blackfriday", "Loja • BLACK FRIDAY"
    if m == 12 and d <= 25:
        return "#natal", "Loja • PROMO DE NATAL"
    if (m == 12 and d >= 26) or (m == 1 and d <= 2):
        return "#anonovo", None
    if m in (1, 2) or (m == 12) or (m == 3 and d <= 20):
        ano = a + 1 if m == 12 else a
        return f"#verao{ano}", "Loja • LOOK DE VERÃO"
    return None, None


def hashtags(info, hoje=None, rnd=random):
    sets = HASHTAGS.get(info["categoria"], HASHTAGS["geral"])
    especificos = [h for chaves, h in sets if chaves and tem(info["nome_norm"], chaves)]
    genericos = [h for chaves, h in sets if not chaves]
    tags = (especificos[0] if especificos else rnd.choice(genericos or [h for _, h in sets])).split()
    quinta, _ = temporada(hoje)
    if not quinta or quinta in tags:
        quinta = next(h for h in QUINTA_GENERICA if h not in tags)
    return " ".join(tags + [quinta])


def chamada(info, hoje=None):
    _, sazonal = temporada(hoje)
    if sazonal:
        return sazonal
    if info["termo"] == GENERICO[0]:
        return CHAMADA_GENERICA
    if info["categoria"] == "plussize":
        return "Loja • PROMO PLUS SIZE"
    return CHAMADA_ESPECIAL.get(info["termo"], f"Loja • PROMO {info['termo'].upper()}")


def preencher(texto, info, preco):
    m = info["genero"] == "m"
    vals = {
        "produto": info["termo"],
        "esse": "esse" if m else "essa", "desse": "desse" if m else "dessa",
        "nesse": "nesse" if m else "nessa", "o": "o" if m else "a", "O": "O" if m else "A",
        "um": "um" if m else "uma", "do": "do" if m else "da", "no": "no" if m else "na",
        "preco": "", "menos": "",
    }
    if preco:
        vals["preco"] = (f"{preco:.2f}".replace(".", ",")).replace(",00", "")
        vals["menos"] = str(int(preco // 5 * 5 + 5))  # 39,90 → 40 · 40 → 45
    return texto.format(**vals)


def opcoes_headline(info, preco):
    return [(i, ang) for i, (ang, _, precisa_preco, so_roupa) in enumerate(HEADLINES)
            if (preco or not precisa_preco) and (info["roupa"] or not so_roupa)]


def escolher_headline(info, preco, evitar_angulo=None, ja_usadas=(), rnd=random):
    """Retorna (indice, angulo, texto). Evita repetir o ângulo do vídeo anterior."""
    ops = [o for o in opcoes_headline(info, preco) if o[0] not in ja_usadas] \
        or opcoes_headline(info, preco)
    melhores = [o for o in ops if o[1] != evitar_angulo] or ops
    angulo = rnd.choice(sorted({a for _, a in melhores}))
    i = rnd.choice([idx for idx, a in melhores if a == angulo])
    return i, angulo, preencher(HEADLINES[i][1], info, preco)


def ler_legenda(texto):
    """'Cropped canelado manga longa | 39,90' → ('Cropped canelado manga longa', 39.9)."""
    if not texto:
        return None, None
    partes = [p.strip() for p in texto.strip().split("|")]
    nome, preco = partes[0], None
    if len(partes) > 1:
        bruto = partes[1].lower().replace("r$", "").replace("reais", "").strip()
        bruto = bruto.replace(".", "").replace(",", ".") if "," in bruto else bruto
        try:
            preco = float(bruto)
        except ValueError:
            preco = None
    return (nome or None), preco
