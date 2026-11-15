"""
PostZap — posta links da Shopee nos grupos de WhatsApp, com aprovação de cada postagem.

App separado da AfiliDash e do robô do Shopee Vídeo:
  * lê (só leitura) os produtos do Garimpo (Supabase) e da Central Shopee Vídeo (estado.db do robô);
  * guarda grupos, fila e histórico no próprio banco (postzap.db);
  * envia pelo Evolution API (WhatsApp do chip separado), com intervalo entre os grupos.

Só usa a biblioteca padrão do Python. Configuração no arquivo .env (veja .env.example).
"""

import hashlib
import hmac
import json
import logging
import os
import random
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent
BRT = timezone(timedelta(hours=-3))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('postzap')


def load_env():
    env_file = BASE / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
CFG = {
    'porta': int(os.getenv('POSTZAP_PORTA', '8790')),
    'senha': os.getenv('POSTZAP_SENHA', ''),
    'segredo': os.getenv('POSTZAP_SEGREDO', '') or hashlib.sha256(os.getenv('POSTZAP_SENHA', 'x').encode()).hexdigest(),
    'supabase_url': os.getenv('SUPABASE_URL', 'https://tkxkrbdvcctoajuigvvv.supabase.co').rstrip('/'),
    'supabase_key': os.getenv('SUPABASE_KEY', ''),
    'central_db': os.getenv('CENTRAL_DB', '/opt/shopee-video/shopee-video-automation/estado.db'),
    'evo_url': os.getenv('EVOLUTION_URL', 'http://127.0.0.1:8080').rstrip('/'),
    'evo_key': os.getenv('EVOLUTION_KEY', ''),
    'evo_insts': [x.strip() for x in os.getenv('EVOLUTION_INSTANCIAS', 'chip1,chip2,chip3').split(',') if x.strip()],
    'autorizados': [re.sub(r'\D', '', x) for x in os.getenv('NUMEROS_AUTORIZADOS', '').split(',') if re.sub(r'\D', '', x)],
    'webhook_segredo': os.getenv('WEBHOOK_SEGREDO', ''),
    'openai_model': os.getenv('OPENAI_MODEL', 'gpt-5.6-luna'),
    'intervalo_min': int(os.getenv('INTERVALO_MIN_SEG', '90')),
    'intervalo_max': int(os.getenv('INTERVALO_MAX_SEG', '240')),
    'limite_dia': int(os.getenv('LIMITE_POSTS_DIA_POR_GRUPO', '8')),
    'repetir_dias': int(os.getenv('NAO_REPETIR_DIAS', '7')),
    'comissao_min': float(os.getenv('COMISSAO_MIN', '9')),
    'url_publica': os.getenv('URL_PUBLICA', 'https://posts.descontoirresistivel.com.br/zap').rstrip('/'),
    'titulo_previa': os.getenv('TITULO_PREVIA', '@descontoirresistivel'),
    'sub_id': os.getenv('SUB_ID', 'postzap'),
    'central_env': os.getenv('CENTRAL_ENV', '/opt/shopee-video/shopee-video-automation/.env'),
}
BLOQUEADOS = ('suplement', 'vitamin', 'colágeno', 'colageno', 'whey', 'creatina', 'termogênic', 'termogenic')

MODELO_PADRAO = """*{chamada}*

🛍️ {produto}

~De: {preco_de}~
*Por: {preco}* ✅

🔗 *Compre aqui:* {link}

⚠️ Todas as promoções estão sujeitas a alterações a qualquer momento."""

# ---------------------------------------------------------------- banco próprio

DB_PATH = BASE / 'postzap.db'
SCHEMA = """
CREATE TABLE IF NOT EXISTS grupos (jid TEXT PRIMARY KEY, nome TEXT, ativo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS fila (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origem TEXT, chave TEXT, produto TEXT, preco TEXT, comissao TEXT, link TEXT,
    texto TEXT, grupos TEXT DEFAULT '[]',
    status TEXT DEFAULT 'rascunho',        -- rascunho | aprovado | enviando | enviado | erro | descartado
    agendado_para TEXT,                    -- ISO (Brasília); vazio = assim que aprovado
    criado_em TEXT, aprovado_em TEXT, enviado_em TEXT, erro TEXT
);
CREATE TABLE IF NOT EXISTS envios (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fila_id INTEGER, jid TEXT, chave TEXT, quando TEXT, ok INTEGER, erro TEXT
);
CREATE TABLE IF NOT EXISTS config (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS grupo_chips (jid TEXT, instancia TEXT, PRIMARY KEY (jid, instancia));
CREATE TABLE IF NOT EXISTS conversa (numero TEXT PRIMARY KEY, fila_id INTEGER, esperando TEXT);
CREATE TABLE IF NOT EXISTS links (           -- links curtos com prévia (foto + título) no WhatsApp
    codigo TEXT PRIMARY KEY, destino TEXT, titulo TEXT, imagem TEXT, criado_em TEXT, cliques INTEGER DEFAULT 0
);
"""
_lock = threading.Lock()


def db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript(SCHEMA)
        for tab, col in (('envios', 'instancia TEXT'), ('fila', 'dados TEXT'), ('fila', 'pedido_por TEXT'),
                         ('fila', 'pedido_inst TEXT')):
            if col.split()[0] not in {r[1] for r in c.execute(f'PRAGMA table_info({tab})')}:
                c.execute(f'ALTER TABLE {tab} ADD COLUMN {col}')


def get_cfg(k, default=''):
    with db() as c:
        r = c.execute('SELECT v FROM config WHERE k=?', (k,)).fetchone()
    return r[0] if r else default


