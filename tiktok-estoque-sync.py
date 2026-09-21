"""
Validador de estoque — TikTok Shop
==================================

Checa, de tempos em tempos, se os produtos que a Juliane postou no TikTok
ainda estão disponíveis. Roda via GitHub Actions (ver .github/workflows/
tiktok-estoque.yml) e escreve o resultado no Supabase, na tabela
`tiktok_estoque_monitor`. A página validador-tiktok.html só lê esse resultado.

Status possíveis:
  disponivel  — achou sinal claro de que dá pra comprar
  esgotado    — achou sinal claro de esgotado / sem estoque
  removido    — link caiu (404) ou o produto saiu do ar
  indefinido  — a página carregou mas não deu pra afirmar nada (bloqueio,
                captcha, layout novo). NUNCA dispara alerta.
  erro        — falha de rede/timeout

Regra anti-alarme-falso: um único resultado "esgotado" não manda alerta.
Só manda quando dois ciclos seguidos derem o mesmo resultado ruim
(CONFIRMACOES_NECESSARIAS).

Modos de uso:
  python3 tiktok-estoque-sync.py                   # rodada normal (usa o Supabase)
  python3 tiktok-estoque-sync.py --url "<link>"    # testa UM link e explica o que achou
  python3 tiktok-estoque-sync.py --dry-run         # checa tudo, não grava nada
  python3 tiktok-estoque-sync.py --debug           # salva o HTML lido em /tmp pra inspeção
  python3 tiktok-estoque-sync.py --playwright      # força o navegador headless
  python3 tiktok-estoque-sync.py --limite 10       # checa no máximo 10 produtos
"""

import argparse
import gzip
import html as html_mod
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone

# ── Configuração ─────────────────────────────────────────────────
# A chave anon já é pública (está embutida no garimpo-shopee.html). Dá pra
# sobrescrever por SUPABASE_KEY — use a service_role se quiser mais folga.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tkxkrbdvcctoajuigvvv.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRreGtyYmR2Y2N0b2FqdWlndnZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NzY2NzUsImV4cCI6MjA5OTQ1MjY3NX0.-szTE2wYYr9DNTLiff6zmLpbP6UOL1l9SFpvc-29Njs",
)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CONFIRMACOES_NECESSARIAS = int(os.environ.get("CONFIRMACOES", "2"))
TIMEOUT                  = int(os.environ.get("TIMEOUT", "25"))
PAUSA_MIN, PAUSA_MAX     = 2.0, 5.0   # respiro entre um produto e outro
MAX_POR_RODADA           = int(os.environ.get("MAX_POR_RODADA", "60"))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def agora_iso():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    print(msg, flush=True)


# ── Supabase (REST) ──────────────────────────────────────────────
def sb(metodo, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt.strip() else []
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Supabase {metodo} {path} -> {e.code}: {detalhe}") from None


def carregar_monitorados(limite):
    """Ativos primeiro os que a Juliane pediu recheck, depois os mais antigos."""
    campos = ("id,produto,link,link_resolvido,product_id,status,confirmacoes,"
              "esgotado_desde,alerta_enviado_em,ultima_verificacao,recheck_solicitado,ativo")
    linhas = sb("GET", f"tiktok_estoque_monitor?select={campos}"
                       f"&ativo=eq.true&order=recheck_solicitado.desc,"
                       f"ultima_verificacao.asc.nullsfirst&limit={limite}")
    return linhas


def gravar_resultado(linha, res, alerta_enviado):
    patch = {
        "status":             res["status"],
        "status_anterior":    linha.get("status"),
        "confirmacoes":       res["confirmacoes"],
        "ultima_verificacao": agora_iso(),
        "ultimo_http":        res.get("http"),
        "metodo_deteccao":    res.get("metodo"),
        "detalhe":            (res.get("detalhe") or "")[:500],
        "esgotado_desde":     res.get("esgotado_desde"),
        "recheck_solicitado": False,
    }
    if res.get("link_resolvido"):
        patch["link_resolvido"] = res["link_resolvido"]
    if res.get("product_id"):
        patch["product_id"] = res["product_id"]
    if res.get("preco"):
        patch["preco_atual"] = res["preco"][:60]
    if res.get("estoque") is not None:
        patch["estoque_restante"] = res["estoque"]
    if alerta_enviado:
        patch["alerta_enviado_em"] = agora_iso()

    sb("PATCH", f"tiktok_estoque_monitor?id=eq.{linha['id']}", patch)
    sb("POST", "tiktok_estoque_log", {
        "monitor_id":      linha["id"],
        "status":          res["status"],
        "status_anterior": linha.get("status"),
        "http_code":       res.get("http"),
        "metodo":          res.get("metodo"),
        "detalhe":         (res.get("detalhe") or "")[:500],
    })


# ── Telegram ─────────────────────────────────────────────────────
def telegram(texto):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("   (Telegram não configurado — alerta só ficou registrado no painel)")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        log(f"   ⚠ Falha ao mandar Telegram: {e}")
        return False


# ── Busca da página ──────────────────────────────────────────────
def cabecalhos(referer=None):
    h = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "no-cache",
    }
    if referer:
        h["Referer"] = referer
        h["Sec-Fetch-Site"] = "same-origin"
    return h


