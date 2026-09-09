"""
Ponte com a Shopee Affiliate Open API.

Faz duas coisas a partir do link que chega no Telegram:
  1. descobre qual e o produto (nome, preco, nota, vendas, comissao);
  2. devolve o link curto de afiliado ja rastreado.

Usa as mesmas credenciais do shopee-sync.py: SHOPEE_APP_ID e SHOPEE_SECRET.
"""
import hashlib
import json
import os
import re
import time
import urllib.request

URL = "https://open-api.affiliate.shopee.com.br/graphql"
TIMEOUT = 30

# https://shopee.com.br/produto-i.123.456  |  /product/123/456
PADRAO_I = re.compile(r"-i\.(\d+)\.(\d+)")
PADRAO_PRODUCT = re.compile(r"/product/(\d+)/(\d+)")


def _credenciais():
    app_id = os.environ.get("SHOPEE_APP_ID")
    secret = os.environ.get("SHOPEE_SECRET")
    if not app_id or not secret:
        raise RuntimeError(
            "Defina SHOPEE_APP_ID e SHOPEE_SECRET (mesmas chaves do shopee-sync.py)."
        )
    return app_id, secret


def consultar(query):
    app_id, secret = _credenciais()
    corpo = json.dumps({"query": query}, separators=(",", ":"))
    ts = str(int(time.time()))
    assinatura = hashlib.sha256((app_id + ts + corpo + secret).encode()).hexdigest()
    req = urllib.request.Request(
        URL,
        data=corpo.encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": (
                f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={assinatura}"
            ),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resposta:
        dados = json.loads(resposta.read())
    if dados.get("errors"):
        raise RuntimeError(f"Shopee respondeu com erro: {dados['errors']}")
    return dados.get("data", {})


def expandir(link):
    """Segue o redirect de s.shopee.com.br ate a URL longa do produto."""
    req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resposta:
            return resposta.geturl()
    except Exception:
        return link


def ids_do_link(link):
    """Extrai (shop_id, item_id) da URL do produto. Devolve None se nao achar."""
    alvo = link if PADRAO_I.search(link) or PADRAO_PRODUCT.search(link) else expandir(link)
    achado = PADRAO_I.search(alvo)
    if achado:
        return int(achado.group(1)), int(achado.group(2))
    achado = PADRAO_PRODUCT.search(alvo)
    if achado:
        return int(achado.group(1)), int(achado.group(2))
    return None


CAMPOS = ("itemId shopId productName shopName priceMin priceMax "
          "commissionRate sales ratingStar imageUrl productLink offerLink")


def _formatar(no):
    preco = no.get("priceMin") or no.get("priceMax")
    comissao = float(no.get("commissionRate") or 0)
    preco_num = float(preco) if preco else 0.0
    return {
        "nome": no.get("productName", ""),
        "loja": no.get("shopName", ""),
        "preco": f"{preco_num:.2f}".replace(".", ",") if preco_num else None,
        "preco_num": preco_num,
        "nota": round(float(no.get("ratingStar") or 0), 1) or None,
        "vendas": int(no.get("sales") or 0) or None,
        "comissao_pct": round(comissao * 100, 1),
        "comissao_reais": round(preco_num * comissao, 2),
        "imagem": no.get("imageUrl"),
        "item_id": no.get("itemId"),
        "shop_id": no.get("shopId"),
    }


def buscar_produto(link):
    """Dados do produto a partir do link. Cai para busca por palavra-chave."""
    ids = ids_do_link(link)
    if ids:
        shop_id, item_id = ids
        dados = consultar(
            "{ productOfferV2(itemId: %d, shopId: %d, limit: 1) { nodes { %s } } }"
            % (item_id, shop_id, CAMPOS)
        )
        nos = (dados.get("productOfferV2") or {}).get("nodes") or []
        if nos:
            return _formatar(nos[0])

    chave = palavra_chave_do_link(link)
    if chave:
        dados = consultar(
            '{ productOfferV2(keyword: "%s", limit: 1) { nodes { %s } } }'
            % (chave, CAMPOS)
        )
        nos = (dados.get("productOfferV2") or {}).get("nodes") or []
        if nos:
            return _formatar(nos[0])
    return None


def palavra_chave_do_link(link):
    """Usa o slug da URL como termo de busca quando os ids falham."""
    alvo = expandir(link)
    slug = alvo.split("?")[0].rstrip("/").split("/")[-1]
    slug = re.sub(r"-i\.\d+\.\d+$", "", slug)
    termo = " ".join(slug.replace("-", " ").split()[:6])
    return termo.replace('"', "") if len(termo) > 3 else None


def link_afiliado(link, sub_ids=None):
    """Encurta e rastreia. sub_ids marca a origem, ex: ['shopee_video']."""
    subs = json.dumps(sub_ids or ["shopee_video"])
    dados = consultar(
        '{ generateShortLink(input: {originUrl: "%s", subIds: %s})'
        " { shortLink shortLinkList } }" % (link.replace('"', ""), subs)
    )
    bloco = dados.get("generateShortLink") or {}
    curto = bloco.get("shortLink") or (bloco.get("shortLinkList") or [None])[0]
    if not curto:
        raise RuntimeError("A Shopee nao devolveu link curto para essa URL.")
    return curto
