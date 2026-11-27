"""
Converte links da Shopee em links de afiliado RASTREÁVEIS e descobre o nome do produto.

Sub-ID no mesmo padrão do robô da Shopee Vídeo (partes separadas; o relatório junta com "-"):
    facebook-<sigla da Página>-<NomeBreve>      ex.: facebook-vea-MacaquinhoCanelado
Se o mesmo produto sair de novo na mesma Página, ganha V2, V3... no nome breve.

As chaves da API de afiliados (SHOPEE_AFFILIATE_APP_ID / SHOPEE_AFFILIATE_SECRET) vêm do .env deste robô ou, se
faltarem, do .env do robô da Shopee Vídeo (SHOPEE_ENV), só leitura. Nada disso é impresso.
Só biblioteca padrão do Python.
"""
import hashlib, json, os, re, time, unicodedata, urllib.error, urllib.request
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

AQUI = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HOSTS = ("shopee.com.br", "shp.ee")
ID_PATTERNS = [re.compile(r"/(?:product|opaanlp)/(?P<shop>\d+)/(?P<item>\d+)"), re.compile(r"-i\.(?P<shop>\d+)\.(?P<item>\d+)")]
CAMPOS = "itemId shopId productName shopName priceMin priceMax ratingStar sales commissionRate"
MAX_NOME = 20


class ErroShopee(Exception):
    pass


def _api_url():
    return os.environ.get("SHOPEE_API_URL", "https://open-api.affiliate.shopee.com.br/graphql")


def eh_shopee(link):
    host = urlparse(link).netloc.lower()
    extras = [h.strip().lower() for h in os.environ.get("SHOPEE_HOSTS_EXTRA", "").split(",") if h.strip()]
    if "sv.shopee" in host or "/share-video/" in link:
        return False  # link de vídeo da Shopee Vídeo não é produto
    return any(host == h or host.endswith("." + h) for h in HOSTS) or host in extras


def credenciais():
    app, seg = os.environ.get("SHOPEE_AFFILIATE_APP_ID", ""), os.environ.get("SHOPEE_AFFILIATE_SECRET", "")
    if app and seg:
        return app, seg
    try:
        arq = Path(os.environ.get("SHOPEE_ENV", "/opt/shopee-video/shopee-video-automation/.env"))
        valores = {}
        for linha in arq.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(SHOPEE_AFFILIATE_APP_ID|SHOPEE_AFFILIATE_SECRET)\s*=\s*(.*?)\s*$", linha)
            if m:
                valores[m.group(1)] = m.group(2).strip("\"'")
        return valores.get("SHOPEE_AFFILIATE_APP_ID", ""), valores.get("SHOPEE_AFFILIATE_SECRET", "")
    except OSError:
        return "", ""


def disponivel():
    a, s = credenciais()
    return bool(a and s)


def extrair_ids(url):
    decodificado = unquote(unquote(url))
    for p in ID_PATTERNS:
        m = p.search(decodificado)
        if m:
            return int(m["shop"]), int(m["item"])
    qs = parse_qs(urlparse(url).query)
    shop, item = (qs.get("shopid") or qs.get("shop_id")), (qs.get("itemid") or qs.get("item_id"))
    if shop and item and shop[0].isdigit() and item[0].isdigit():
        return int(shop[0]), int(item[0])
    return None


def resolver(url):
    """Segue os redirecionamentos de links curtos (s.shopee.com.br, br.shp.ee) e devolve a URL final."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.geturl()
    except urllib.error.HTTPError as e:
        return e.geturl() or url
    except Exception:
        return url


def _gql(texto):
    return json.dumps(str(texto), ensure_ascii=False)


def graphql(query):
    app, seg = credenciais()
    if not (app and seg):
        raise ErroShopee("faltam as chaves da API de afiliados da Shopee")
    corpo = json.dumps({"query": query}, separators=(",", ":"), ensure_ascii=False)
    ts = str(int(time.time()))
    assinatura = hashlib.sha256(f"{app}{ts}{corpo}{seg}".encode()).hexdigest()
    req = urllib.request.Request(_api_url(), data=corpo.encode(), method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app}, Timestamp={ts}, Signature={assinatura}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            dado = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErroShopee(f"a Shopee respondeu {e.code}")
    except Exception as e:
        raise ErroShopee(f"não consegui falar com a Shopee ({e})")
    if dado.get("errors"):
        raise ErroShopee("a Shopee recusou: " + str(dado["errors"][0].get("message", "erro"))[:120])
    return dado["data"]


def produto(shop_id, item_id):
    q = f"{{productOfferV2(shopId:{int(shop_id)},itemId:{int(item_id)},limit:1){{nodes{{{CAMPOS}}}}}}}"
    nos = graphql(q)["productOfferV2"]["nodes"]
    return nos[0] if nos else None


def link_curto(url_origem, sub_ids):
    subs = ",".join(_gql(s) for s in sub_ids)
    q = f"mutation{{generateShortLink(input:{{originUrl:{_gql(url_origem)},subIds:[{subs}]}}){{shortLink}}}}"
    return graphql(q)["generateShortLink"]["shortLink"]


def nome_breve(nome):
    """'Macaquinho Canelado Feminino Brilhoso' -> 'MacaquinhoCaneladoFe' (sem acento/símbolo, até 20 letras)."""
    t = unicodedata.normalize("NFKD", nome or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    palavras = [re.sub(r"[^A-Za-z0-9]", "", p) for p in re.split(r"\s+", t)]
    palavras = [p for p in palavras if p][:3]
    return ("".join(p[:1].upper() + p[1:] for p in palavras))[:MAX_NOME] or "Produto"


def _registro():
    return AQUI / "sub_ids_usados.json"


def sub_ids_para(sigla, nome, reservar=True):
    """Lista de sub_ids ['facebook', 'vea', 'NomeBreve'] (com V2, V3 se já usado nessa Página)."""
    base = nome_breve(nome)
    try:
        usados = set(json.loads(_registro().read_text()))
    except (OSError, ValueError):
        usados = set()
    escolhido, v = base, 2
    while f"facebook-{sigla}-{escolhido}" in usados:
        escolhido, v = f"{base}V{v}", v + 1
    if reservar:
        usados.add(f"facebook-{sigla}-{escolhido}")
        _registro().write_text(json.dumps(sorted(usados)))
    return ["facebook", sigla.lower(), escolhido]


def converter(link, sigla, nome_digitado=""):
    """
    Devolve {'link', 'nome', 'subid', 'item_id', 'shop_id'} ou levanta ErroShopee.
    Resolve o link (curto ou não), acha o produto, lê o nome oficial e gera o link de afiliado com o sub-ID.
    """
    final = resolver(link)
    ids = extrair_ids(final) or extrair_ids(link)
    if not ids:
        raise ErroShopee("não achei o produto nesse link")
    shop_id, item_id = ids
    p = produto(shop_id, item_id)
    nome = (p or {}).get("productName") or nome_digitado
    if not nome:
        raise ErroShopee("não achei o nome do produto")
    subs = sub_ids_para(sigla, nome)
    novo = link_curto(f"https://shopee.com.br/product/{shop_id}/{item_id}", subs)
    return {"link": novo, "nome": nome, "subid": "-".join(subs), "item_id": item_id, "shop_id": shop_id}
