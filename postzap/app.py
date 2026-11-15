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
    'evo_inst': os.getenv('EVOLUTION_INSTANCIA', 'postzap'),
    'intervalo_min': int(os.getenv('INTERVALO_MIN_SEG', '90')),
    'intervalo_max': int(os.getenv('INTERVALO_MAX_SEG', '240')),
    'limite_dia': int(os.getenv('LIMITE_POSTS_DIA_POR_GRUPO', '8')),
    'repetir_dias': int(os.getenv('NAO_REPETIR_DIAS', '7')),
    'comissao_min': float(os.getenv('COMISSAO_MIN', '9')),
}
BLOQUEADOS = ('suplement', 'vitamin', 'colágeno', 'colageno', 'whey', 'creatina', 'termogênic', 'termogenic')

MODELO_PADRAO = """🔥 *{produto}*

💰 Por apenas *R$ {preco}*
⭐ Nota {nota} · {vendas} vendidos

👉 {link}

_Promoção por tempo limitado — o preço pode mudar a qualquer momento._"""

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
"""
_lock = threading.Lock()


def db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript(SCHEMA)


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
        posts = conn.execute("SELECT product_key, product_name, products, links, posted_at FROM posts "
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
                    'detalhe': f"Já postado em vídeo · {(p['posted_at'] or '')[:10]}"})
    return out, ''


def ultimos_envios():
    """chave -> data do último envio (para avisar repetição)."""
    with db() as c:
        rows = c.execute('SELECT chave, MAX(quando) q FROM envios WHERE ok=1 GROUP BY chave').fetchall()
    return {r['chave']: r['q'] for r in rows}


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


def whatsapp_status():
    inst = CFG['evo_inst']
    try:
        st = evo('GET', f'/instance/connectionState/{inst}')
    except RuntimeError as e:
        if '404' in str(e):
            evo('POST', '/instance/create', {'instanceName': inst, 'qrcode': True, 'integration': 'WHATSAPP-BAILEYS'})
            st = evo('GET', f'/instance/connectionState/{inst}')
        else:
            return {'estado': 'erro', 'erro': str(e)}
    estado = (st.get('instance') or {}).get('state') or st.get('state') or 'desconhecido'
    res = {'estado': estado}
    if estado != 'open':
        try:
            qr = evo('GET', f'/instance/connect/{inst}')
            res['qr'] = qr.get('base64') or ''
            res['codigo'] = qr.get('pairingCode') or ''
        except RuntimeError as e:
            res['erro'] = str(e)
    return res


def atualizar_grupos():
    lista = evo('GET', f"/group/fetchAllGroups/{CFG['evo_inst']}?getParticipants=false", timeout=60)
    with _lock, db() as c:
        for g in lista:
            c.execute('INSERT INTO grupos (jid, nome) VALUES (?,?) ON CONFLICT(jid) DO UPDATE SET nome=excluded.nome',
                      (g['id'], g.get('subject') or g['id']))
    return len(lista)


def enviar_texto(jid, texto):
    evo('POST', f"/message/sendText/{CFG['evo_inst']}", {'number': jid, 'text': texto, 'linkPreview': True}, timeout=60)


# ---------------------------------------------------------------- envio (fila aprovada)

def posts_hoje(c, jid):
    inicio = agora().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return c.execute('SELECT COUNT(*) FROM envios WHERE jid=? AND ok=1 AND quando>=?', (jid, inicio)).fetchone()[0]


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
    erros = []
    for i, jid in enumerate(grupos):
        if get_cfg('pausado') == '1':
            erros.append('pausado no meio do envio')
            break
        with db() as c:
            if posts_hoje(c, jid) >= CFG['limite_dia']:
                erros.append(f'{jid}: limite de {CFG["limite_dia"]} posts/dia atingido')
                continue
            ja = c.execute('SELECT 1 FROM envios WHERE fila_id=? AND jid=? AND ok=1', (item['id'], jid)).fetchone()
        if ja:
            continue
        ok, erro = 1, None
        try:
            enviar_texto(jid, item['texto'])
            log.info(f"Fila {item['id']} enviada para {jid}")
        except Exception as e:
            ok, erro = 0, str(e)[:300]
            erros.append(f'{jid}: {erro}')
        with _lock, db() as c:
            c.execute('INSERT INTO envios (fila_id, jid, chave, quando, ok, erro) VALUES (?,?,?,?,?,?)',
                      (item['id'], jid, item['chave'], agora().isoformat(), ok, erro))
        if i < len(grupos) - 1:
            time.sleep(random.randint(CFG['intervalo_min'], max(CFG['intervalo_min'], CFG['intervalo_max'])))
    with _lock, db() as c:
        status = 'erro' if erros and len(erros) >= len(grupos) else 'enviado'
        c.execute('UPDATE fila SET status=?, enviado_em=?, erro=? WHERE id=?',
                  (status, agora().isoformat(), '\n'.join(erros) or None, item['id']))


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
                return self.send_json(whatsapp_status())
            if p == '/api/grupos':
                with db() as c:
                    rows = [dict(r) for r in c.execute('SELECT * FROM grupos ORDER BY ativo DESC, nome')]
                    for r in rows:
                        r['hoje'] = posts_hoje(c, r['jid'])
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
        if p == '/api/grupos/atualizar':
            return self.send_json({'total': atualizar_grupos()})
        if p == '/api/grupos/ativo':
            with _lock, db() as c:
                c.execute('UPDATE grupos SET ativo=? WHERE jid=?', (1 if b.get('ativo') else 0, b['jid']))
            return self.send_json({'ok': True})
        if p == '/api/whatsapp/desconectar':
            evo('DELETE', f"/instance/logout/{CFG['evo_inst']}")
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
    srv = ThreadingHTTPServer(('127.0.0.1', CFG['porta']), H)
    log.info(f"PostZap em http://127.0.0.1:{CFG['porta']}/zap")
    srv.serve_forever()


if __name__ == '__main__':
    main()
