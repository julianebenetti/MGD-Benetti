"""
Cliente da API do Kalodata -> Supabase (Espião TikTok Shop)

Substitui o export manual de CSV: puxa os dados direto da API oficial do Kalodata
e grava nas mesmas tabelas que o tiktok-sync.py alimenta.

Uso:
    python kalodata-api.py --testar              # 1 chamada só, confere se a chave funciona
    python kalodata-api.py --video 7404191282148511007
    python kalodata-api.py --ranking-produtos    # precisa dos parâmetros confirmados (veja abaixo)

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
  2. O caminho e os parâmetros dos endpoints de lista de classificação
     (produtos, lojas, vídeos). Só o /tiktok/video/detail está confirmado pela doc.
     Os outros estão em ENDPOINTS marcados como A CONFIRMAR.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

BASE = "https://www.kalodata.com/openapi/v1"

# Só o primeiro veio confirmado da documentação que a Juliane mandou.
# Os demais são o caminho provável, a partir dos nomes do menu lateral —
# corrija aqui assim que abrir a página de cada um no Centro Aberto.
ENDPOINTS = {
    "video_detalhe":      ("/tiktok/video/detail",    "confirmado"),
    "video_ranking":      ("/tiktok/video/list",      "A CONFIRMAR"),
    "produto_detalhe":    ("/tiktok/product/detail",  "A CONFIRMAR"),
    "produto_ranking":    ("/tiktok/product/list",    "A CONFIRMAR"),
    "loja_detalhe":       ("/tiktok/shop/detail",     "A CONFIRMAR"),
    "loja_ranking":       ("/tiktok/shop/list",       "A CONFIRMAR"),
    "criador_ranking":    ("/tiktok/creator/list",    "A CONFIRMAR"),
    "categoria_ranking":  ("/tiktok/category/list",   "A CONFIRMAR"),
}

# Padrões do Brasil, conforme a lista de valores aceitos na documentação
PADRAO = {"region": "BR", "language": "pt-BR", "currency": "BRL", "date_range": "last7Day"}

KALODATA_KEY    = os.environ.get("KALODATA_KEY", "")
KALODATA_HEADER = os.environ.get("KALODATA_HEADER", "secret-key")
SUPABASE_URL    = os.environ.get("SUPABASE_URL", "https://tkxkrbdvcctoajuigvvv.supabase.co")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY", "")

# A doc diz 100 chamadas a cada 10 segundos. Fico bem abaixo disso de propósito.
INTERVALO_MINIMO = 0.15
_ultima_chamada = 0.0


def chamar(nome_endpoint, corpo):
    """Uma chamada POST na API. Devolve o dict de resposta ou levanta erro claro."""
    global _ultima_chamada
    if not KALODATA_KEY:
        raise SystemExit("Falta a variável de ambiente KALODATA_KEY.")

    caminho, situacao = ENDPOINTS[nome_endpoint]
    espera = INTERVALO_MINIMO - (time.time() - _ultima_chamada)
    if espera > 0:
        time.sleep(espera)
    _ultima_chamada = time.time()

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
        if e.code == 404 and situacao == "A CONFIRMAR":
            raise SystemExit(
                f"O caminho {caminho!r} não existe. Ele estava marcado como A CONFIRMAR.\n"
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


PERIODOS = {"1d": "lastDay", "7d": "last7Day", "30d": "last30Day",
            "60d": "last60Day", "90d": "last90Day"}


def periodo_api(periodo):
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
        for nome, (caminho, situacao) in ENDPOINTS.items():
            print(f"  {nome:20} {caminho:28} {situacao}")
        return

    periodo, data_ref = "7d", date.today().isoformat()
    video_id = None
    i = 0
    while i < len(args):
        if args[i] == "--periodo" and i + 1 < len(args):
            periodo = args[i + 1]; i += 2
        elif args[i] == "--data" and i + 1 < len(args):
            data_ref = args[i + 1]; i += 2
        elif args[i] == "--video" and i + 1 < len(args):
            video_id = args[i + 1]; i += 2
        else:
            i += 1

    if "--testar" in args:
        testar()
    elif video_id:
        buscar_video(video_id, periodo, data_ref)
    else:
        raise SystemExit(
            "Nada pra fazer. Use --testar pra conferir a chave, ou --video <id>.\n"
            "Os endpoints de lista de classificação ainda estão marcados como A CONFIRMAR — "
            "mande a página deles do Centro Aberto que eu ligo.")


if __name__ == "__main__":
    main()