def _decodifica(resp, bruto):
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        try:
            bruto = gzip.decompress(bruto)
        except Exception:
            pass
    elif "deflate" in enc:
        try:
            bruto = zlib.decompress(bruto, -zlib.MAX_WBITS)
        except Exception:
            pass
    charset = "utf-8"
    ctype = resp.headers.get("Content-Type") or ""
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    if m:
        charset = m.group(1)
    return bruto.decode(charset, errors="replace")


def buscar_http(url, referer=None):
    """Retorna (http_code, url_final, html). Não levanta exceção em 4xx/5xx."""
    req = urllib.request.Request(url, headers=cabecalhos(referer))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.geturl(), _decodifica(r, r.read())
    except urllib.error.HTTPError as e:
        try:
            corpo = _decodifica(e, e.read())
        except Exception:
            corpo = ""
        return e.code, e.geturl() if hasattr(e, "geturl") else url, corpo


def buscar_playwright(url):
    """Navegador de verdade — pega o que só aparece depois do JS rodar."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None, None
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
            ctx = nav.new_context(user_agent=UA, locale="pt-BR",
                                  viewport={"width": 1366, "height": 900})
            pg = ctx.new_page()
            resp = pg.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            pg.wait_for_timeout(3500)          # deixa o preço/botão renderizar
            conteudo = pg.content()
            code = resp.status if resp else None
            final = pg.url
            nav.close()
            return code, final, conteudo
    except Exception as e:
        log(f"   ⚠ Playwright falhou: {e}")
        return None, None, None


# ── Leitura dos sinais ───────────────────────────────────────────
RE_PRODUCT_ID = [
    re.compile(r"/view/product/(\d{8,25})"),
    re.compile(r"/product/(\d{8,25})"),
    re.compile(r"[?&]product_id=(\d{8,25})"),
    re.compile(r"[?&]productId=(\d{8,25})"),
]

# Frases visíveis. Só valem fora de <script> — dentro do bundle de JS o TikTok
# carrega TODAS as traduções ("Sold out" inclusive), o que daria alarme falso.
FRASES_ESGOTADO = [
    "esgotado", "produto esgotado", "sem estoque", "fora de estoque",
    "out of stock", "sold out", "agotado", "estoque insuficiente",
    "temporariamente indisponível", "temporarily out of stock",
]
FRASES_REMOVIDO = [
    "produto não encontrado", "product not found", "no longer available",
    "não está mais disponível", "produto indisponível", "this product is unavailable",
    "página não encontrada", "page not found", "conteúdo indisponível",
]
FRASES_DISPONIVEL = [
    "adicionar ao carrinho", "add to cart", "comprar agora", "buy now",
    "comprar já", "adicionar à sacola", "add to bag", "em estoque", "in stock",
]
# Muro de bot / verificação — resultado não confiável.
FRASES_BLOQUEIO = [
    "verify to continue", "security check", "verificação de segurança",
    "captcha", "unusual traffic", "access denied", "acesso negado",
    "please verify", "verifique para continuar", "are you a robot",
    "javascript is required", "enable javascript",
]

# Sinais fortes: são do produto principal, não de vitrine de recomendados.
RE_JSON_ESGOTADO_FORTE = [
    (re.compile(r'"(?:sold_?out|is_?sold_?out)"\s*:\s*true', re.I), "campo sold_out=true"),
    (re.compile(r'"availability"\s*:\s*"[^"]*(?:OutOfStock|OUT_OF_STOCK|SoldOut)"', re.I), "availability=OutOfStock"),
    (re.compile(r'"sale_?status"\s*:\s*"?(?:SOLD_OUT|OUT_OF_STOCK)', re.I), "sale_status=SOLD_OUT"),
]
RE_JSON_DISPONIVEL = [
    (re.compile(r'"availability"\s*:\s*"[^"]*(?:InStock|IN_STOCK)"', re.I), "availability=InStock"),
    (re.compile(r'"(?:sold_?out|is_?sold_?out)"\s*:\s*false', re.I), "campo sold_out=false"),
]
# Sinal fraco: "stock":0 aparece também em variação/produto recomendado que
# acabou. Só vale quando NÃO há nenhum sinal de disponível na página.
RE_JSON_ESGOTADO_FRACO = [
    (re.compile(r'"(?:stock|stock_?num|inventory|available_?stock)"\s*:\s*0\b', re.I), "estoque=0"),
]
RE_ESTOQUE_NUM = re.compile(r'"(?:stock|stock_?num|available_?stock|inventory)"\s*:\s*(\d+)', re.I)
RE_PRECO = re.compile(r'"(?:real_price|sale_price|price_?str|format(?:ted)?_?price)"\s*:\s*"([^"]{1,40})"', re.I)


def extrair_product_id(*textos):
    for t in textos:
        if not t:
            continue
        for rx in RE_PRODUCT_ID:
            m = rx.search(t)
            if m:
                return m.group(1)
    return None


def texto_visivel(bruto):
    """Tira script/style/noscript e tags — sobra só o que a pessoa lê na tela."""
    s = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", bruto,
               flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).lower()


def ler_json_ld(bruto):
    """offers.availability do schema.org — o sinal mais confiável quando existe."""
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         bruto, re.S | re.I):
        try:
            dados = json.loads(m.group(1).strip())
        except Exception:
            continue
        pilha = [dados]
        while pilha:
            no = pilha.pop()
            if isinstance(no, list):
                pilha.extend(no)
            elif isinstance(no, dict):
                ofertas = no.get("offers")
                if ofertas:
                    pilha.append(ofertas)
                disp = no.get("availability")
                if isinstance(disp, str):
                    d = disp.lower()
                    if "outofstock" in d or "soldout" in d:
                        return "esgotado", f"JSON-LD availability={disp}"
                    if "instock" in d or "limitedavailability" in d:
                        return "disponivel", f"JSON-LD availability={disp}"
                if "discontinued" in str(no.get("availability", "")).lower():
                    return "removido", "JSON-LD availability=Discontinued"
                pilha.extend(v for v in no.values() if isinstance(v, (dict, list)))
    return None, None


def analisar(http_code, url_final, bruto, product_id):
    """Devolve dict com status, metodo, detalhe, preco, estoque."""
    r = {"status": "indefinido", "metodo": None, "detalhe": None,
         "preco": None, "estoque": None, "http": http_code}

    if not bruto:
        r["status"] = "erro" if http_code is None else "removido" if http_code in (404, 410) else "indefinido"
        r["metodo"] = "sem-conteudo"
        r["detalhe"] = f"Resposta vazia (HTTP {http_code})"
        return r

    if http_code in (404, 410):
        r.update(status="removido", metodo="http",
                 detalhe=f"HTTP {http_code} — o link do produto não existe mais")
        return r

    visivel = texto_visivel(bruto)

    # Muro de verificação declarado: nada do que estiver aqui é confiável.
    bloqueio = next((f for f in FRASES_BLOQUEIO if f in visivel), None)
    if bloqueio or http_code in (403, 429):
        motivo = bloqueio or f"HTTP {http_code}"
        r.update(status="indefinido", metodo="bloqueio",
                 detalhe=f"TikTok não entregou a página ({motivo}). Não dá pra afirmar nada.")
        return r

    # 1) JSON-LD (mais confiável)
    st, det = ler_json_ld(bruto)
    if st:
        r.update(status=st, metodo="json-ld", detalhe=det)

    # 2) Estado embutido na página (JSON do próprio TikTok)
    if r["status"] == "indefinido":
        forte = next(((n) for rx, n in RE_JSON_ESGOTADO_FORTE if rx.search(bruto)), None)
        ok    = next(((n) for rx, n in RE_JSON_DISPONIVEL if rx.search(bruto)), None)
        if forte and not ok:
            r.update(status="esgotado", metodo="json-embutido", detalhe=forte)
        elif ok and not forte:
            r.update(status="disponivel", metodo="json-embutido", detalhe=ok)
        elif forte and ok:
            r.update(status="indefinido", metodo="json-conflito",
                     detalhe=f"a página tem os dois sinais ({forte} e {ok}) — não arrisco concluir")
            return r
        else:
            fraco = next(((n) for rx, n in RE_JSON_ESGOTADO_FRACO if rx.search(bruto)), None)
            if fraco:
                r.update(status="esgotado", metodo="json-embutido-fraco", detalhe=fraco)

    # Sem nenhum dado estruturado E quase sem texto: o TikTok devolveu uma
    # casca vazia (bloqueio silencioso, ou página que só monta pelo JS).
    if r["status"] == "indefinido" and len(visivel) < 400:
        r.update(status="indefinido", metodo="bloqueio",
                 detalhe=f"Página veio quase vazia ({len(visivel)} caracteres de texto) e sem "
                         "dados de produto — provável bloqueio silencioso. Rode com --playwright.")
        return r

    # 3) Texto visível — com desempate, porque a palavra "esgotado" também
    #    aparece em produto recomendado lá embaixo da página.
    if r["status"] == "indefinido":
        f_rem = next((f for f in FRASES_REMOVIDO if f in visivel), None)
        f_esg = next((f for f in FRASES_ESGOTADO if f in visivel), None)
        f_ok  = next((f for f in FRASES_DISPONIVEL if f in visivel), None)
        if f_rem and not f_ok:
            r.update(status="removido", metodo="texto", detalhe=f'texto na página: "{f_rem}"')
        elif f_esg and not f_ok:
            r.update(status="esgotado", metodo="texto", detalhe=f'texto na página: "{f_esg}"')
        elif f_ok and not (f_esg or f_rem):
            r.update(status="disponivel", metodo="texto", detalhe=f'botão/texto: "{f_ok}"')
        elif f_ok and (f_esg or f_rem):
            r.update(status="indefinido", metodo="texto-conflito",
                     detalhe=f'a página mostra "{f_esg or f_rem}" e "{f_ok}" ao mesmo tempo — '
                             "pode ser vitrine de recomendados. Não concluí nada.")
            return r

    # 4) Redirecionou pra longe da página do produto = saiu do ar
    if r["status"] == "indefinido" and product_id and url_final:
        if product_id not in url_final and not re.search(r"/(product|view)/", url_final):
            r.update(status="removido", metodo="redirect",
                     detalhe=f"o link jogou pra outra página: {url_final[:120]}")

    if r["status"] == "indefinido" and not r["detalhe"]:
        r["metodo"] = "sem-sinal"
        r["detalhe"] = (f"Página abriu (HTTP {http_code}, {len(visivel)} caracteres de texto) "
                        "mas nenhum sinal de estoque foi reconhecido.")

    m = RE_PRECO.search(bruto)
    if m:
        r["preco"] = m.group(1)
    m = RE_ESTOQUE_NUM.search(bruto)
    if m:
        try:
            r["estoque"] = int(m.group(1))
        except ValueError:
            pass
    return r


def verificar(link, forcar_playwright=False, debug=False):
    """Resolve o link, busca a página e devolve o diagnóstico."""
    product_id = extrair_product_id(link)
    http_code = url_final = bruto = None

    if not forcar_playwright:
        try:
            http_code, url_final, bruto = buscar_http(link)
        except Exception as e:
            log(f"   ⚠ Erro de rede: {e}")
            http_code, url_final, bruto = None, link, ""

        product_id = product_id or extrair_product_id(url_final, bruto or "")

        # Link curto de afiliado que abriu numa página genérica: tenta a
        # página canônica do produto, em pt-BR.
        if product_id and url_final and product_id not in (url_final or ""):
            canon = (f"https://shop.tiktok.com/view/product/{product_id}"
                     f"?region=BR&locale=pt-BR")
            try:
                c_code, c_final, c_html = buscar_http(canon, referer="https://shop.tiktok.com/")
                if c_html and len(c_html) > len(bruto or ""):
                    http_code, url_final, bruto = c_code, c_final, c_html
            except Exception:
                pass

    res = analisar(http_code, url_final, bruto or "", product_id)

    # Se o HTTP simples não concluiu nada, tenta com navegador de verdade.
    if forcar_playwright or res["status"] in ("indefinido", "erro"):
        alvo = (f"https://shop.tiktok.com/view/product/{product_id}?region=BR&locale=pt-BR"
                if product_id else link)
        p_code, p_final, p_html = buscar_playwright(alvo)
        if p_html:
            product_id = product_id or extrair_product_id(p_final, p_html)
            p_res = analisar(p_code, p_final, p_html, product_id)
            if p_res["status"] != "indefinido" or res["status"] == "erro":
                p_res["metodo"] = f"playwright/{p_res['metodo']}"
                res = p_res
                url_final, bruto = p_final, p_html

    res["link_resolvido"] = url_final
    res["product_id"] = product_id

    if debug and bruto:
        caminho = f"/tmp/tiktok-estoque-{product_id or 'sem-id'}.html"
        with open(caminho, "w", encoding="utf-8") as fh:
            fh.write(bruto)
        log(f"   🐛 HTML salvo em {caminho} ({len(bruto)} bytes)")
    return res


# ── Regra de confirmação e alerta ────────────────────────────────
def aplicar_regra(linha, res):
    """Conta confirmações seguidas e decide se é hora de avisar."""
    status_bruto = res["status"]
    conf_antes   = linha.get("confirmacoes") or 0
    status_antes = linha.get("status") or "indefinido"
    ruim_antes   = status_antes in ("esgotado", "removido")

    if status_bruto == "disponivel":
        res["confirmacoes"] = 0
        res["esgotado_desde"] = None
        # Voltou ao estoque depois de ter sido confirmado como esgotado.
        res["avisar_volta"] = ruim_antes and conf_antes >= CONFIRMACOES_NECESSARIAS
    elif status_bruto in ("esgotado", "removido"):
        res["confirmacoes"] = (conf_antes + 1) if ruim_antes else 1
        res["esgotado_desde"] = linha.get("esgotado_desde") if ruim_antes else agora_iso()
        res["avisar_volta"] = False
    else:
        # indefinido/erro não confirma nem zera: mantém o que já havia.
        res["status"] = status_antes
        res["status_bruto"] = status_bruto
        res["confirmacoes"] = conf_antes
        res["esgotado_desde"] = linha.get("esgotado_desde")
        res["avisar_volta"] = False

    # Só avisa numa leitura NOVA de esgotado/removido. Se a rodada deu
    # "indefinido", o contador ficou parado — avisar de novo seria repetir o
    # mesmo alerta toda hora. O segundo braço cobre o caso de o Telegram ter
    # falhado justamente na rodada em que o contador bateu.
    leitura_ruim = status_bruto in ("esgotado", "removido")
    res["avisar_esgotou"] = leitura_ruim and res["confirmacoes"] >= CONFIRMACOES_NECESSARIAS and (
        res["confirmacoes"] == CONFIRMACOES_NECESSARIAS or not linha.get("alerta_enviado_em")
    )
    return res


def texto_alerta(linha, res):
    nome = html_mod.escape(linha.get("produto") or "produto sem nome")
    link = linha.get("link_resolvido") or linha.get("link") or ""
    if res["status"] == "removido":
        titulo = "🚫 <b>PRODUTO SAIU DO AR</b>"
        corpo = "O link não existe mais no TikTok Shop."
    else:
        titulo = "🔴 <b>PRODUTO ESGOTADO</b>"
        corpo = "O TikTok Shop está mostrando esse produto como esgotado."
    onde = linha.get("onde_postei")
    extra = f"\n📍 Postado em: {html_mod.escape(onde)}" if onde else ""
    return (f"{titulo}\n\n<b>{nome}</b>\n{corpo}{extra}\n"
            f"🔎 Como detectei: {html_mod.escape(res.get('detalhe') or '—')}\n\n"
            f"👉 Tira o link do ar ou troca o produto.\n{html_mod.escape(link)}")


def texto_volta(linha):
    nome = html_mod.escape(linha.get("produto") or "produto sem nome")
    link = linha.get("link_resolvido") or linha.get("link") or ""
    return (f"🟢 <b>VOLTOU AO ESTOQUE</b>\n\n<b>{nome}</b>\n"
            f"Está disponível de novo — dá pra voltar a divulgar.\n\n{html_mod.escape(link)}")


# ── Execução ─────────────────────────────────────────────────────
def rodada(args):
    try:
        linhas = carregar_monitorados(min(args.limite or MAX_POR_RODADA, MAX_POR_RODADA))
    except Exception as e:
        log(f"❌ Não consegui ler o Supabase: {e}")
        return 1

    if not linhas:
        log("Nenhum produto ativo pra checar. Cadastre na página validador-tiktok.html.")
        return 0

    log(f"🔎 Checando {len(linhas)} produto(s) do TikTok Shop…\n")
    contagem = {"disponivel": 0, "esgotado": 0, "removido": 0, "indefinido": 0, "erro": 0}
    alertas = 0

    for i, linha in enumerate(linhas, 1):
        nome = (linha.get("produto") or "?")[:50]
        log(f"[{i}/{len(linhas)}] {nome}")
        if not linha.get("link"):
            log("   ⚠ sem link cadastrado — pulando")
            continue

        res = verificar(linha["link"], forcar_playwright=args.playwright, debug=args.debug)
        bruto = res["status"]
        res = aplicar_regra(linha, res)
        contagem[bruto] = contagem.get(bruto, 0) + 1

        marca = {"disponivel": "🟢", "esgotado": "🔴", "removido": "🚫",
                 "indefinido": "⚪", "erro": "⚠"}.get(bruto, "•")
        sufixo = ""
        if res["status"] in ("esgotado", "removido"):
            sufixo = f" (confirmação {res['confirmacoes']}/{CONFIRMACOES_NECESSARIAS})"
        log(f"   {marca} {bruto}{sufixo} — {res.get('detalhe')}")

        enviado = False
        if args.dry_run:
            log("   (dry-run: nada gravado)")
        else:
            if res.get("avisar_esgotou"):
                enviado = telegram(texto_alerta(linha, res))
                alertas += 1
                log(f"   📲 alerta de esgotamento {'enviado' if enviado else 'NÃO enviado'}")
            elif res.get("avisar_volta"):
                telegram(texto_volta(linha))
                log("   📲 avisei que voltou ao estoque")
            try:
                gravar_resultado(linha, res, enviado)
            except Exception as e:
                log(f"   ❌ erro ao gravar no Supabase: {e}")

        if i < len(linhas):
            time.sleep(random.uniform(PAUSA_MIN, PAUSA_MAX))

    log("\n── Resumo ──")
    for k, v in contagem.items():
        if v:
            log(f"  {k}: {v}")
    if contagem["indefinido"] >= max(3, len(linhas) // 2):
        log("\n⚠ Muitos 'indefinido': o TikTok provavelmente barrou o robô nesta rodada.")
        log("  Rode com --playwright, ou configure FETCH via VPS/proxy. Nenhum alerta falso foi disparado.")
    if alertas:
        log(f"\n📲 {alertas} alerta(s) de esgotamento disparado(s).")
    return 0


def testar_url(url, args):
    log(f"🔎 Testando: {url}\n")
    res = verificar(url, forcar_playwright=args.playwright, debug=True)
    log("── Diagnóstico ──")
    log(f"  status        : {res['status']}")
    log(f"  método        : {res.get('metodo')}")
    log(f"  detalhe       : {res.get('detalhe')}")
    log(f"  HTTP          : {res.get('http')}")
    log(f"  product_id    : {res.get('product_id')}")
    log(f"  link resolvido: {res.get('link_resolvido')}")
    log(f"  preço lido    : {res.get('preco')}")
    log(f"  estoque lido  : {res.get('estoque')}")
    if res["status"] == "indefinido":
        log("\n⚠ Não deu pra concluir. Abra o HTML salvo em /tmp e procure como a página")
        log("  escreve 'esgotado'; depois é só acrescentar a frase em FRASES_ESGOTADO.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Validador de estoque do TikTok Shop")
    ap.add_argument("--url", help="testa um único link e explica o diagnóstico")
    ap.add_argument("--dry-run", action="store_true", help="checa tudo mas não grava nada")
    ap.add_argument("--debug", action="store_true", help="salva o HTML lido em /tmp")
    ap.add_argument("--playwright", action="store_true", help="força o navegador headless")
    ap.add_argument("--limite", type=int, help="checa no máximo N produtos")
    args = ap.parse_args()

    if args.url:
        return testar_url(args.url, args)
    return rodada(args)


if __name__ == "__main__":
    sys.exit(main())
