"""
Cliente da API do Kalodata -> Supabase (Espião TikTok Shop)

Substitui o export manual de CSV: puxa os dados direto da API oficial do Kalodata
e grava nas mesmas tabelas que o tiktok-sync.py alimenta.

Uso:
    python kalodata-api.py --testar              # 1 chamada só, confere se a chave funciona
    python kalodata-api.py --video 7404191282148511007
    python kalodata-api.py --ranking-videos --paginas 2
    python kalodata-api.py --videos-do-produto 1729587769570529799

Variáveis de ambiente:
    KALODATA_KEY     obrigatória — a chave criada em Conta no Centro Aberto do Kalodata
    KALODATA_HEADER  nome do cabeçalho que leva a chave (padrão: secret-key)
    SUPABASE_URL     padrão: projeto da AfiliDash
    SUPABASE_KEY     obrigatória pra gravar

CUIDADO COM CRÉDITO: a API do Kalodata é paga por chamada. Este script nunca faz
uma chamada por produto — sempre prefira os endpoints de lista, que trazem tudo
de uma vez. O --testar gasta exatamente 1 chamada.

O QUE AINDA PRECISA SER CONFIRMADO NA DOCUMENTAÇÃO:
  1. O nome exato do cabeçalho da chave (a doc diz "secret-key nos cabeçalhos",
     mas não mostra o nome). Ajuste em KALODATA_HEADER ou na variável de ambiente.
  2. Os endpoints marcados como "provável" em ENDPOINTS. Confirmados pela doc:
     video/detail, video/rank e shop/detail. Os outros seguem o mesmo padrão
     (/tiktok/<familia>/detail e /tiktok/<familia>/rank), mas não foram vistos.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

BASE = "https://www.kalodata.com/openapi/v1"

# Caminho, situação e limite de taxa (chamadas por 10 segundos), conforme a doc.
# Os endpoints de /rank são bem mais restritos que os de /detail.
ENDPOINTS = {
    "video_detalhe":     ("/tiktok/video/detail",    "confirmado", 100),
    "video_ranking":     ("/tiktok/video/rank",      "confirmado",  10),
    "loja_detalhe":      ("/tiktok/shop/detail",     "confirmado", 100),
    "loja_ranking":      ("/tiktok/shop/rank",       "confirmado",  10),
    "produto_detalhe":   ("/tiktok/product/detail",  "confirmado", 100),
    "produto_ranking":   ("/tiktok/product/rank",    "provável",    10),
    "criador_ranking":   ("/tiktok/creator/rank",    "provável",    10),
    "categoria_ranking": ("/tiktok/category/rank",   "provável",    10),
}

# Padrões do Brasil, conforme a lista de valores aceitos na documentação
PADRAO = {"region": "BR", "language": "pt-BR", "currency": "BRL", "date_range": "last7Day"}

KALODATA_KEY    = os.environ.get("KALODATA_KEY", "")
KALODATA_HEADER = os.environ.get("KALODATA_HEADER", "secret-key")
SUPABASE_URL    = os.environ.get("SUPABASE_URL", "https://tkxkrbdvcctoajuigvvv.supabase.co")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY", "")

# Cada endpoint tem seu limite. Guardo o instante da última chamada por caminho
# e espero o suficiente pra ficar com folga abaixo do teto.
_ultima_chamada = {}


def chamar(nome_endpoint, corpo):
    """Uma chamada POST na API. Devolve o dict de resposta ou levanta erro claro."""
    global _ultima_chamada
    if not KALODATA_KEY:
        raise SystemExit("Falta a variável de ambiente KALODATA_KEY.")

    caminho, situacao, teto = ENDPOINTS[nome_endpoint]
    intervalo = 10.0 / teto * 1.2  # 20% de folga
    espera = intervalo - (time.time() - _ultima_chamada.get(caminho, 0.0))
    if espera > 0:
        time.sleep(espera)
    _ultima_chamada[caminho] = time.time()

    payload = json.dumps({**PADRAO, **corpo}).encode()
    req = urllib.request.Request(
        BASE + caminho, data=payload, method="POST",
        headers={"Content-Type": "application/json", KALODATA_HEADER: KALODATA_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resposta = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode()[:500]
        if e.code in (401, 403):
            raise SystemExit(
                f"A API recusou a chave (HTTP {e.code}).\n"
                f"Cabeçalho usado: {KALODATA_HEADER!r}. Se a doc do Kalodata usar outro nome,\n"
                f"defina KALODATA_HEADER com o nome certo.\nResposta: {detalhe}")
        if e.code == 404 and situacao == "provável":
            raise SystemExit(
                f"O caminho {caminho!r} não existe. Ele estava marcado como provável.\n"
                f"Abra '{nome_endpoint}' no Centro Aberto do Kalodata e corrija ENDPOINTS "
                f"no topo deste arquivo.")
        raise SystemExit(f"A API respondeu {e.code}: {detalhe}")

    if not resposta.get("success"):
        raise SystemExit(
            f"A API respondeu success=false.\n"
            f"code: {resposta.get('code')}\nmessage: {resposta.get('message')}\n"
            f"Se falar em crédito ou saldo, recarregue no Centro Aberto antes de rodar de novo.")
    return resposta


# ── Supabase ─────────────────────────────────────────────────────────────
def supabase(metodo, caminho, corpo=None, headers=None):
    if not SUPABASE_KEY:
        raise SystemExit("Falta a variável de ambiente SUPABASE_KEY.")
    cabecalhos = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                  "Content-Type": "application/json"}
    cabecalhos.update(headers or {})
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{caminho}",
                                 data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texto = r.read().decode()
            return json.loads(texto) if texto.strip() else []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Supabase respondeu {e.code}: {e.read().decode()[:500]}")


def gravar(tabela, registros, conflito):
    if not registros:
        return 0
    for i in range(0, len(registros), 200):
        supabase("POST", f"{tabela}?on_conflict={conflito}", registros[i:i + 200],
                 {"Prefer": "resolution=merge-duplicates,return=minimal"})
    return len(registros)


# ── Vídeo ────────────────────────────────────────────────────────────────
def montar_video(d, periodo, data_ref):
    """Traduz a resposta de /tiktok/video/detail pra uma linha de tiktok_videos."""
    arroba = d.get("belonged_creator_handle")
    return {
        "video_id":          d.get("video_id"),
        "arroba":            f"@{arroba}" if arroba and not str(arroba).startswith("@") else arroba,
        "criador_id":        d.get("belonged_creator_id"),
        "gancho":            d.get("video_title"),
        "produtos_no_video": d.get("product_number"),
        "receita":           d.get("revenue"),
        # a API escreve "sales_volumn" mesmo, com o erro de digitação
        "itens_vendidos":    d.get("sales_volumn", d.get("sales_volume")),
        "views":             d.get("views"),
        "gpm":               d.get("video_gpm"),
        "ads_views":         d.get("ads_views"),
        "ads_roas":          d.get("ads_roas"),
        "ad_cpa":            d.get("ad_cpa"),
        "proporcao_ads":     d.get("ad_view_ratio"),
        "likes":             d.get("digg_count"),
        "compartilhamentos": d.get("share_count"),
        "comentarios":       d.get("comment_count"),
        "duracao_seg":       int(d["duration"]) if d.get("duration") is not None else None,
        "anuncio":           d.get("ad") == 1,
        "video_ia":          d.get("ai_video") == 1,
        "link_video":        f"https://www.tiktok.com/@{arroba}/video/{d.get('video_id')}"
                             if arroba and d.get("video_id") else None,
        "periodo":           periodo,
        "data_ref":          data_ref,
        "data_deteccao":     data_ref,
        "fonte":             "kalodata",
    }


def buscar_video(video_id, periodo, data_ref, gravar_no_banco=True):
    resposta = chamar("video_detalhe", {"video_id": video_id, "date_range": periodo_api(periodo),
                                        "need_extra": False})
    linha = montar_video(resposta.get("data") or {}, periodo, data_ref)
    print(json.dumps(linha, ensure_ascii=False, indent=1))
    if gravar_no_banco:
        gravar("tiktok_videos", [linha], "video_id")
        print("Gravado em tiktok_videos.")
    return linha


def montar_video_rank(d, periodo, data_ref):
    """Traduz uma linha de /tiktok/video/rank. Tem menos campos que o detail,
    mas traz crescimento da receita e a fatia de receita vinda de anúncio."""
    arroba = d.get("belonged_creator_handle")
    return {
        "video_id":              d.get("video_id"),
        "arroba":                f"@{arroba}" if arroba and not str(arroba).startswith("@") else arroba,
        "criador_id":            d.get("belonged_creator_id"),
        "gancho":                d.get("video_title"),
        "receita":               d.get("revenue"),
        "views":                 d.get("views"),
        "crescimento_pct":       d.get("revenue_growth_rate"),
        "ads_roas":              d.get("ads_roas"),
        "likes":                 d.get("digg_count"),
        "compartilhamentos":     d.get("share_count"),
        "comentarios":           d.get("comment_count"),
        "proporcao_receita_ads": d.get("ad_revenue_ratio"),
        "proporcao_ads":         d.get("ad_view_ratio"),
        "data_postagem":         (d.get("creator_debut") or "")[:10] or None,
        "anuncio":               d.get("ad") == 1,
        "video_ia":              d.get("ai_video") == 1,
        "link_video":            f"https://www.tiktok.com/@{arroba}/video/{d.get('video_id')}"
                                 if arroba and d.get("video_id") else None,
        "periodo":               periodo,
        "data_ref":              data_ref,
        "data_deteccao":         data_ref,
        "fonte":                 "kalodata",
    }


def buscar_ranking_videos(periodo, data_ref, paginas=1, por_pagina=100,
                          produto_id=None, loja_id=None, categorias=None,
                          palavra=None, so_organico=False, dry_run=False):
    """Puxa o ranking de vídeos. Uma chamada traz até 100 linhas — sempre prefira
    aumentar por_pagina a fazer várias chamadas."""
    todos = []
    for pagina in range(1, paginas + 1):
        corpo = {
            "date_range": periodo_api(periodo),
            "sort_field": {"field": "revenue", "type": "DESC"},
            "page_size": min(por_pagina, 100),
            "page_number": pagina,
        }
        if produto_id:  corpo["product_id"] = produto_id
        if loja_id:     corpo["shop_id"] = loja_id
        if categorias:  corpo["category_ids"] = categorias
        if palavra:     corpo["keyword"] = palavra
        resposta = chamar("video_ranking", corpo)
        linhas = resposta.get("data") or []
        print(f"  página {pagina}: {len(linhas)} vídeo(s)")
        todos += [montar_video_rank(d, periodo, data_ref) for d in linhas]
        if len(linhas) < corpo["page_size"]:
            break

    if so_organico:
        antes = len(todos)
        todos = [v for v in todos if not v["anuncio"]]
        print(f"  filtrei os impulsionados: {antes} → {len(todos)}")

    com_id = [v for v in todos if v.get("video_id")]
    print(f"  {len(com_id)} vídeo(s) com id, prontos pra gravar")
    if com_id:
        print(f"  exemplo: {json.dumps(com_id[0], ensure_ascii=False)[:260]}")
    if dry_run:
        print("  (dry-run: nada foi gravado)")
        return com_id
    gravar("tiktok_videos", com_id, "video_id")
    print(f"  {len(com_id)} linha(s) gravada(s) em tiktok_videos.")
    return com_id


def montar_loja(d, periodo, data_ref):
    """Traduz uma loja, tanto de /shop/detail quanto de /shop/rank.
    A doc escreve alguns campos de dois jeitos, então leio os dois."""
    def pega(*nomes):
        for n in nomes:
            if d.get(n) is not None:
                return d[n]
        return None
    return {
        "loja_id":           d.get("shop_id"),
        "loja":              d.get("shop_name"),
        "gmv":               d.get("revenue"),
        "receita_afiliados": d.get("affiliate_revenue"),
        "receita_propria":   pega("self_account_revenue", "self_promotion_revenue"),
        "receita_shopping":  pega("shoppingmall_revenue", "shopping_mall_revenue"),
        "unidades":          pega("sales_volumn", "sales_volume"),
        "preco_medio":       d.get("unit_price"),
        "criadores":         d.get("creator_number"),
        "produtos_ativos":   pega("product_number", "on_sell_product_count"),
        "videos":            d.get("video_number"),
        "lives":             d.get("live_number"),
        "crescimento_pct":   d.get("revenue_growth_rate"),
        "tipo_loja":         pega("seller_type", "shop_type"),
        "top3_produtos":     d.get("top3_product_ids"),
        "imagem_url":        d.get("image_url"),
        "categorias":        d.get("category_list"),
        "ranking":           d.get("rank"),
        "periodo":           periodo,
        "data_ref":          data_ref,
        "fonte":             "kalodata",
    }


def buscar_ranking_lojas(periodo, data_ref, paginas=1, por_pagina=100,
                         ordenar_por="revenue", categorias=None, palavra=None,
                         tipo_loja=None, faixa_receita=None, dry_run=False):
    """Ranking de lojas. Ordene por affiliate_revenue pra achar quem já vende
    com criador, não só quem vende muito."""
    todas = []
    for pagina in range(1, paginas + 1):
        corpo = {
            "date_range": periodo_api(periodo),
            "sort_field": {"field": ordenar_por, "type": "DESC"},
            "page_size": min(por_pagina, 100),
            "page_number": pagina,
            "need_category": 1,
        }
        if categorias:     corpo["category_ids"] = categorias
        if palavra:        corpo["keyword"] = palavra
        if tipo_loja:      corpo["shop_type"] = tipo_loja
        if faixa_receita:  corpo["revenue_range"] = faixa_receita
        resposta = chamar("loja_ranking", corpo)
        linhas = resposta.get("data") or []
        print(f"  página {pagina}: {len(linhas)} loja(s)")
        todas += [montar_loja(d, periodo, data_ref) for d in linhas]
        if len(linhas) < corpo["page_size"]:
            break

    for i, loja in enumerate(todas, start=1):
        if loja.get("ranking") is None:
            loja["ranking"] = i
    com_id = [l for l in todas if l.get("loja_id") and l.get("loja")]
    print(f"  {len(com_id)} loja(s) pronta(s) pra gravar")
    if com_id:
        print(f"  exemplo: {json.dumps(com_id[0], ensure_ascii=False)[:280]}")
    if dry_run:
        print("  (dry-run: nada foi gravado)")
        return com_id
    gravar("tiktok_lojas", com_id, "loja_id,periodo,data_ref")
    print(f"  {len(com_id)} linha(s) gravada(s) em tiktok_lojas.")
    return com_id


def buscar_loja(loja_id, periodo, data_ref, dry_run=False):
    resposta = chamar("loja_detalhe", {"shop_id": loja_id,
                                       "date_range": periodo_api(periodo),
                                       "need_extra": False})
    linha = montar_loja(resposta.get("data") or {}, periodo, data_ref)
    print(json.dumps(linha, ensure_ascii=False, indent=1))
    if not dry_run and linha.get("loja_id"):
        gravar("tiktok_lojas", [linha], "loja_id,periodo,data_ref")
        print("Gravado em tiktok_lojas.")
    return linha


def montar_produto(d, periodo, data_ref):
    """Traduz /tiktok/product/detail. O ouro aqui é video_revenue x live_revenue:
    diz na hora se o produto vende por vídeo gravado ou só ao vivo."""
    def pega(*nomes):
        for n in nomes:
            if d.get(n) is not None:
                return d[n]
        return None
    receita = d.get("revenue")
    preco_min, preco_max = d.get("min_price"), d.get("max_price")
    return {
        "produto_id":        d.get("product_id"),
        "produto":           d.get("product_name"),
        "loja_id":           d.get("product_shop_id"),
        "loja":              d.get("shop_name"),
        "cat_principal_id":  d.get("pri_cate_id"),
        "cat_secundaria_id": d.get("sec_cate_id"),
        "cat_terciaria_id":  d.get("ter_cate_id"),
        "preco_min":         preco_min,
        "preco_max":         preco_max,
        "preco":             preco_min if preco_min == preco_max else None,
        "preco_medio":       pega("unit_price", "avg_price"),
        "gmv":               receita,
        "receita_video":     d.get("video_revenue"),
        "receita_live":      d.get("live_revenue"),
        "unidades":          pega("sales_volumn", "sales_volume"),
        "criadores":         d.get("creator_number"),
        "videos":            d.get("video_number"),
        "crescimento_pct":   d.get("revenue_growth_rate"),
        "comissao_percentual": pega("commission_rate", "commission"),
        "avaliacao":         pega("rating", "review_score"),
        "imagem_url":        d.get("image_url"),
        "periodo":           periodo,
        "data_ref":          data_ref,
        "fonte":             "kalodata",
    }


def buscar_produto(produto_id, periodo, data_ref, dry_run=False):
    resposta = chamar("produto_detalhe", {"product_id": produto_id,
                                          "date_range": periodo_api(periodo),
                                          "need_image": 1, "need_extra": False})
    linha = montar_produto(resposta.get("data") or {}, periodo, data_ref)
    print(json.dumps(linha, ensure_ascii=False, indent=1))
    if linha.get("gmv") and linha.get("receita_video") is not None:
        fatia = float(linha["receita_video"]) / float(linha["gmv"]) * 100
        print(f"\nFatia de vídeo: {fatia:.1f}% da receita "
              f"({'vale gravar' if fatia >= 30 else 'vende mais ao vivo que por vídeo'})")
    if not dry_run and linha.get("produto_id") and linha.get("produto"):
        gravar("tiktok_ranking_produtos", [linha], "produto_id,periodo,data_ref")
        print("Gravado em tiktok_ranking_produtos.")
    return linha


PERIODOS = {"1d": "lastDay", "7d": "last7Day", "30d": "last30Day"}


def periodo_api(periodo):
    # O ranking de vídeos limita a janela a 30 dias, então fico nesse conjunto.
    if periodo not in PERIODOS:
        raise SystemExit(f"--periodo aceita {', '.join(PERIODOS)}.")
    return PERIODOS[periodo]


def testar():
    """Gasta 1 chamada só, com os parâmetros de exemplo da própria documentação."""
    print(f"Base: {BASE}")
    print(f"Cabeçalho da chave: {KALODATA_HEADER}")
    print(f"Chave: {'definida' if KALODATA_KEY else 'AUSENTE'}")
    print("Chamando /tiktok/video/detail com o exemplo da doc (1 chamada)…\n")
    resposta = chamar("video_detalhe", {
        "region": "US", "language": "en-US", "currency": "USD",
        "date_range": "last7Day", "video_id": "7404191282148511007", "need_extra": False})
    print(json.dumps(resposta, ensure_ascii=False, indent=1)[:1500])
    print("\nA chave funciona. Pode rodar as buscas de verdade.")


def main():
    args = sys.argv[1:]
    if not args or "--ajuda" in args or "-h" in args:
        print(__doc__)
        print("Situação dos endpoints:")
        for nome, (caminho, situacao, teto) in ENDPOINTS.items():
            print(f"  {nome:18} {caminho:26} {situacao:11} {teto:>3} chamadas/10s")
        return

    periodo, data_ref = "7d", date.today().isoformat()
    video_id = produto_id = loja_id = palavra = produto_detalhe_id = None
    ordenar_por, tipo_loja = "revenue", None
    paginas, por_pagina = 1, 100
    dry_run = "--dry-run" in args
    so_organico = "--so-organico" in args
    i = 0
    while i < len(args):
        if args[i] == "--periodo" and i + 1 < len(args):
            periodo = args[i + 1]; i += 2
        elif args[i] == "--data" and i + 1 < len(args):
            data_ref = args[i + 1]; i += 2
        elif args[i] == "--video" and i + 1 < len(args):
            video_id = args[i + 1]; i += 2
        elif args[i] == "--videos-do-produto" and i + 1 < len(args):
            produto_id = args[i + 1]; i += 2
        elif args[i] == "--videos-da-loja" and i + 1 < len(args):
            loja_id = args[i + 1]; i += 2
        elif args[i] == "--produto" and i + 1 < len(args):
            produto_detalhe_id = args[i + 1]; i += 2
        elif args[i] == "--loja" and i + 1 < len(args):
            loja_id = args[i + 1]; i += 2
        elif args[i] == "--ordenar-por" and i + 1 < len(args):
            ordenar_por = args[i + 1]; i += 2
        elif args[i] == "--tipo-loja" and i + 1 < len(args):
            tipo_loja = args[i + 1]; i += 2
        elif args[i] == "--palavra" and i + 1 < len(args):
            palavra = args[i + 1]; i += 2
        elif args[i] == "--paginas" and i + 1 < len(args):
            paginas = int(args[i + 1]); i += 2
        elif args[i] == "--por-pagina" and i + 1 < len(args):
            por_pagina = int(args[i + 1]); i += 2
        else:
            i += 1

    if "--testar" in args:
        testar()
    elif "--ranking-lojas" in args:
        print(f"Ranking de lojas, período {periodo}, ordenado por {ordenar_por}, "
              f"{paginas} chamada(s):")
        buscar_ranking_lojas(periodo, data_ref, paginas, por_pagina, ordenar_por,
                             None, palavra, tipo_loja, None, dry_run)
    elif produto_detalhe_id:
        buscar_produto(produto_detalhe_id, periodo, data_ref, dry_run)
    elif loja_id and "--videos-da-loja" not in args:
        buscar_loja(loja_id, periodo, data_ref, dry_run)
    elif video_id:
        buscar_video(video_id, periodo, data_ref)
    elif produto_id or loja_id or palavra or "--ranking-videos" in args:
        alvo = (f"produto {produto_id}" if produto_id else
                f"loja {loja_id}" if loja_id else
                f"palavra {palavra!r}" if palavra else "geral")
        print(f"Ranking de vídeos ({alvo}), período {periodo}, "
              f"até {paginas * min(por_pagina, 100)} linhas, "
              f"{paginas} chamada(s):")
        buscar_ranking_videos(periodo, data_ref, paginas, por_pagina,
                              produto_id, loja_id, None, palavra, so_organico, dry_run)
    else:
        raise SystemExit(
            "Nada pra fazer. Opções:\n"
            "  --testar                      confere a chave, gasta 1 chamada\n"
            "  --ranking-videos              top de vídeos do período\n"
            "  --ranking-lojas               top de lojas do período\n"
            "  --ordenar-por affiliate_revenue   ordena as lojas por receita de afiliado\n"
            "  --tipo-loja BRAND             só marca própria, ou RETAILER pra varejista\n"
            "  --loja <id>                   detalhe de uma loja\n"
            "  --produto <id>                detalhe de um produto, com o split vídeo x live\n"
            "  --videos-do-produto <id>      os vídeos que vendem um produto\n"
            "  --videos-da-loja <id>         os vídeos que vendem uma loja\n"
            "  --palavra fashion             busca por palavra-chave\n"
            "  --video <id>                  detalhe de um vídeo\n"
            "Junte --so-organico pra descartar os impulsionados, e --dry-run pra não gravar.")


if __name__ == "__main__":
    main()