def set_cfg(k, v):
    with _lock, db() as c:
        c.execute('INSERT OR REPLACE INTO config VALUES (?,?)', (k, v))


def agora():
    return datetime.now(BRT)


# ---------------------------------------------------------------- fontes de produtos (só leitura)

def bloqueado(nome):
    n = (nome or '').lower()
    return any(b in n for b in BLOQUEADOS)


def num(v):
    """29.9, "29,90", "R$ 1.299,90", "R$ 29,90 - 39,90" -> primeiro número."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r'\d[\d.,]*', str(v or ''))
    if not m:
        return 0.0
    s = m.group(0).rstrip('.,')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def br(v):
    return f"{num(v):.2f}".replace('.', ',')


def produtos_garimpo(limite=150):
    if not CFG['supabase_key']:
        return [], 'SUPABASE_KEY não configurada no .env'
    q = urllib.parse.urlencode({
        'select': 'id,produto,loja,preco,comissao_reais,cpa_maximo,vendas,nota,nicho,link,tipo,shop_id,item_id,data_indicacao',
        'order': 'data_indicacao.desc,vendas.desc', 'limit': str(limite)})
    req = urllib.request.Request(f"{CFG['supabase_url']}/rest/v1/garimpo_produtos?{q}", headers={
        'apikey': CFG['supabase_key'], 'Authorization': f"Bearer {CFG['supabase_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            rows = json.load(r)
    except Exception as e:
        return [], f'Garimpo indisponível: {e}'
    out = []
    for p in rows:
        com = max(num(p.get('comissao_reais')), num(p.get('cpa_maximo')))
        if bloqueado(p.get('produto')) or com < CFG['comissao_min'] or not p.get('link'):
            continue
        chave = f"{p.get('shop_id')}:{p.get('item_id')}" if p.get('item_id') else f"g{p['id']}"
        out.append({'origem': 'garimpo', 'chave': chave, 'produto': p.get('produto') or '', 'loja': p.get('loja') or '',
                    'preco': br(p.get('preco')), 'comissao': br(com), 'vendas': p.get('vendas') or 0,
                    'nota': p.get('nota') or '', 'link': p['link'],
                    'detalhe': ' · '.join(x for x in (p.get('nicho'), p.get('tipo'), str(p.get('data_indicacao') or '')) if x)})
    return out, ''


def produtos_central():
    path = Path(CFG['central_db'])
    if not path.exists():
        return [], f'Banco da Central não encontrado em {path}'
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        meta = conn.execute("SELECT value FROM meta WHERE key='ideias_links'").fetchone()
        posts = conn.execute("SELECT product_key, product_name, products, links, posted_at, metadata FROM posts "
                             "WHERE status='postado' ORDER BY posted_at DESC LIMIT 80").fetchall()
        conn.close()
    except Exception as e:
        return [], f'Erro ao ler a Central: {e}'
    out, vistos = [], set()
    if meta:
        data = json.loads(meta[0] or '{}')
        for r in data.get('rows', []):
            chave = '/'.join(r.get('link_produto', '').rstrip('/').split('/')[-2:]).replace('/', ':')
            if not r.get('link') or bloqueado(r.get('produto')) or num(r.get('comissao')) < CFG['comissao_min']:
                continue
            vistos.add(chave)
            out.append({'origem': 'central_ideias', 'chave': chave, 'produto': r.get('produto', ''),
                        'loja': r.get('loja', ''), 'preco': br(r.get('preco')), 'comissao': br(r.get('comissao')),
                        'vendas': r.get('vendas') or 0, 'nota': r.get('nota') or '', 'link': r['link'],
                        'detalhe': f"Ideias de {data.get('dia', '')} · {r.get('secao', '')}"})
    for p in posts:
        chave = p['product_key'] or ''
        links = json.loads(p['links'] or '[]')
        prods = json.loads(p['products'] or '[]')
        if not links or chave in vistos or bloqueado(p['product_name']):
            continue
        vistos.add(chave)
        info = prods[0] if prods and isinstance(prods[0], dict) else {}
        out.append({'origem': 'central_video', 'chave': chave, 'produto': p['product_name'] or '',
                    'loja': info.get('shopName', ''), 'preco': br(info.get('priceMin') or info.get('price') or 0),
                    'comissao': br(info.get('commission') or 0), 'vendas': info.get('sales') or 0,
                    'nota': info.get('ratingStar') or '', 'link': links[0],
                    'imagem': info.get('imageUrl', ''),
                    'chamada': (json.loads(p['metadata'] or '{}') or {}).get('headline', ''),
                    'detalhe': f"Já postado em vídeo · {(p['posted_at'] or '')[:10]}"})
    return out, ''


def ultimos_envios():
    """chave -> data do último envio (para avisar repetição)."""
    with db() as c:
        rows = c.execute('SELECT chave, MAX(quando) q FROM envios WHERE ok=1 GROUP BY chave').fetchall()
    return {r['chave']: r['q'] for r in rows}


# ---------------------------------------------------------------- Shopee (foto, preço atual e link de afiliado)

def credenciais_shopee():
    """Usa as chaves do .env do PostZap ou, se vazias, lê (só leitura) as do robô do Shopee Vídeo."""
    app_id, secret = os.getenv('SHOPEE_AFFILIATE_APP_ID', ''), os.getenv('SHOPEE_AFFILIATE_SECRET', '')
    if not (app_id and secret) and Path(CFG['central_env']).exists():
        for line in Path(CFG['central_env']).read_text(encoding='utf-8').splitlines():
            k, _, v = line.partition('=')
            if k.strip() == 'SHOPEE_AFFILIATE_APP_ID' and not app_id:
                app_id = v.strip().strip('"\'')
            if k.strip() == 'SHOPEE_AFFILIATE_SECRET' and not secret:
                secret = v.strip().strip('"\'')
    return app_id, secret


def shopee_gql(query):
    app_id, secret = credenciais_shopee()
    if not (app_id and secret):
        raise RuntimeError('chaves da Shopee Affiliate não encontradas')
    payload = json.dumps({'query': query}, separators=(',', ':'), ensure_ascii=False)
    ts = str(int(time.time()))
    sig = hashlib.sha256(f'{app_id}{ts}{payload}{secret}'.encode()).hexdigest()
    req = urllib.request.Request('https://open-api.affiliate.shopee.com.br/graphql', data=payload.encode(), headers={
        'Content-Type': 'application/json',
        'Authorization': f'SHA256 Credential={app_id}, Timestamp={ts}, Signature={sig}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get('errors'):
        raise RuntimeError(f"Shopee: {data['errors'][0].get('message')}")
    return data['data']


def ids_da_chave(chave):
    m = re.fullmatch(r'(\d+):(\d+)', chave or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def preparar(p):
    """Completa o produto antes de postar: foto, preço atual, link de afiliado (sub_id) e link curto com prévia."""
    avisos = list(p.get('avisos') or [])
    ids = ids_da_chave(p.get('chave'))
    link = p.get('link') or ''
    if ids:
        try:
            nodes = shopee_gql(f'{{productOfferV2(shopId:{ids[0]},itemId:{ids[1]},limit:1)'
                               '{nodes{productName priceMin priceMax imageUrl sales ratingStar}}}')['productOfferV2']['nodes']
            if nodes:
                n = nodes[0]
                p['imagem'] = n.get('imageUrl') or p.get('imagem', '')
                if n.get('priceMin'):
                    p['preco'] = br(n['priceMin'])
            else:
                avisos.append('Produto não encontrado na Shopee agora (pode ter saído do ar).')
        except Exception as e:
            avisos.append(f'Não consegui atualizar foto/preço: {e}')
        if 's.shopee.com.br' not in link:
            try:
                origem = f'https://shopee.com.br/product/{ids[0]}/{ids[1]}'
                link = shopee_gql(f'mutation{{generateShortLink(input:{{originUrl:{json.dumps(origem)},'
                                  f'subIds:[{json.dumps(CFG["sub_id"])}]}}){{shortLink}}}}')['generateShortLink']['shortLink']
            except Exception as e:
                avisos.append(f'Não consegui gerar o link de afiliado: {e}')
    p['link_afiliado'] = link
    p['link'] = criar_link_curto(link, p.get('produto', ''), p.get('imagem', '')) if link else ''
    p['avisos'] = avisos
    return p


LOJAS = (('magazineluiza', 'Magalu'), ('magalu', 'Magalu'), ('mercadolivre', 'Mercado Livre'),
         ('mercadolibre', 'Mercado Livre'), ('meli.la', 'Mercado Livre'), ('amazon', 'Amazon'), ('amzn', 'Amazon'),
         ('shopee', 'Shopee'), ('shp.ee', 'Shopee'))


def loja_do_link(*urls):
    for u in urls:
        host = urllib.parse.urlparse(u or '').netloc.lower()
        for trecho, nome in LOJAS:
            if trecho in host:
                return nome
    return ''


def ler_link(url):
    """Link de afiliado de outra loja (Magalu, Mercado Livre, Amazon…): tenta ler nome, foto e preço da página.
    O link enviado nos grupos é sempre o que você colou (é ele que tem o seu código de afiliado)."""
    import html as h
    if not re.match(r'https?://', url or ''):
        raise ValueError('Cole o link completo, começando com https://')
    info = {'origem': 'manual', 'link': url.strip(), 'produto': '', 'imagem': '', 'preco': '', 'avisos': []}
    final, pagina = url, ''
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/126.0 Safari/537.36', 'Accept-Language': 'pt-BR,pt;q=0.9'})
        with urllib.request.urlopen(req, timeout=20) as r:
            final = r.geturl()
            pagina = r.read(1_500_000).decode('utf-8', 'ignore')
    except Exception as e:
        info['avisos'].append(f'A loja não deixou ler a página ({str(e)[:80]}): preencha nome, foto e preço à mão.')

    def meta(*nomes):
        for n in nomes:
            m = (re.search(rf'<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(n)}["\'][^>]*content=["\']([^"\']+)', pagina, re.I)
                 or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']{re.escape(n)}["\']', pagina, re.I))
            if m:
                return h.unescape(m.group(1)).strip()
        return ''
    info['produto'] = re.sub(r'\s*[|\-–]\s*(Magalu|Mercado Livre|Amazon\.com\.br.*|Magazine Luiza)\s*$', '',
                             meta('og:title', 'twitter:title') or h.unescape((re.search(r'<title>([^<]+)', pagina) or [None, ''])[1]).strip())
    info['imagem'] = meta('og:image', 'twitter:image')
    preco = meta('product:price:amount', 'og:price:amount', 'price')
    if not preco:
        m = re.search(r'"price"\s*:\s*"?(\d+[.,]?\d*)', pagina)
        preco = m.group(1) if m else ''
    info['preco'] = br(preco) if preco else ''
    info['loja'] = loja_do_link(final, url)
    info['chave'] = 'url:' + hashlib.sha1(final.split('?')[0].encode()).hexdigest()[:16]
    if not info['produto']:
        info['avisos'].append('Não achei o nome do produto: escreva no campo.')
    return info


def criar_link_curto(destino, titulo, imagem):
    import secrets
    with _lock, db() as c:
        r = c.execute('SELECT codigo FROM links WHERE destino=? AND imagem=?', (destino, imagem or '')).fetchone()
        if r:
            return f"{CFG['url_publica']}/l/{r[0]}"
        codigo = secrets.token_urlsafe(5).replace('-', 'x').replace('_', 'y')
        c.execute('INSERT INTO links VALUES (?,?,?,?,?,0)', (codigo, destino, titulo, imagem or '', agora().isoformat()))
    return f"{CFG['url_publica']}/l/{codigo}"


def pagina_link(codigo):
    """Página do link curto: o WhatsApp lê og:title/og:image (a miniatura), a pessoa é levada à Shopee."""
    import html as h
    with _lock, db() as c:
        r = c.execute('SELECT * FROM links WHERE codigo=?', (codigo,)).fetchone()
        if r:
            c.execute('UPDATE links SET cliques=cliques+1 WHERE codigo=?', (codigo,))
    if not r:
        return None
    d, t, img = h.escape(r['destino']), h.escape(CFG['titulo_previa']), h.escape(r['imagem'] or '')
    desc = h.escape(r['titulo'] or '')
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{t}</title>
<meta property="og:title" content="{t}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="website">{f'<meta property="og:image" content="{img}">' if img else ''}
<meta http-equiv="refresh" content="0;url={d}"></head>
<body style="font-family:sans-serif;text-align:center;padding:40px">
<p>Abrindo a oferta…</p><p><a href="{d}">Toque aqui se não abrir</a></p>
<script>location.replace({json.dumps(r['destino'])})</script></body></html>""".encode()


# ---------------------------------------------------------------- Evolution API (WhatsApp)

def evo(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{CFG['evo_url']}{path}", data=data, method=method,
                                 headers={'apikey': CFG['evo_key'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode() or '{}'
            return json.loads(txt)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Evolution {e.code}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Evolution fora do ar: {e.reason}")


_webhook_ok = set()
_estado_cache = {}


def instancias():
    return CFG['evo_insts']


def estado_chip(inst, cache_seg=60):
    """'open' = conectado. Guardado por 1 min para não consultar a cada envio."""
    t, st = _estado_cache.get(inst, (0, ''))
    if time.time() - t < cache_seg:
        return st
    try:
        r = evo('GET', f'/instance/connectionState/{inst}')
        st = (r.get('instance') or {}).get('state') or r.get('state') or 'desconhecido'
    except RuntimeError as e:
        st = 'inexistente' if '404' in str(e) else 'erro'
    _estado_cache[inst] = (time.time(), st)
    return st


def configurar_webhook(inst):
    """Mensagens recebidas pelo chip chegam ao PostZap (para a conversa de links)."""
    if inst in _webhook_ok or not CFG['webhook_segredo']:
        return
    try:
        evo('POST', f'/webhook/set/{inst}', {'webhook': {
            'enabled': True, 'url': f"{CFG['url_publica']}/webhook/{CFG['webhook_segredo']}",
            'byEvents': False, 'base64': False, 'events': ['MESSAGES_UPSERT']}})
        _webhook_ok.add(inst)
    except RuntimeError as e:
        log.warning(f'Webhook de {inst}: {e}')


def whatsapp_status(inst):
    st = estado_chip(inst, cache_seg=0)
    if st == 'inexistente':
        evo('POST', '/instance/create', {'instanceName': inst, 'qrcode': True, 'integration': 'WHATSAPP-BAILEYS'})
        st = estado_chip(inst, cache_seg=0)
    res = {'instancia': inst, 'estado': st}
    if st == 'open':
        configurar_webhook(inst)
        try:
            info = evo('GET', f'/instance/fetchInstances?instanceName={inst}')
            info = info[0] if isinstance(info, list) and info else {}
            res['numero'] = (info.get('ownerJid') or '').split('@')[0]
            res['nome'] = info.get('profileName') or ''
        except RuntimeError:
            pass
    else:
        try:
            qr = evo('GET', f'/instance/connect/{inst}')
            res['qr'] = qr.get('base64') or ''
            res['codigo'] = qr.get('pairingCode') or ''
        except RuntimeError as e:
            res['erro'] = str(e)
    return res


def atualizar_grupos():
    """Busca os grupos de cada chip conectado e guarda em quais grupos cada chip está."""
    total = set()
    for inst in instancias():
        if estado_chip(inst, cache_seg=0) != 'open':
            continue
        lista = evo('GET', f"/group/fetchAllGroups/{inst}?getParticipants=false", timeout=60)
        with _lock, db() as c:
            c.execute('DELETE FROM grupo_chips WHERE instancia=?', (inst,))
            for g in lista:
                total.add(g['id'])
                c.execute('INSERT INTO grupos (jid, nome) VALUES (?,?) ON CONFLICT(jid) DO UPDATE SET nome=excluded.nome',
                          (g['id'], g.get('subject') or g['id']))
                c.execute('INSERT OR IGNORE INTO grupo_chips VALUES (?,?)', (g['id'], inst))
    return len(total)


def enviar_texto(inst, jid, texto, previa=True):
    evo('POST', f"/message/sendText/{inst}", {'number': jid, 'text': texto, 'linkPreview': previa}, timeout=60)


# ---------------------------------------------------------------- envio (fila aprovada)

def posts_hoje(c, jid):
    inicio = agora().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return c.execute('SELECT COUNT(*) FROM envios WHERE jid=? AND ok=1 AND quando>=?', (jid, inicio)).fetchone()[0]


def sortear_chip(jid, evitar=None):
    """Sorteia entre os chips conectados que estão no grupo; evita repetir o mesmo chip da postagem anterior."""
    with db() as c:
        chips = [r[0] for r in c.execute('SELECT instancia FROM grupo_chips WHERE jid=?', (jid,))]
        ultimo = c.execute('SELECT instancia FROM envios WHERE jid=? AND ok=1 ORDER BY id DESC LIMIT 1', (jid,)).fetchone()
    chips = [x for x in chips if x in instancias() and estado_chip(x) == 'open'] or \
            [x for x in instancias() if estado_chip(x) == 'open' and not chips]
    if not chips:
        return None
    opcoes = [x for x in chips if x not in {evitar, ultimo and ultimo[0]}] or chips
    return random.choice(opcoes)


def worker():
    while True:
        try:
            processar_fila()
        except Exception:
            log.exception('Erro no envio')
        time.sleep(30)


def processar_fila():
    if get_cfg('pausado') == '1':
        return
    with _lock, db() as c:
        item = c.execute("SELECT * FROM fila WHERE status='aprovado' AND (agendado_para IS NULL OR agendado_para='' "
                         "OR agendado_para<=?) ORDER BY COALESCE(NULLIF(agendado_para,''), aprovado_em) LIMIT 1",
                         (agora().isoformat(),)).fetchone()
        if not item:
            return
        c.execute("UPDATE fila SET status='enviando' WHERE id=?", (item['id'],))
    grupos = json.loads(item['grupos'] or '[]')
    random.shuffle(grupos)                     # ordem dos grupos também muda a cada postagem
    erros, usados, anterior = [], {}, None
    for i, jid in enumerate(grupos):
        if get_cfg('pausado') == '1':
            erros.append('pausado no meio do envio')
            break
        with db() as c:
            nome = (c.execute('SELECT nome FROM grupos WHERE jid=?', (jid,)).fetchone() or [jid])[0]
            if posts_hoje(c, jid) >= CFG['limite_dia']:
                erros.append(f'{nome}: limite de {CFG["limite_dia"]} posts/dia atingido')
                continue
            ja = c.execute('SELECT 1 FROM envios WHERE fila_id=? AND jid=? AND ok=1', (item['id'], jid)).fetchone()
        if ja:
            continue
        inst = sortear_chip(jid, anterior)
        ok, erro = 1, None
        if not inst:
            ok, erro = 0, 'nenhum chip conectado está neste grupo'
        else:
            try:
                enviar_texto(inst, jid, item['texto'])
                usados[inst] = usados.get(inst, 0) + 1
                anterior = inst
                log.info(f"Fila {item['id']} → {nome} pelo chip {inst}")
            except Exception as e:
                ok, erro = 0, str(e)[:300]
        if not ok:
            erros.append(f'{nome}: {erro}')
        with _lock, db() as c:
            c.execute('INSERT INTO envios (fila_id, jid, chave, quando, ok, erro, instancia) VALUES (?,?,?,?,?,?,?)',
                      (item['id'], jid, item['chave'], agora().isoformat(), ok, erro, inst))
        if i < len(grupos) - 1:
            time.sleep(random.randint(CFG['intervalo_min'], max(CFG['intervalo_min'], CFG['intervalo_max'])))
    with _lock, db() as c:
        status = 'erro' if erros and len(erros) >= len(grupos) else 'enviado'
        c.execute('UPDATE fila SET status=?, enviado_em=?, erro=? WHERE id=?',
                  (status, agora().isoformat(), '\n'.join(erros) or None, item['id']))
    if item['pedido_por']:
        resumo = ', '.join(f'{k}: {v}' for k, v in usados.items()) or 'nenhum'
        aviso = (f"✅ Postado: *{item['produto'][:60]}*\n{sum(usados.values())} grupo(s) · chips usados → {resumo}"
                 + (f"\n⚠️ {chr(10).join(erros)}" if erros else ''))
        responder(item['pedido_inst'], item['pedido_por'], aviso)


# ---------------------------------------------------------------- chamada automática (IA)

def chave_openai():
    k = os.getenv('OPENAI_API_KEY', '')
    if not k and Path(CFG['central_env']).exists():
        for line in Path(CFG['central_env']).read_text(encoding='utf-8').splitlines():
            a, _, v = line.partition('=')
            if a.strip() == 'OPENAI_API_KEY':
                k = v.strip().strip('"\'')
    return k


def gerar_chamada(produto):
    """Frase curta em MAIÚSCULAS com 1 emoji, no estilo dos grupos de ofertas. Sem IA: frase padrão."""
    key = chave_openai()
    if key and produto:
        prompt = ("Você escreve chamadas para grupos de ofertas no WhatsApp. Crie UMA chamada curta (máx. 7 palavras) "
                  "em MAIÚSCULAS, terminando com '!' e 1 emoji que combine, destacando o principal benefício do produto. "
                  "Exemplos: 'TREINE CONFORTÁVEL E SEM TRANSPARÊNCIA! 🏋️', 'CAIXAS QUE TRANSFORMAM SEU ESPAÇO! 📦', "
                  "'CUIDADO CERÂMICO PRA SUA SAÚDE! 🍳'. Não invente preço, desconto ou promessas falsas. "
                  f"Responda só a chamada.\nProduto: {produto}")
        try:
            req = urllib.request.Request('https://api.openai.com/v1/chat/completions', headers={
                'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                data=json.dumps({'model': CFG['openai_model'],
                                 'messages': [{'role': 'user', 'content': prompt}]}).encode())
            with urllib.request.urlopen(req, timeout=40) as r:
                txt = json.load(r)['choices'][0]['message']['content'].strip().strip('"*').splitlines()[0]
            if 3 < len(txt) < 90:
                return txt.upper()
        except Exception as e:
            log.warning(f'Chamada automática falhou: {e}')
    return 'OFERTA IMPERDÍVEL! 🔥'


# ---------------------------------------------------------------- conversa no WhatsApp (mandar links)

MENU = ("Responda com:\n*1* ✅ aprovar e postar agora\n*2* ✏️ trocar a chamada\n*3* 💸 colocar o preço \"De:\"\n"
        "*4* 💰 trocar o preço \"Por:\"\n*5* 🕒 agendar (ex.: *5 20h* ou *5 20:30*)\n*0* 🗑️ descartar")


def montar_texto(p):
    linhas = [l for l in (get_cfg('modelo', MODELO_PADRAO)).split('\n') if '{preco_de}' not in l or p.get('preco_de')]
    return re.sub(r'\{(\w+)\}', lambda m: str(p.get(m.group(1), '') or ''), '\n'.join(linhas))


def digitos(x):
    return re.sub(r'\D', '', x or '')


def autorizado(numeros):
    for n in numeros:
        d = digitos(n)
        if len(d) >= 8 and any(a[-8:] == d[-8:] for a in CFG['autorizados']):
            return True
    return False


def responder(inst, para, texto, previa=False):
    try:
        enviar_texto(inst, para, texto, previa)
    except Exception as e:
        log.warning(f'Resposta para {para} falhou: {e}')


def grupos_ativos():
    with db() as c:
        return [r[0] for r in c.execute('SELECT jid FROM grupos WHERE ativo=1')]


def conversa_get(numero):
    with db() as c:
        r = c.execute('SELECT * FROM conversa WHERE numero=?', (numero,)).fetchone()
    return dict(r) if r else {'numero': numero, 'fila_id': None, 'esperando': ''}


def conversa_set(numero, fila_id, esperando=''):
    with _lock, db() as c:
        c.execute('INSERT OR REPLACE INTO conversa VALUES (?,?,?)', (numero, fila_id, esperando))


def item_fila(fid):
    with db() as c:
        r = c.execute('SELECT * FROM fila WHERE id=?', (fid,)).fetchone()
    return dict(r) if r else None


def regravar(item, **mud):
    dados = json.loads(item.get('dados') or '{}')
    dados.update(mud)
    texto = montar_texto(dados)
    with _lock, db() as c:
        c.execute('UPDATE fila SET texto=?, dados=?, preco=? WHERE id=?', (texto, json.dumps(dados), dados.get('preco'), item['id']))
    return texto


def receber_webhook(payload):
    if (payload.get('event') or '').lower().replace('_', '.') != 'messages.upsert':
        return
    inst = payload.get('instance') or ''
    data = payload.get('data') or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    key = data.get('key') or {}
    jid = key.get('remoteJid') or ''
    if key.get('fromMe') or jid.endswith('@g.us') or jid.endswith('@broadcast'):
        return
    if not autorizado([jid, key.get('remoteJidAlt'), key.get('senderPn'), data.get('sender')]):
        return
    msg = data.get('message') or {}
    texto = (msg.get('conversation') or (msg.get('extendedTextMessage') or {}).get('text')
             or (msg.get('imageMessage') or {}).get('caption') or '').strip()
    if texto:
        threading.Thread(target=tratar_mensagem, args=(inst, jid, texto), daemon=True).start()


def tratar_mensagem(inst, numero, texto):
    try:
        _tratar(inst, numero, texto)
    except Exception as e:
        log.exception('Conversa')
        responder(inst, numero, f'⚠️ Deu erro: {str(e)[:150]}')


def _tratar(inst, numero, texto):
    conv = conversa_get(numero)
    link = re.search(r'https?://\S+', texto)
    if link:                                         # link novo = nova postagem
        responder(inst, numero, '⏳ Montando a postagem…')
        url = link.group(0).rstrip('.,)')
        ids = None
        if 'shopee' in url or 'shp.ee' in url:
            try:
                final = urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers={
                    'User-Agent': 'Mozilla/5.0'}), timeout=15).geturl()
            except Exception:
                final = url
            m = re.search(r'/product/(\d+)/(\d+)', final) or re.search(r'i\.(\d+)\.(\d+)', final)
            ids = f'{m.group(1)}:{m.group(2)}' if m else None
        if ids:
            p = {'origem': 'whatsapp', 'chave': ids, 'link': url if 's.shopee' in url else '', 'produto': ''}
            nodes = []
            try:
                a, b = ids.split(':')
                nodes = shopee_gql(f'{{productOfferV2(shopId:{a},itemId:{b},limit:1){{nodes{{productName}}}}}}')['productOfferV2']['nodes']
            except Exception:
                pass
            p['produto'] = nodes[0]['productName'] if nodes else ''
            p = preparar(p)
        else:
            p = ler_link(url)
            p['origem'] = 'whatsapp'
            p = preparar(p)
        if bloqueado(p.get('produto')):
            return responder(inst, numero, '🚫 Produto de suplementação: não posto esse tipo de produto.')
        if not p.get('produto'):
            p['produto'] = 'Oferta'
            p['avisos'].append('Não consegui ler o nome do produto: mande *2* para escrever a chamada e edite no app se quiser.')
        p['chamada'] = gerar_chamada(p['produto'])
        p['produto'] = p['produto'][:120]
        grupos = grupos_ativos()
        with _lock, db() as c:
            cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, comissao, link, texto, grupos, criado_em, '
                            'dados, pedido_por, pedido_inst) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            ('whatsapp', p.get('chave'), p['produto'], p.get('preco'), p.get('comissao', ''), p['link'],
                             montar_texto(p), json.dumps(grupos), agora().isoformat(), json.dumps(p), numero, inst))
            fid = cur.lastrowid
        conversa_set(numero, fid)
        item = item_fila(fid)
        responder(inst, numero, item['texto'], previa=True)
        extra = ('\n⚠️ ' + '\n⚠️ '.join(p['avisos'])) if p.get('avisos') else ''
        sem_preco = '' if p.get('preco') else '\n⚠️ Sem preço: mande *4* para colocar.'
        responder(inst, numero, f"👆 Prévia · vai para {len(grupos)} grupo(s){extra}{sem_preco}\n\n{MENU}")
        return

    item = item_fila(conv['fila_id']) if conv['fila_id'] else None
    if not item or item['status'] not in ('rascunho', 'erro'):
        return responder(inst, numero, '📲 Me mande o link de um produto (Shopee, Magalu, Mercado Livre, Amazon…) '
                                       'que eu monto a postagem.')
    esperando, t = conv['esperando'], texto.strip()
    if esperando:
        conversa_set(numero, item['id'])
        campo = {'chamada': 'chamada', 'de': 'preco_de', 'por': 'preco'}[esperando]
        valor = t.upper() if campo == 'chamada' else br(t)
        regravar(item, **{campo: valor})
        responder(inst, numero, item_fila(item['id'])['texto'], previa=True)
        return responder(inst, numero, f'👆 Atualizado.\n\n{MENU}')
    cmd, _, resto = t.partition(' ')
    if cmd == '1':
        grupos = json.loads(item['grupos'] or '[]')
        if not grupos:
            return responder(inst, numero, '⚠️ Nenhum grupo marcado. Marque os grupos no app (👥 Grupos).')
        with _lock, db() as c:
            c.execute("UPDATE fila SET status='aprovado', aprovado_em=?, erro=NULL WHERE id=?", (agora().isoformat(), item['id']))
        conversa_set(numero, None)
        quando = item['agendado_para']
        return responder(inst, numero, f"✅ Aprovado! {'Posto às ' + quando[11:16] if quando else 'Começando a postar'} em "
                                       f"{len(grupos)} grupo(s), sorteando entre os chips. Aviso quando terminar.")
    if cmd in ('2', '3', '4'):
        esp = {'2': 'chamada', '3': 'de', '4': 'por'}[cmd]
        if resto:
            conversa_set(numero, item['id'], esp)
            return _tratar(inst, numero, resto)
        conversa_set(numero, item['id'], esp)
        return responder(inst, numero, {'chamada': '✏️ Mande a nova chamada:', 'de': '💸 Mande o preço "De:" (ex.: 149,90):',
                                        'por': '💰 Mande o preço "Por:" (ex.: 99,90):'}[esp])
    if cmd == '5':
        m = re.match(r'(\d{1,2})(?:[:h](\d{2}))?h?$', resto.strip().lower())
        if not m:
            return responder(inst, numero, '🕒 Mande assim: *5 20h* ou *5 20:30*')
        quando = agora().replace(hour=int(m.group(1)), minute=int(m.group(2) or 0), second=0, microsecond=0)
        if quando < agora():
            quando += timedelta(days=1)
        with _lock, db() as c:
            c.execute("UPDATE fila SET agendado_para=?, status='aprovado', aprovado_em=? WHERE id=?",
                      (quando.isoformat(), agora().isoformat(), item['id']))
        conversa_set(numero, None)
        return responder(inst, numero, f"🕒 Agendado para {quando.strftime('%d/%m às %H:%M')}. Aviso quando postar.")
    if cmd == '0':
        with _lock, db() as c:
            c.execute("UPDATE fila SET status='descartado' WHERE id=?", (item['id'],))
        conversa_set(numero, None)
        return responder(inst, numero, '🗑️ Descartado.')
    responder(inst, numero, MENU)


# ---------------------------------------------------------------- login simples

def token():
    dia = agora().strftime('%Y%m')
    return hmac.new(CFG['segredo'].encode(), f'ok{dia}'.encode(), 'sha256').hexdigest()


# ---------------------------------------------------------------- HTTP

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def logado(self):
        c = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        return 'pz' in c and hmac.compare_digest(c['pz'].value, token())

    def send_json(self, obj, code=200, extra=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def rota(self):
        p = urllib.parse.urlparse(self.path).path
        for pre in ('/zap',):
            if p.startswith(pre):
                p = p[len(pre):]
        return p or '/'

    def do_GET(self):
        p = self.rota()
        if p in ('/', '/index.html'):
            html = (BASE / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if p.startswith('/l/'):
            pg = pagina_link(p[3:])
            self.send_response(200 if pg else 404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(pg or b'Link nao encontrado')
            return
        if not self.logado():
            return self.send_json({'erro': 'login'}, 401)
        try:
            if p == '/api/produtos':
                g, eg = produtos_garimpo()
                ce, ec = produtos_central()
                env = ultimos_envios()
                for x in g + ce:
                    x['ultimo_envio'] = env.get(x['chave'], '')
                return self.send_json({'produtos': ce + g, 'avisos': [a for a in (eg, ec) if a]})
            if p == '/api/whatsapp':
                return self.send_json({'chips': [whatsapp_status(i) for i in instancias()]})
            if p == '/api/grupos':
                with db() as c:
                    rows = [dict(r) for r in c.execute('SELECT * FROM grupos ORDER BY ativo DESC, nome')]
                    for r in rows:
                        r['hoje'] = posts_hoje(c, r['jid'])
                        r['chips'] = [x[0] for x in c.execute('SELECT instancia FROM grupo_chips WHERE jid=?', (r['jid'],))]
                return self.send_json({'grupos': rows})
            if p == '/api/fila':
                with db() as c:
                    rows = [dict(r) for r in c.execute(
                        "SELECT * FROM fila WHERE status!='descartado' ORDER BY id DESC LIMIT 200")]
                return self.send_json({'fila': rows, 'pausado': get_cfg('pausado') == '1'})
            if p == '/api/config':
                return self.send_json({'modelo': get_cfg('modelo', MODELO_PADRAO),
                                       'intervalo': [CFG['intervalo_min'], CFG['intervalo_max']],
                                       'limite_dia': CFG['limite_dia'], 'repetir_dias': CFG['repetir_dias']})
        except Exception as e:
            log.exception('GET')
            return self.send_json({'erro': str(e)}, 500)
        self.send_json({'erro': 'não encontrado'}, 404)

    def do_POST(self):
        p = self.rota()
        b = self.body()
        if CFG['webhook_segredo'] and p == f"/webhook/{CFG['webhook_segredo']}":
            try:
                receber_webhook(b)
            except Exception:
                log.exception('webhook')
            return self.send_json({'ok': True})
        if p == '/api/login':
            if CFG['senha'] and hmac.compare_digest(str(b.get('senha', '')), CFG['senha']):
                return self.send_json({'ok': True}, extra={
                    'Set-Cookie': f'pz={token()}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000'})
            time.sleep(1)
            return self.send_json({'erro': 'senha incorreta'}, 403)
        if not self.logado():
            return self.send_json({'erro': 'login'}, 401)
        try:
            return self.post(p, b)
        except Exception as e:
            log.exception('POST')
            return self.send_json({'erro': str(e)}, 500)

    def post(self, p, b):
        if p == '/api/ler_link':
            return self.send_json(ler_link(b.get('url', '')))
        if p == '/api/preparar':
            if bloqueado(b.get('produto')):
                return self.send_json({'erro': 'Produto de suplementação não pode ser postado.'}, 400)
            return self.send_json(preparar(b))
        if p == '/api/grupos/atualizar':
            return self.send_json({'total': atualizar_grupos()})
        if p == '/api/grupos/ativo':
            with _lock, db() as c:
                c.execute('UPDATE grupos SET ativo=? WHERE jid=?', (1 if b.get('ativo') else 0, b['jid']))
            return self.send_json({'ok': True})
        if p == '/api/whatsapp/desconectar':
            if b.get('instancia') not in instancias():
                return self.send_json({'erro': 'chip desconhecido'}, 400)
            evo('DELETE', f"/instance/logout/{b['instancia']}")
            _estado_cache.pop(b['instancia'], None)
            return self.send_json({'ok': True})
        if p == '/api/modelo':
            set_cfg('modelo', b.get('modelo') or MODELO_PADRAO)
            return self.send_json({'ok': True})
        if p == '/api/pausar':
            set_cfg('pausado', '1' if b.get('pausado') else '0')
            return self.send_json({'ok': True})
        if p == '/api/fila/criar':
            if bloqueado(b.get('produto')):
                return self.send_json({'erro': 'Produto de suplementação não pode ser postado.'}, 400)
            with _lock, db() as c:
                cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, comissao, link, texto, grupos, '
                                'agendado_para, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?)',
                                (b.get('origem'), b.get('chave'), b.get('produto'), b.get('preco'), b.get('comissao'),
                                 b.get('link'), b.get('texto'), json.dumps(b.get('grupos') or []),
                                 b.get('agendado_para') or '', agora().isoformat()))
            return self.send_json({'id': cur.lastrowid})
        if p == '/api/fila/editar':
            with _lock, db() as c:
                c.execute("UPDATE fila SET texto=?, grupos=?, agendado_para=? WHERE id=? AND status IN ('rascunho','erro')",
                          (b.get('texto'), json.dumps(b.get('grupos') or []), b.get('agendado_para') or '', b['id']))
            return self.send_json({'ok': True})
        if p == '/api/fila/aprovar':
            with _lock, db() as c:
                it = c.execute('SELECT grupos FROM fila WHERE id=?', (b['id'],)).fetchone()
                if not it or not json.loads(it['grupos'] or '[]'):
                    return self.send_json({'erro': 'Escolha pelo menos um grupo antes de aprovar.'}, 400)
                c.execute("UPDATE fila SET status='aprovado', aprovado_em=?, erro=NULL WHERE id=? "
                          "AND status IN ('rascunho','erro')", (agora().isoformat(), b['id']))
            return self.send_json({'ok': True})
        if p == '/api/fila/voltar':
            with _lock, db() as c:
                c.execute("UPDATE fila SET status='rascunho' WHERE id=? AND status='aprovado'", (b['id'],))
            return self.send_json({'ok': True})
        if p == '/api/fila/descartar':
            with _lock, db() as c:
                c.execute("UPDATE fila SET status='descartado' WHERE id=? AND status!='enviando'", (b['id'],))
            return self.send_json({'ok': True})
        self.send_json({'erro': 'não encontrado'}, 404)


def main():
    if not CFG['senha']:
        raise SystemExit('Defina POSTZAP_SENHA no arquivo .env')
    init_db()
    with _lock, db() as c:   # envio interrompido por reinício volta para aprovado (não repete grupos já enviados)
        c.execute("UPDATE fila SET status='aprovado' WHERE status='enviando'")
    threading.Thread(target=worker, daemon=True).start()
    if not CFG['autorizados']:
        log.warning('NUMEROS_AUTORIZADOS vazio: a conversa de links pelo WhatsApp fica desligada')
    srv = ThreadingHTTPServer(('127.0.0.1', CFG['porta']), H)
    log.info(f"PostZap em http://127.0.0.1:{CFG['porta']}/zap")
    srv.serve_forever()


if __name__ == '__main__':
    main()
