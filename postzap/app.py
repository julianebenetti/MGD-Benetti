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
from datetime import date, datetime, timedelta, timezone
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
    # chave pública (anon), a mesma do garimpo-shopee.html: só lê o que a página do Garimpo já lê
    'supabase_key': os.getenv('SUPABASE_KEY', '') or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRreGtyYmR2Y2N0b2FqdWlndnZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NzY2NzUsImV4cCI6MjA5OTQ1MjY3NX0.-szTE2wYYr9DNTLiff6zmLpbP6UOL1l9SFpvc-29Njs',
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
    'amazon_tag': os.getenv('AMAZON_TAG', '').strip(),
    'central_env': os.getenv('CENTRAL_ENV', '/opt/shopee-video/shopee-video-automation/.env'),
}
BLOQUEADOS = ('suplement', 'vitamin', 'colágeno', 'colageno', 'whey', 'creatina', 'termogênic', 'termogenic')

MODELO_PADRAO = """*{chamada}*

🛍️ {produto}

~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* ✅
💠 {pix} no Pix
💳 {parcelamento}
🎟️ Cupom: *{cupom}* {cupom_texto}

👉 {cta}
🔗 *Compre aqui:* {link}

⚠️ Todas as promoções estão sujeitas a alterações a qualquer momento."""

# Estilos prontos (editáveis no app). Linha cujos campos {..} estão todos vazios some sozinha.
ESTILOS_PADRAO = {
    'Padrão': MODELO_PADRAO,
    'Relâmpago': """⚡ *OFERTA RELÂMPAGO* ⚡
*{chamada}*

🛍️ {produto}

~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* 🔥
🎟️ Cupom: *{cupom}* {cupom_texto}

👉 {cta}
🔗 {link}

⚠️ Todas as promoções estão sujeitas a alterações a qualquer momento.""",
    'Cupom': """🎟️ *CUPOM LIBERADO!*
*{chamada}*

🛍️ {produto}

Use o cupom: *{cupom}* {cupom_texto}
~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* ✅

👉 {cta}
🔗 *Compre aqui:* {link}

⚠️ Cupom sujeito a disponibilidade e às regras da loja.""",
    'VIP': """👑 *EXCLUSIVO DO GRUPO VIP* 👑
*{chamada}*

🛍️ {produto}

~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* ✅
🎟️ Cupom: *{cupom}* {cupom_texto}

👉 {cta}
🔗 {link}

⚠️ Todas as promoções estão sujeitas a alterações a qualquer momento.""",
}
LOJAS_NOMES = ('Shopee', 'Magalu', 'Mercado Livre', 'Amazon', 'Outras')

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
CREATE TABLE IF NOT EXISTS listas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, grupos TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS cupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, loja TEXT, codigo TEXT, texto TEXT, validade TEXT, ativo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS chip_eventos (    -- conexões/quedas de cada chip (para ver reconexões frequentes)
    id INTEGER PRIMARY KEY AUTOINCREMENT, instancia TEXT, estado TEXT, numero TEXT, nome TEXT, quando TEXT
);
CREATE TABLE IF NOT EXISTS cliques (          -- cada clique de pessoa (robôs de prévia não contam), por grupo
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, grupo INTEGER, quando TEXT
);
CREATE TABLE IF NOT EXISTS previas (          -- mensagem de prévia → post (para responder em cima de cada uma)
    msg_id TEXT PRIMARY KEY, fila_id INTEGER, quando TEXT
);
CREATE TABLE IF NOT EXISTS enquetes (           -- enquete enviada a um grupo (para contar os votos)
    msg_id TEXT PRIMARY KEY, fila_id INTEGER, jid TEXT, opcoes TEXT, quando TEXT
);
CREATE TABLE IF NOT EXISTS votos (
    msg_id TEXT, eleitor TEXT, opcoes TEXT, quando TEXT, PRIMARY KEY (msg_id, eleitor)
);
CREATE TABLE IF NOT EXISTS pedidos_inbox (       -- o que as pessoas pedem no privado (e o que recebeu)
    id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT, texto TEXT, resultado TEXT, quando TEXT
);
CREATE TABLE IF NOT EXISTS membros (dia TEXT, jid TEXT, entradas INTEGER DEFAULT 0, saidas INTEGER DEFAULT 0, total INTEGER, PRIMARY KEY (dia, jid));
CREATE TABLE IF NOT EXISTS monitor_vistos (chave TEXT PRIMARY KEY, quando TEXT);
CREATE TABLE IF NOT EXISTS vendas (             -- vendas da Shopee ligadas ao post/grupo pelos Sub IDs (postzap-origem-data-gN)
    chave TEXT PRIMARY KEY, fila_id INTEGER, jid TEXT, item TEXT, produto TEXT, valor REAL, comissao REAL, status TEXT,
    quando TEXT, sub TEXT
);
CREATE TABLE IF NOT EXISTS links (           -- links curtos com prévia (foto + título) no WhatsApp
    codigo TEXT PRIMARY KEY, destino TEXT, titulo TEXT, imagem TEXT, criado_em TEXT, cliques INTEGER DEFAULT 0
);
"""
_lock = threading.RLock()   # reentrante: montar o texto dentro de uma transação pode gravar config


def db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript(SCHEMA)
        for tab, col in (('envios', 'instancia TEXT'), ('fila', 'dados TEXT'), ('fila', 'pedido_por TEXT'),
                         ('fila', 'pedido_inst TEXT'), ('grupo_chips', 'admin INTEGER'), ('grupos', 'admin INTEGER'),
                         ('envios', 'msg_id TEXT'), ('envios', 'wa_status TEXT')):
            if col.split()[0] not in {r[1] for r in c.execute(f'PRAGMA table_info({tab})')}:
                c.execute(f'ALTER TABLE {tab} ADD COLUMN {col}')


def get_cfg(k, default=''):
    with db() as c:
        r = c.execute('SELECT v FROM config WHERE k=?', (k,)).fetchone()
    return r[0] if r else default


def set_cfg(k, v):
    with _lock, db() as c:
        c.execute('INSERT OR REPLACE INTO config VALUES (?,?)', (k, v))


def get_json(k, default):
    try:
        return json.loads(get_cfg(k, '')) if get_cfg(k, '') else default
    except ValueError:
        return default


def modelos():
    m = get_json('modelos', None)
    if not m:                                   # 1ª vez: estilos prontos (o modelo antigo vira o "Padrão")
        m = dict(ESTILOS_PADRAO)
        if get_cfg('modelo'):
            m['Padrão'] = get_cfg('modelo')
    if get_cfg('migr_cta') != '1':              # 1ª vez: põe a linha da CTA ({cta}) antes do link nos estilos salvos
        for k, v in m.items():
            if '{cta}' not in v and '{link}' in v:
                ls = v.split('\n')
                i = next(j for j, l in enumerate(ls) if '{link}' in l)
                ls.insert(i, '👉 {cta}')
                m[k] = '\n'.join(ls)
        set_cfg('modelos', json.dumps(m, ensure_ascii=False))
        set_cfg('migr_cta', '1')
    return m


CTAS_PADRAO = ['Corre que é por tempo limitado! 🏃‍♀️', 'Aproveita antes que acabe o estoque! 🔥', 'Garanta o seu agora! 🛒',
               'Clica no link e confere! 👇', 'Esse preço não vai durar! ⏳', 'Últimas unidades com esse valor! ⚡',
               'Vale cada centavo, confia! 💖', 'Compartilha com quem vai amar! 💬']


def gerar_cta(produto):
    """CTA (chamada para ação) do post, revezando entre as suas (✏️ Mensagens) ou criada pela IA."""
    modo = get_cfg('cta_modo', 'frases')
    lista = [c for c in get_json('ctas', CTAS_PADRAO) if c.strip()]
    if modo == 'nenhum':
        return ''
    if lista and (modo == 'frases' or (modo == 'misto' and random.random() < 0.5) or not chave_openai()):
        return random.choice(lista).strip()
    try:
        req = urllib.request.Request('https://api.openai.com/v1/chat/completions', headers={
            'Authorization': f'Bearer {chave_openai()}', 'Content-Type': 'application/json'},
            data=json.dumps({'model': CFG['openai_model'], 'messages': [{'role': 'user', 'content':
                'Escreva UMA frase curta (máx. 8 palavras) de chamada para ação para um grupo de ofertas no WhatsApp, '
                'com 1 emoji no final, sem preço, sem promessas falsas, sem aspas. Estilo: ' + '; '.join(lista[:4]) +
                f'. Produto: {produto}'}]}).encode())
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = json.load(r)['choices'][0]['message']['content'].strip().strip('"').splitlines()[0]
        if 3 < len(txt) < 80:
            return txt
    except Exception as e:
        log.warning(f'CTA pela IA falhou: {e}')
    return random.choice(lista).strip() if lista else ''


def estilo_da_loja(loja):
    return get_json('estilo_loja', {}).get(loja or 'Outras') or get_json('estilo_loja', {}).get('Outras') or 'Padrão'


def cupom_para(loja):
    hoje = agora().date().isoformat()
    with db() as c:
        r = c.execute("SELECT codigo, texto FROM cupons WHERE ativo=1 AND (loja=? OR loja='Todas') "
                      "AND (validade IS NULL OR validade='' OR validade>=?) ORDER BY id DESC LIMIT 1",
                      (loja or '', hoje)).fetchone()
    return (r[0], r[1] or '') if r else ('', '')


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
        if bloqueado(p.get('produto')) or com < piso_comissao(classificar_nicho(p.get('produto'), p.get('nicho'))) or not p.get('link'):
            continue
        chave = f"{p.get('shop_id')}:{p.get('item_id')}" if p.get('item_id') else f"g{p['id']}"
        out.append({'origem': 'garimpo', 'chave': chave, 'produto': p.get('produto') or '', 'loja': p.get('loja') or '',
                    'preco': br(p.get('preco')), 'comissao': br(com), 'vendas': p.get('vendas') or 0,
                    'nota': p.get('nota') or '', 'link': p['link'],
                    'nicho': classificar_nicho(p.get('produto'), p.get('nicho')),
                    'focos': classificar_focos(p.get('produto'), p.get('nicho')),
                    'detalhe': ' · '.join(x for x in (p.get('nicho'), p.get('tipo'), data_tela(p.get('data_indicacao'))) if x)})
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
            if not r.get('link') or bloqueado(r.get('produto')) or \
                    num(r.get('comissao')) < piso_comissao(classificar_nicho(r.get('produto'), r.get('secao'))):
                continue
            vistos.add(chave)
            out.append({'origem': 'central_ideias', 'chave': chave, 'produto': r.get('produto', ''),
                        'loja': r.get('loja', ''), 'preco': br(r.get('preco')), 'comissao': br(r.get('comissao')),
                        'vendas': r.get('vendas') or 0, 'nota': r.get('nota') or '', 'link': r['link'],
                        'nicho': classificar_nicho(r.get('produto'), f"{r.get('secao', '')} {r.get('tema', '')}"),
                        'focos': classificar_focos(r.get('produto'), f"{r.get('secao', '')} {r.get('tema', '')}"),
                        'detalhe': f"Ideias de {data_tela(data.get('dia'))} · {r.get('secao', '')}"})
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
                    'nicho': classificar_nicho(p['product_name']),
                    'focos': classificar_focos(p['product_name']),
                    'detalhe': f"Já postado em vídeo · {data_tela(p['posted_at'])}"})
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


ID_PADROES = (re.compile(r'/(?:product|opaanlp)/(\d+)/(\d+)'), re.compile(r'-i\.(\d+)\.(\d+)'),
              re.compile(r'[?&]shopid=(\d+).*?[?&]itemid=(\d+)', re.I))


def ids_no_texto(texto):
    t = urllib.parse.unquote(urllib.parse.unquote(texto or ''))   # destino escondido em ?next= (tela de login)
    for pad in ID_PADROES:
        m = pad.search(t)
        if m:
            return f'{m.group(1)}:{m.group(2)}'
    return None


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def ids_do_link_shopee(url):
    """Link curto (s.shopee.com.br, shp.ee) → 'loja:item'. Segue cada redirecionamento à mão (GET, como navegador)
    e procura os ids em cada endereço e, no fim, no HTML da página."""
    abrir = urllib.request.build_opener(_SemRedirecionar)
    atual = url
    for _ in range(8):
        ids = ids_no_texto(atual)
        if ids:
            return ids
        req = urllib.request.Request(atual, headers={
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'pt-BR,pt;q=0.9'})
        try:
            with abrir.open(req, timeout=20) as r:
                return ids_no_texto(r.read(400_000).decode('utf-8', 'ignore'))
        except urllib.error.HTTPError as e:
            destino = e.headers.get('Location')
            if e.code in (301, 302, 303, 307, 308) and destino:
                atual = urllib.parse.urljoin(atual, destino)
                continue
            return ids_no_texto(e.read(400_000).decode('utf-8', 'ignore'))
        except Exception as e:
            log.warning(f'Não consegui abrir {atual}: {e}')
            return None
    return ids_no_texto(atual)


MESES = ('Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez')


def data_sub(d):
    """Data dos Sub IDs no padrão ddMmmaa (ex.: 18Nov26), o mesmo do robô do Shopee Vídeo."""
    return f"{d.day:02d}{MESES[d.month - 1]}{d:%y}"


def data_tela(valor, hora=False):
    """'2026-11-18' / ISO / date → '18Nov26' (com hora: '18Nov26 20:30'). Vazio ou inválido: devolve como veio."""
    if not valor:
        return ''
    try:
        d = valor if isinstance(valor, (date, datetime)) else datetime.fromisoformat(str(valor).replace('Z', '+00:00'))
    except ValueError:
        return str(valor)
    if isinstance(d, datetime) and d.tzinfo:
        d = d.astimezone(BRT)
    return data_sub(d) + (f" {d:%H:%M}" if hora and isinstance(d, datetime) else '')


NICHOS = ['🏠 Casa e decoração', '🍳 Cozinha e utensílios', '🔌 Eletrodomésticos', '💇 Beleza e cabelo', '👗 Moda',
          '🧸 Infantil', '🎧 Eletrônicos', '🛋️ Móveis', '🐶 Pet', '📦 Outros']
_REGRAS_NICHO = [   # a primeira que bate vale (ordem importa: "forma para air fryer" é cozinha, "air fryer" é eletro)
    ('🐶 Pet', r'\bpet\b|cachorr|gato|ra[cç][aã]o|coleira|arranhador|caminha pet|tapete higi'),
    ('🧸 Infantil', r'infantil|beb[eê]|brinquedo|boneca|carrinho de|crian[cç]a|kids|fralda|mamadeira|chupeta|pel[uú]cia'),
    ('💇 Beleza e cabelo', r'escova (secadora|rotativa|alisadora|modeladora)|secador|chapinha|prancha|modelador|cabelo|maquiag|batom|'
                          r'\bbase\b|perfume|skin ?care|s[eé]rum|hidratante|shampoo|condicionador|\bunha|c[ií]lios|depila|barbeador|'
                          r'beleza|cosm[eé]t|creme facial|protetor solar|esmalte|pinc[eé]is'),
    ('🍳 Cozinha e utensílios', r'\bformas?\b|assadeira|silicone|descart[aá]ve|potes?\b|tigela|escorredor|t[aá]bua|utens[ií]lio|'
                               r'talher|faca|garrafa|copos?\b|x[ií]cara|caneca|pano de prato|porta tempero|marmita|'
                               r'organizador de geladeira|jogo de panelas|panelas? antiaderente|frigideira|ralador|esp[aá]tula|cozinha'),
    ('🔌 Eletrodomésticos', r'air ?fryer|fritadeira|liquidificador|cafeteira|aspirador|micro-?ondas|ventilador|ar[- ]condicionado|'
                           r'batedeira|panela (el[eé]trica|de press[aã]o el)|mixer|processador|ferro de passar|purificador|'
                           r'sanduicheira|grill|forno el[eé]trico|chaleira el|geladeira|lava|umidificador|climatizador'),
    ('🎧 Eletrônicos', r'fone|smartwatch|rel[oó]gio intelig|celular|carregador|caixa de som|\btv\b|notebook|mouse|teclado|'
                      r'c[aâ]mera|smart|bluetooth|power ?bank|tablet|projetor|ring light|cabo usb'),
    ('🛋️ Móveis', r'cadeira|\bmesa\b|guarda-?roupa|arm[aá]rio|sof[aá]|\brack\b|cama box|colch[aã]o|estante|c[oô]moda|'
                  r'penteadeira|gaveteiro|paneleiro|banqueta|escrivaninha'),
    ('🏠 Casa e decoração', r'[aá]rvore de natal|pisca[- ]?pisca|enfeite|guirlanda|pres[eé]pio|bolas? de natal|mesa posta|'
                           r'tapete|cortina|almofada|quadro|espelho|vaso|lumin[aá]ria|jogo de cama|len[cç]ol|edredom|colcha|'
                           r'manta|cobertor|toalha|organizador|cabide|prateleira|decora|banheiro|travesseiro|lixeira|varal|'
                           r'cesto|jardim|abajur|porta-?retrato|casa'),
    ('👗 Moda', r'vestido|blusa|cal[cç]a|short|saia|macac[aã]o|legging|conjunto|suti[aã]|calcinha|cueca|t[eê]nis|sand[aá]lia|'
               r'chinelo|bolsa|mochila|carteira|biqu[ií]ni|mai[oô]|camis|jaqueta|moletom|pijama|meia|bon[eé]|[oó]culos|brinco|colar'),
]
_DICA_NICHO = {'casa': '🏠 Casa e decoração', 'decor': '🏠 Casa e decoração', 'moveis': '🛋️ Móveis', 'móveis': '🛋️ Móveis',
               'eletro': '🔌 Eletrodomésticos', 'beleza': '💇 Beleza e cabelo', 'cabelo': '💇 Beleza e cabelo',
               'moda': '👗 Moda', 'pet': '🐶 Pet', 'infantil': '🧸 Infantil', 'cozinha': '🍳 Cozinha e utensílios',
               'utens': '🍳 Cozinha e utensílios', 'eletron': '🎧 Eletrônicos', 'tapete': '🏠 Casa e decoração'}


# Temas da mineração (público/ocasião, por cima do nicho). Prontos: regra de detecção pelo nome + palavras de busca.
# A Juliane liga/desliga cada um no 🤖 Divulgador e pode criar temas novos (detectados pelas palavras de busca deles).
TEMAS_PRONTOS = {
    '➕ Plus Size': (r'plus ?size|\bplus\b|tamanhos? grandes?|\bg[1-5]\b|\bxg+\b|\bgg+\b',
                    ['vestido plus size', 'conjunto plus size', 'calça plus size', 'blusa plus size', 'macacão plus size',
                     'short plus size', 'sutiã plus size', 'moda praia plus size', 'saia plus size'], True),
    '✝️ Evangélica': (r'evang[eé]lic|crist[aã]|moda (crist|religios)|modest|saia (longa|midi|m[ií]di|god[eê])|'
                     r'vestido (longo|midi|m[ií]di).*(manga|social)|conjunto (social|saia)',
                     ['vestido evangélico', 'saia midi evangélica', 'saia longa', 'conjunto evangélico', 'vestido midi manga',
                      'saia jeans longa'], True),
    '🎄 Natal': (r'natal|natalin|papai noel|noel|[aá]rvore de natal|pisca[- ]?pisca|guirlanda|pres[eé]pio|amigo secreto|ceia|'
                r'bolas? de natal',
                ['decoração de natal', 'árvore de natal', 'pisca pisca', 'enfeite de natal', 'pijama natal família',
                 'roupa natal', 'presente amigo secreto', 'mesa posta natal', 'kit presente natal'], True),
    '🎆 Réveillon': (r'r[eé]veillon|ano novo|virada|roupa branca|vestido branco|ta[cç]a de champanhe',
                    ['vestido branco réveillon', 'conjunto branco feminino', 'roupa ano novo', 'decoração ano novo',
                     'taça de champanhe', 'look réveillon plus size'], False),
    '☀️ Verão e praia': (r'biqu[ií]ni|mai[oô]|sa[ií]da de praia|moda praia|chap[eé]u de praia|canga|bolsa de praia|'
                        r'piscina|ver[aã]o|regata',
                        ['biquíni', 'maiô', 'saída de praia', 'moda praia plus size', 'chapéu de praia', 'vestido verão',
                         'bolsa de praia', 'canga'], False),
    '🎒 Volta às aulas': (r'volta [aà]s aulas|material escolar|mochila escolar|estojo|caderno|lancheira',
                         ['material escolar', 'mochila escolar', 'estojo escolar', 'lancheira', 'kit caderno'], False),
    # Subcategorias de moda que mais vendem nos pedidos dela (sutiã+calcinha 3,2 mil; calçados 2,9 mil; bolsa 1,3 mil; legging 1,1 mil)
    '👙 Moda íntima': (r'suti[aã]|calcinha|lingerie|cinta modeladora|top sem bojo|body rendado|cal[cç]ola|kit calcinha',
                      ['sutiã', 'kit calcinha', 'sutiã plus size', 'lingerie', 'cinta modeladora', 'top sem bojo'], False),
    '👟 Calçados': (r't[eê]nis|sand[aá]lia|chinelo|sapat|\bbota|rasteirinha|tamanco|\bmule\b|scarpin|papete|sapatilha',
                   ['sandália feminina', 'tênis feminino', 'chinelo feminino', 'rasteirinha', 'tamanco', 'papete feminina'], False),
    '👜 Bolsas e acessórios': (r'bolsa|carteira|bijuteria|brinco|colar|pulseira|rel[oó]gio(?! intelig)|[oó]culos de sol|'
                              r'piranha de cabelo|tiara',
                              ['bolsa feminina', 'bolsa transversal', 'kit bijuteria', 'relógio feminino', 'óculos de sol feminino',
                               'carteira feminina'], False),
    '🏋️ Fitness': (r'legging|fitness|academia|treino|top esportivo|macaquinho|cal[cç]a de compress',
                   ['legging', 'conjunto fitness', 'top fitness', 'short fitness', 'legging plus size', 'macaquinho fitness'], False),
    '🎁 Presentes': (r'presente|amigo secreto|lembrancinha|caixa (de )?presente|kit presente',
                    ['kit presente feminino', 'presente para mãe', 'presente amigo secreto', 'kit presente beleza',
                     'presente criativo'], False),
    '🧔 Masculino': (r'masculin|\bhomem\b|cueca|barba|camisa polo|bermuda',
                    ['camiseta masculina', 'bermuda masculina', 'kit cueca', 'tênis masculino', 'kit barba'], False),
}
TEMA_PAI_PRONTO = {'➕ Plus Size': '👗 Moda', '✝️ Evangélica': '👗 Moda', '🎆 Réveillon': '👗 Moda',
                   '☀️ Verão e praia': '👗 Moda', '🎄 Natal': '🏠 Casa e decoração', '🎒 Volta às aulas': '🧸 Infantil',
                   '👙 Moda íntima': '👗 Moda', '👟 Calçados': '👗 Moda', '👜 Bolsas e acessórios': '👗 Moda',
                   '🏋️ Fitness': '👗 Moda', '🧔 Masculino': '👗 Moda'}     # 🎁 Presentes: várias categorias (cor própria)
FOCOS = list(TEMAS_PRONTOS)          # nomes dos temas prontos (os criados por ela vêm de focos_nomes())
_REGRAS_FOCO = [(n, v[0]) for n, v in TEMAS_PRONTOS.items()]


def temas_pai(d=None):
    """Tema → categoria a que ele pertence (mesma cor e aparece embaixo dela na grade). Temas criados: escolhidos por ela."""
    d = d or divulgador_cfg()
    return {**TEMA_PAI_PRONTO, **{k: v for k, v in (d.get('temas_pai') or {}).items() if v in NICHOS}}


def focos_nomes(d=None):
    """Todos os temas (prontos + criados por ela), na ordem."""
    d = d or divulgador_cfg()
    return list(dict.fromkeys(FOCOS + list((d.get('palavras_foco') or {}).keys())))


def classificar_focos(produto, dica=''):
    t = f"{produto or ''} {dica or ''}".lower()
    achados = [f for f, pad in _REGRAS_FOCO if re.search(pad, t)]
    try:                                   # temas criados por ela: bate se o nome tiver uma das palavras de busca dele
        for f, palavras in (get_json('divulgador', {}).get('palavras_foco') or {}).items():
            if f not in TEMAS_PRONTOS and any(w.strip().lower() and w.strip().lower() in t for w in palavras):
                achados.append(f)
    except Exception:
        pass
    return achados


def classificar_nicho(produto, dica=''):
    """Nicho pelo nome do produto (e, se não der, pela seção/nicho de onde ele veio)."""
    t = (produto or '').lower()
    for nicho, pad in _REGRAS_NICHO:
        if re.search(pad, t):
            return nicho
    d = (dica or '').lower()
    for k, n in _DICA_NICHO.items():
        if k in d:
            return n
    return '📦 Outros'


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
        # Sempre gera o SEU link de afiliado (mesmo que tenham mandado um s.shopee de outra pessoa), com Sub IDs
        # para ver no relatório da Shopee: postzap · origem · data
        try:
            origem = f'https://shopee.com.br/product/{ids[0]}/{ids[1]}'
            subs = [CFG['sub_id'], re.sub(r'[^A-Za-z0-9]', '', p.get('origem') or 'app')[:20] or 'app',
                    data_sub(agora())]
            link = shopee_gql(f'mutation{{generateShortLink(input:{{originUrl:{json.dumps(origem)},'
                              f'subIds:{json.dumps(subs)}}}){{shortLink}}}}')['generateShortLink']['shortLink']
            p['sub_ids'] = subs
        except Exception as e:
            avisos.append(f'⚠️ Link NÃO convertido para o seu link de afiliado ({str(e)[:80]}). '
                          'Confira as chaves da Shopee antes de aprovar.')
    if link and loja_do_link(link) == 'Amazon':
        link, aviso = converter_amazon(link)
        if aviso:
            avisos.append(aviso)
    p['link_afiliado'] = link
    # direto (padrão): o link da mensagem é o próprio link da loja → toque abre o app da Shopee na hora.
    # previa: passa pela página do PostZap (miniatura garantida + cliques por grupo), redireciona na hora.
    p['link'] = (link if modo_link() == 'direto' else criar_link_curto(link, p.get('produto', ''), p.get('imagem', ''))) if link else ''
    p['loja'] = 'Shopee' if ids else (p.get('loja') or loja_do_link(link) or 'Outras')
    if not isinstance(p.get('focos'), list):
        p['focos'] = classificar_focos(p.get('produto'), p.get('palavra') or '')
    if not p.get('nicho') or p['nicho'] not in NICHOS:
        p['nicho'] = classificar_nicho(p.get('produto'), p.get('nicho') or p.get('palavra') or '')
    if 'cupom' not in p:
        p['cupom'], p['cupom_texto'] = cupom_para(p['loja'])
    if not p.get('chamada') and p.get('produto'):
        p['chamada'] = gerar_chamada(p['produto'], p['loja'])
    if 'cta' not in p:
        p['cta'] = gerar_cta(p.get('produto', ''))
    p.setdefault('estilo', 'Cupom' if p.get('cupom') and 'Cupom' in modelos() and estilo_da_loja(p['loja']) == 'Padrão'
                 else estilo_da_loja(p['loja']))
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


def modo_link():
    return get_cfg('modo_link', 'direto')


def link_shopee_do_grupo(item, gid):
    """Link de afiliado só deste grupo: Sub IDs postzap · origem · data · g<grupo> → vendas por grupo no relatório."""
    ids = ids_da_chave(item.get('chave'))
    if not ids:
        return None
    subs = [CFG['sub_id'], re.sub(r'[^A-Za-z0-9]', '', item.get('origem') or 'app')[:20] or 'app', data_sub(agora()), f'g{gid}']
    origem = f'https://shopee.com.br/product/{ids[0]}/{ids[1]}'
    return shopee_gql(f'mutation{{generateShortLink(input:{{originUrl:{json.dumps(origem)},'
                      f'subIds:{json.dumps(subs)}}}){{shortLink}}}}')['generateShortLink']['shortLink']


def converter_amazon(url):
    """Coloca a SUA tag de associada (AMAZON_TAG no .env) no link da Amazon; amzn.to é aberto antes."""
    if not CFG['amazon_tag']:
        return url, 'Amazon: sem AMAZON_TAG no .env, o link vai como você mandou (confira se é o seu link de associada).'
    final = url
    if 'amzn.to' in url or 'a.co/' in url:
        try:
            abrir = urllib.request.build_opener(_SemRedirecionar)
            for _ in range(5):
                try:
                    abrir.open(urllib.request.Request(final, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15)
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308) and e.headers.get('Location'):
                        final = urllib.parse.urljoin(final, e.headers['Location'])
                    else:
                        break
        except Exception as e:
            return url, f'Amazon: não consegui abrir o link curto ({str(e)[:60]}); vai como você mandou.'
    u = urllib.parse.urlparse(final)
    if 'amazon.' not in u.netloc:
        return url, 'Amazon: não reconheci o link; vai como você mandou.'
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if k not in ('tag', 'linkCode', 'ref_', 'ascsubtag')]
    q.append(('tag', CFG['amazon_tag']))
    return urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q))), ''


ROBOS = ('whatsapp', 'facebookexternalhit', 'facebot', 'telegrambot', 'twitterbot', 'slackbot', 'discordbot',
         'bot', 'crawler', 'spider', 'preview', 'curl', 'python-urllib', 'headless')


def criar_link_curto(destino, titulo, imagem):
    import secrets
    with _lock, db() as c:
        r = c.execute('SELECT codigo FROM links WHERE destino=? AND imagem=?', (destino, imagem or '')).fetchone()
        if r:
            return f"{CFG['url_publica']}/l/{r[0]}"
        codigo = secrets.token_urlsafe(5).replace('-', 'x').replace('_', 'y')
        c.execute('INSERT INTO links VALUES (?,?,?,?,?,0)', (codigo, destino, titulo, imagem or '', agora().isoformat()))
    return f"{CFG['url_publica']}/l/{codigo}"


def pagina_link(codigo, grupo=None, agente=''):
    """Página do link curto: o WhatsApp lê og:title/og:image (a miniatura), a pessoa é levada à loja.
    Conta só cliques de pessoas (o robô do WhatsApp que monta a prévia não conta), e de qual grupo veio (?g=)."""
    import html as h
    humano = not any(r in (agente or '').lower() for r in ROBOS)
    with _lock, db() as c:
        r = c.execute('SELECT * FROM links WHERE codigo=?', (codigo,)).fetchone()
        if r and humano:
            c.execute('UPDATE links SET cliques=cliques+1 WHERE codigo=?', (codigo,))
            c.execute('INSERT INTO cliques (codigo, grupo, quando) VALUES (?,?,?)',
                      (codigo, int(grupo) if str(grupo or '').isdigit() else None, agora().isoformat()))
    if not r:
        return None
    if humano:
        return ('302', r['destino'])                  # pessoa: vai direto para a loja, sem página no meio
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
            res = json.loads(txt)
        if path.startswith('/message/send') and isinstance(res, dict):
            mid = (res.get('key') or {}).get('id')
            if mid:
                _marcar_visto(mid)        # respostas do próprio PostZap nunca viram comando (nos outros chips)
        return res
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Evolution {e.code}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Evolution fora do ar: {e.reason}")


_webhook_ok = set()
_vistos, _vistos_lock = {}, threading.Lock()


def _marcar_visto(mid):
    """True se a mensagem já foi vista. Os 3 chips recebem a mesma mensagem do grupo da fila: só um responde."""
    with _vistos_lock:
        if mid in _vistos:
            return True
        _vistos[mid] = time.time()
        if len(_vistos) > 5000:
            for k, _ in sorted(_vistos.items(), key=lambda x: x[1])[:2500]:
                _vistos.pop(k, None)
        return False


def normalizar(t):
    import unicodedata
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode().lower())


def e_grupo_fila(nome):
    n = normalizar(nome)
    return 'filapostzap' in n


def grupos_fila():
    with db() as c:
        return {r[0] for r in c.execute('SELECT jid, nome FROM grupos') if e_grupo_fila(r[1])}
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
            'byEvents': False, 'base64': False, 'events': ['MESSAGES_UPSERT', 'MESSAGES_UPDATE', 'GROUP_PARTICIPANTS_UPDATE']}})
        _webhook_ok.add(inst)
    except RuntimeError as e:
        log.warning(f'Webhook de {inst}: {e}')


def registrar_estado(inst, st):
    """Guarda cada mudança conectado ↔ desconectado, com número e horário."""
    st = 'open' if st == 'open' else 'fechado'
    if get_cfg(f'estado_{inst}') == st:
        return
    numero = nome = ''
    if st == 'open':
        try:
            info = evo('GET', f'/instance/fetchInstances?instanceName={inst}')
            info = info[0] if isinstance(info, list) and info else {}
            numero, nome = (info.get('ownerJid') or '').split('@')[0], info.get('profileName') or ''
        except RuntimeError:
            pass
        configurar_webhook(inst)
    with _lock, db() as c:
        c.execute('INSERT INTO chip_eventos (instancia, estado, numero, nome, quando) VALUES (?,?,?,?,?)',
                  (inst, st, numero, nome, agora().isoformat()))
    set_cfg(f'estado_{inst}', st)
    log.info(f'Chip {inst}: {"conectado " + numero if st == "open" else "desconectado"}')


def monitor_chips():
    while True:
        for inst in instancias():
            try:
                st = estado_chip(inst, cache_seg=0)
                if st not in ('erro', 'inexistente'):
                    registrar_estado(inst, st)
            except Exception:
                log.exception('monitor de chips')
        time.sleep(60)


def historico_chip(inst):
    with db() as c:
        ev = [dict(r) for r in c.execute('SELECT estado, numero, nome, quando FROM chip_eventos WHERE instancia=? '
                                         'ORDER BY id DESC LIMIT 8', (inst,))]
        semana = (agora() - timedelta(days=7)).isoformat()
        conexoes = c.execute("SELECT COUNT(*) FROM chip_eventos WHERE instancia=? AND estado='open' AND quando>=?",
                             (inst, semana)).fetchone()[0]
    desde = ev[0]['quando'] if ev and ev[0]['estado'] == 'open' else ''
    return {'eventos': ev, 'conexoes_7d': conexoes, 'desde': desde}


def whatsapp_status(inst):
    st = estado_chip(inst, cache_seg=0)
    if st not in ('erro', 'inexistente'):
        registrar_estado(inst, st)
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
    res.update(historico_chip(inst))
    return res


def atualizar_grupos():
    """Busca os grupos de cada chip conectado e guarda em quais grupos cada chip está."""
    total = set()
    for inst in instancias():
        if estado_chip(inst, cache_seg=0) != 'open':
            continue
        dono = numero_do_chip(inst)
        try:
            lista = evo('GET', f"/group/fetchAllGroups/{inst}?getParticipants=true", timeout=240)
        except RuntimeError:
            lista = evo('GET', f"/group/fetchAllGroups/{inst}?getParticipants=false", timeout=120)
        with _lock, db() as c:
            c.execute('DELETE FROM grupo_chips WHERE instancia=?', (inst,))
            for g in lista:
                total.add(g['id'])
                adm = chip_e_admin(g.get('participants'), dono)
                c.execute('INSERT INTO grupos (jid, nome) VALUES (?,?) ON CONFLICT(jid) DO UPDATE SET nome=excluded.nome',
                          (g['id'], g.get('subject') or g['id']))
                c.execute('INSERT OR REPLACE INTO grupo_chips (jid, instancia, admin) VALUES (?,?,?)', (g['id'], inst, adm))
                n = len(g['participants']) if isinstance(g.get('participants'), list) else g.get('size')
                if n:                                # foto do tamanho do grupo no dia
                    c.execute('INSERT INTO membros (dia, jid, total) VALUES (?,?,?) ON CONFLICT(dia, jid) DO UPDATE SET total=excluded.total',
                              (agora().date().isoformat(), g['id'], int(n)))
    with _lock, db() as c:      # grupo é "seu" quando algum chip é admin nele
        c.execute('UPDATE grupos SET admin=(SELECT MAX(admin) FROM grupo_chips gc WHERE gc.jid=grupos.jid)')
    return len(total)


def numero_do_chip(inst):
    try:
        info = evo('GET', f'/instance/fetchInstances?instanceName={inst}')
        info = info[0] if isinstance(info, list) and info else {}
        return digitos((info.get('ownerJid') or '').split('@')[0])
    except RuntimeError:
        return ''


def chip_e_admin(participantes, dono):
    """1 = o chip é admin no grupo · 0 = não é · None = não deu para saber."""
    if participantes is None or not dono:
        return None
    for pt in participantes:
        ids = [pt.get('id'), pt.get('phoneNumber'), pt.get('jid'), pt.get('pn')]
        if any(len(digitos(x)) >= 8 and digitos(x)[-8:] == dono[-8:] for x in ids if x):
            return 1 if pt.get('admin') in ('admin', 'superadmin') or pt.get('isAdmin') else 0
    return 0


def enviar_texto(inst, jid, texto, previa=True):
    return evo('POST', f"/message/sendText/{inst}", {'number': jid, 'text': texto, 'linkPreview': previa}, timeout=60)


MIDIA_DIR = BASE / 'midia'


def enviar_item(inst, jid, item):
    dados = json.loads(item.get('dados') or '{}')
    if dados.get('enquete'):
        e = dados['enquete']
        res = evo('POST', f"/message/sendPoll/{inst}", {'number': jid, 'name': e['pergunta'],
                                                        'selectableCount': len(e['opcoes']), 'values': e['opcoes']}, timeout=60)
        mid = (res or {}).get('key', {}).get('id') if isinstance(res, dict) else None
        if mid:
            with _lock, db() as c:
                c.execute('INSERT OR REPLACE INTO enquetes VALUES (?,?,?,?,?)',
                          (mid, item.get('id'), jid, json.dumps(e['opcoes'], ensure_ascii=False), agora().isoformat()))
        return res
    midia = dados.get('midia')
    if midia and Path(midia).exists():
        return evo('POST', f"/message/sendMedia/{inst}", {
            'number': jid, 'mediatype': dados.get('midia_tipo', 'image'), 'mimetype': dados.get('mimetype', 'image/jpeg'),
            'caption': item['texto'] or '', 'media': Path(midia).read_text(), 'fileName': Path(midia).stem}, timeout=180)
    elif dados.get('imagem') and modo_link() != 'previa' and item.get('origem') != 'aviso':
        # Link direto: o WhatsApp não consegue montar a miniatura da Shopee → vai a foto do produto com o texto
        # na legenda (o link continua direto na loja). Se a foto falhar, vai só o texto.
        try:
            return evo('POST', f"/message/sendMedia/{inst}", {
                'number': jid, 'mediatype': 'image', 'mimetype': 'image/jpeg', 'caption': item['texto'] or '',
                'media': dados['imagem'], 'fileName': 'oferta.jpg'}, timeout=120)
        except RuntimeError as e:
            log.warning(f'Foto do produto não foi ({e}); mandando só o texto')
            return enviar_texto(inst, jid, item['texto'])
    else:
        return enviar_texto(inst, jid, item['texto'])


def ligar_previa(res, fid):
    """Guarda: esta mensagem enviada é do post #fid (responder em cima dela vale para ele)."""
    mid = (res or {}).get('key', {}).get('id') if isinstance(res, dict) else None
    if mid and fid:
        with _lock, db() as c:
            c.execute('INSERT OR REPLACE INTO previas VALUES (?,?,?)', (mid, fid, agora().isoformat()))


def mostrar_previa(inst, numero, fid):
    """Mostra para você exatamente como vai sair no grupo (com foto, se for o caso)."""
    try:
        ligar_previa(enviar_item(inst, numero, item_fila(fid)), fid)
    except Exception as e:
        log.warning(f'Prévia para {numero} falhou: {e}')


# ---------------------------------------------------------------- envio (fila aprovada)

def posts_hoje(c, jid):
    inicio = agora().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return c.execute('SELECT COUNT(*) FROM envios WHERE jid=? AND ok=1 AND quando>=?', (jid, inicio)).fetchone()[0]


def sortear_chip(jid, evitar=None):
    """Sorteia entre os chips conectados que estão no grupo; evita repetir o mesmo chip da postagem anterior."""
    with db() as c:
        rows = c.execute('SELECT instancia, admin FROM grupo_chips WHERE jid=?', (jid,)).fetchall()
        chips = [r[0] for r in rows if r[1] == 1] or [r[0] for r in rows]   # chips admin primeiro
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


RITMO_PADRAO = {
    'inicio': '08:00', 'fim': '22:00',      # rajadas só nesse horário (agendado com hora marcada sai na hora)
    'rajada': [1, 3],                       # posts por rajada (sorteado)
    'pausa': [40, 90],                      # minutos de pausa entre rajadas (sorteado)
    'entre_grupos': [120, 300],             # segundos entre um grupo e outro no mesmo post
    'aquec_inicio': 6, 'aquec_passo': 2, 'aquec_max': 20, 'aquec_desde': '',   # posts/dia por grupo: 6 → +2/dia → 20
    # nichos por horário: em cada faixa, as rajadas dão preferência a esses nichos
    'nichos_ativo': True, 'nicho_estrito': False,
    'nichos_horario': [     # baseado nas vendas reais (Ago25–Jul26): quando cada nicho vende mais
        {'de': '06:00', 'ate': '10:00', 'nichos': ['🏠 Casa e decoração', '🛋️ Móveis']},
        {'de': '10:00', 'ate': '12:00', 'nichos': ['👗 Moda', '💇 Beleza e cabelo']},
        {'de': '12:00', 'ate': '15:00', 'nichos': ['🔌 Eletrodomésticos', '🍳 Cozinha e utensílios', '🛋️ Móveis']},
        {'de': '15:00', 'ate': '18:00', 'nichos': ['🏠 Casa e decoração', '🔌 Eletrodomésticos', '👗 Moda']},
        {'de': '18:00', 'ate': '20:00', 'nichos': ['🧸 Infantil', '🐶 Pet', '👗 Moda']},
        {'de': '20:00', 'ate': '23:59', 'nichos': ['👗 Moda', '💇 Beleza e cabelo', '🏠 Casa e decoração', '🛋️ Móveis']},
    ],
}


def nichos_da_hora(r=None, quando=None):
    r = r or ritmo()
    if not r.get('nichos_ativo'):
        return []
    hm = (quando or agora()).strftime('%H:%M')
    for f in r.get('nichos_horario') or []:
        if f.get('de', '') <= hm < f.get('ate', ''):
            return f.get('nichos') or []
    return []


def focos_do_item(item):
    try:
        d = json.loads(item['dados'] or '{}') or {}
        return d['focos'] if 'focos' in d else classificar_focos(item['produto'])
    except (ValueError, KeyError, TypeError):
        return []


def nicho_do_item(item):
    try:
        return (json.loads(item['dados'] or '{}') or {}).get('nicho') or classificar_nicho(item['produto'])
    except (ValueError, KeyError, TypeError):
        return '📦 Outros'


def ritmo():
    r = dict(RITMO_PADRAO)
    r.update(get_json('ritmo', {}))
    if get_cfg('migr_focos') != '1':           # 1ª vez: põe os focos nas faixas de moda e de noite
        extra = {'10:00': ['➕ Plus Size', '✝️ Evangélica'], '15:00': ['🎄 Natal'], '18:00': ['🎄 Natal'],
                 '20:00': ['➕ Plus Size', '✝️ Evangélica', '🎄 Natal']}
        for f in r.get('nichos_horario') or []:
            for k, v in extra.items():
                if f.get('de', '') <= k < f.get('ate', ''):
                    f['nichos'] = list(dict.fromkeys((f.get('nichos') or []) + v))
        set_cfg('ritmo', json.dumps(r))
        set_cfg('migr_focos', '1')
    if get_cfg('migr_nichos_dados') != '1':        # 1ª vez: faixas novas, baseadas nas vendas reais
        r['nichos_horario'] = RITMO_PADRAO['nichos_horario']
        set_cfg('ritmo', json.dumps(r))
        d = get_json('divulgador', {})
        if d:
            d.update({'palavras': DIVULGADOR_PADRAO['palavras'], 'horarios': DIVULGADOR_PADRAO['horarios']})
            set_cfg('divulgador', json.dumps(d, ensure_ascii=False))
        set_cfg('migr_nichos_dados', '1')
    if not r.get('aquec_desde'):
        r['aquec_desde'] = agora().date().isoformat()
        set_cfg('ritmo', json.dumps(r))
    return r


def limite_hoje(r=None):
    """Aquecimento: começa devagar e sobe um pouco por dia até o máximo."""
    r = r or ritmo()
    try:
        dias = (agora().date() - date.fromisoformat(r['aquec_desde'])).days
    except ValueError:
        dias = 0
    return _com_trava(r, min(int(r['aquec_max']), int(r['aquec_inicio']) + int(r['aquec_passo']) * max(0, dias)))


def _com_trava(r, n):
    """🔒 Ritmo travado: não passa do teto escolhido, por mais que o aquecimento suba."""
    t = int(r.get('trava') or 0)
    return min(n, t) if t > 0 else n


def limite_em(dia, r=None):
    """Limite do aquecimento (posts por grupo) num dia passado ou futuro."""
    r = r or ritmo()
    try:
        dias = (dia - date.fromisoformat(r['aquec_desde'])).days
    except (ValueError, TypeError):
        return _com_trava(r, int(r['aquec_max']))
    return _com_trava(r, min(int(r['aquec_max']), int(r['aquec_inicio']) + int(r['aquec_passo']) * max(0, dias)))


def historico(periodo='7', mes=''):
    """📜 Posts enviados (por dia/horário/nicho) e 👥 quanto cada grupo recebeu por dia no mês."""
    hoje = agora().date()
    ini = {'hoje': hoje, '7': hoje - timedelta(days=6), 'mes': hoje.replace(day=1), '30': hoje - timedelta(days=29)}.get(periodo, hoje - timedelta(days=6))
    with db() as c:
        linhas = c.execute(
            "SELECT f.id, f.produto, f.origem, f.dados, f.link, MIN(e.quando) primeiro, COUNT(DISTINCT e.jid) grupos "
            "FROM envios e JOIN fila f ON f.id=e.fila_id WHERE e.ok=1 AND substr(e.quando,1,10)>=? "
            "GROUP BY f.id ORDER BY primeiro DESC", (ini.isoformat(),)).fetchall()
        posts = []
        for r in linhas:
            cod = (r['link'] or '').rsplit('/l/', 1)[-1] if '/l/' in (r['link'] or '') else ''
            item = {'dados': r['dados'], 'produto': r['produto']}
            posts.append({'id': r['id'], 'produto': r['produto'], 'quando': r['primeiro'], 'grupos': r['grupos'],
                          'nicho': '📢 Aviso' if r['origem'] == 'aviso' else nicho_do_item(item),
                          'focos': [] if r['origem'] == 'aviso' else focos_do_item(item),
                          'cliques': c.execute('SELECT COUNT(*) FROM cliques WHERE codigo=?', (cod,)).fetchone()[0] if cod else None,
                          'entrega': dict(c.execute("SELECT COALESCE(NULLIF(UPPER(wa_status),''),'?'), COUNT(*) FROM envios WHERE fila_id=? AND ok=1 "
                                                    "GROUP BY 1", (r['id'],)).fetchall()),
                          **dict(zip(('vendas', 'comissao'), c.execute(
                              "SELECT COUNT(*), COALESCE(SUM(comissao),0) FROM vendas WHERE fila_id=? AND status NOT IN ('CANCELLED','UNPAID')",
                              (r['id'],)).fetchone()))})
        # por grupo, no mês escolhido
        mes = mes if re.fullmatch(r'\d{4}-\d{2}', mes or '') else hoje.strftime('%Y-%m')
        cont = {}
        for jid, dia, n in c.execute("SELECT jid, substr(quando,1,10) d, COUNT(DISTINCT fila_id) FROM envios WHERE ok=1 "
                                     "AND substr(quando,1,7)=? GROUP BY jid, d", (mes,)):
            cont.setdefault(jid, {})[dia] = n
        nomes = {r[0]: r[1] for r in c.execute('SELECT jid, nome FROM grupos')}
        vend = {r[0]: (r[1], r[2]) for r in c.execute(
            "SELECT jid, COUNT(*), COALESCE(SUM(comissao),0) FROM vendas WHERE substr(quando,1,7)=? AND jid IS NOT NULL "
            "AND status NOT IN ('CANCELLED','UNPAID') GROUP BY jid", (mes,))}
        meses = [r[0] for r in c.execute("SELECT DISTINCT substr(quando,1,7) FROM envios WHERE ok=1 ORDER BY 1")]
        memb = {}
        for jid, ent, sai in c.execute("SELECT jid, SUM(entradas), SUM(saidas) FROM membros WHERE substr(dia,1,7)=? GROUP BY jid", (mes,)):
            memb[jid] = {'entradas': ent or 0, 'saidas': sai or 0}
        for jid, tot in c.execute("SELECT m.jid, m.total FROM membros m WHERE m.total IS NOT NULL AND m.dia=(SELECT MAX(dia) FROM membros "
                                  "WHERE jid=m.jid AND total IS NOT NULL)"):
            memb.setdefault(jid, {'entradas': 0, 'saidas': 0})['total'] = tot
        memb_dia = {}
        for jid, dia, ent, sai in c.execute("SELECT jid, dia, entradas, saidas FROM membros WHERE substr(dia,1,7)=?", (mes,)):
            memb_dia.setdefault(jid, {})[dia] = [ent or 0, sai or 0]
        por_dia = {r[0]: [r[1] or 0, r[2] or 0] for r in c.execute(
            "SELECT dia, SUM(entradas), SUM(saidas) FROM membros WHERE dia>=? GROUP BY dia", (ini.isoformat(),))}
    a, m = map(int, mes.split('-'))
    prox = date(a + (m == 12), m % 12 + 1, 1)
    dias = [(date(a, m, 1) + timedelta(days=i)) for i in range((prox - date(a, m, 1)).days)]
    r = ritmo()
    grupos = sorted([{'jid': j, 'nome': nomes.get(j, j), 'dias': d, 'total': sum(d.values()),
                      'vendas': vend.get(j, (0, 0))[0], 'comissao': round(vend.get(j, (0, 0))[1], 2),
                      'membros': memb.get(j, {}), 'membros_dia': memb_dia.get(j, {})} for j, d in cont.items()],
                    key=lambda g: -g['total'])
    return {'posts': posts, 'inicio': ini.isoformat(), 'mes': mes, 'meses': sorted(set(meses + [hoje.strftime('%Y-%m')])),
            'dias': [d.isoformat() for d in dias], 'limites': {d.isoformat(): limite_em(d, r) for d in dias}, 'grupos': grupos,
            'vendas_atualizado': get_cfg('vendas_atualizado'), 'membros_por_dia': por_dia}


def no_horario(r, quando=None):
    h = (quando or agora()).strftime('%H:%M')
    return r['inicio'] <= h < r['fim']


def proxima_saida():
    """Quando sai o próximo post da fila (para avisar você)."""
    r = ritmo()
    prox = get_cfg('proxima_rajada')
    t = max(agora(), datetime.fromisoformat(prox)) if prox else agora()
    if not no_horario(r, t):
        ini = datetime.strptime(r['inicio'], '%H:%M').time()
        t = t.replace(hour=ini.hour, minute=ini.minute, second=0, microsecond=0)
        if t <= agora():
            t += timedelta(days=1)
    return t


def proximos_itens():
    """Agendado com hora marcada sai sozinho na hora. Fora isso, uma RAJADA: sorteia quantos posts (ex.: 1–3),
    pega os primeiros da fila (preferindo o nicho da hora) e marca a pausa até a próxima rajada."""
    r = ritmo()
    agora_iso = agora().isoformat()
    with db() as c:
        item = c.execute("SELECT * FROM fila WHERE status='aprovado' AND agendado_para!='' AND agendado_para IS NOT NULL "
                         "AND agendado_para<=? ORDER BY agendado_para LIMIT 1", (agora_iso,)).fetchone()
    if item:
        return [item]
    if not no_horario(r):
        return []
    prox = get_cfg('proxima_rajada')
    if prox and prox > agora_iso:
        return []
    with db() as c:
        candidatos = c.execute("SELECT * FROM fila WHERE status='aprovado' AND (agendado_para IS NULL OR agendado_para='') "
                               "ORDER BY aprovado_em").fetchall()
    da_hora = nichos_da_hora(r)
    if da_hora:                     # rajada do nicho da hora; completa com outros (a não ser que seja estrito)
        do_nicho = [x for x in candidatos if x['origem'] == 'aviso' or nicho_do_item(x) in da_hora
                    or set(focos_do_item(x)) & set(da_hora)]          # avisos/engajamento saem em qualquer faixa
        resto = [x for x in candidatos if x not in do_nicho]
        candidatos = do_nicho + ([] if r.get('nicho_estrito') else resto)
    if not candidatos:
        return []
    n = random.randint(*sorted(r['rajada']))
    set_cfg('proxima_rajada', (agora() + timedelta(minutes=random.randint(*r['pausa']))).isoformat())
    return candidatos[:n]


def _link_do_grupo(item, jid):
    envio = dict(item)
    with db() as c:
        gid = c.execute('SELECT rowid FROM grupos WHERE jid=?', (jid,)).fetchone()
    if gid and item['link'] and item['link'] in (item['texto'] or ''):
        if '/l/' in item['link']:                   # página do PostZap: marca do grupo → cliques por grupo
            envio['texto'] = item['texto'].replace(item['link'], f"{item['link']}?g={gid[0]}")
        elif 'shopee' in item['link']:              # link direto: um link de afiliado por grupo → vendas por grupo
            try:
                novo = link_shopee_do_grupo(item, gid[0])
                if novo:
                    envio['texto'] = item['texto'].replace(item['link'], novo)
            except Exception as e:
                log.warning(f'Link por grupo falhou ({e}); vai o link geral')
    return envio


def processar_fila():
    """Envia a rajada GRUPO A GRUPO: em cada grupo saem todos os posts da rajada em sequência (segundos entre eles),
    depois espera o intervalo entre grupos e vai para o próximo."""
    if get_cfg('pausado') == '1':
        return
    itens = [dict(x) for x in proximos_itens()]
    if not itens:
        return
    r = ritmo()
    limite = limite_hoje(r)
    fila = grupos_fila()
    with _lock, db() as c:
        for it in itens:
            c.execute("UPDATE fila SET status='enviando' WHERE id=?", (it['id'],))
    for it in itens:
        it['_grupos'] = [g for g in (json.loads(it['grupos'] or '[]') or grupos_ativos()) if g not in fila]
        it['_erros'], it['_usados'] = [], {}
        if not it['_grupos']:
            it['_erros'].append('Nenhum grupo: marque grupos em 👥 Grupos ou use 📋 Definir grupos e aprove de novo.')
    todos = list(dict.fromkeys(g for it in itens for g in it['_grupos']))
    random.shuffle(todos)                      # ordem dos grupos também muda a cada rajada
    entre_posts = r.get('entre_posts') or [15, 45]
    anterior = None
    for gi, jid in enumerate(todos):
        if get_cfg('pausado') == '1':
            for it in itens:
                it['_erros'].append('pausado no meio do envio')
            break
        with db() as c:
            nome = (c.execute('SELECT nome FROM grupos WHERE jid=?', (jid,)).fetchone() or [jid])[0]
        inst = sortear_chip(jid, anterior)     # o mesmo chip manda a rajada inteira neste grupo
        enviou = False
        for it in [x for x in itens if jid in x['_grupos']]:
            with db() as c:
                if c.execute('SELECT 1 FROM envios WHERE fila_id=? AND jid=? AND ok=1', (it['id'], jid)).fetchone():
                    continue
                if posts_hoje(c, jid) >= limite:
                    it['_erros'].append(f'{nome}: limite de hoje ({limite} posts/grupo, aquecimento) atingido')
                    continue
            if enviou:
                time.sleep(random.randint(*sorted(entre_posts)))
            envio = _link_do_grupo(it, jid)
            sc = status_cfg()
            inst_it = inst
            if json.loads(it.get('dados') or '{}').get('so_status'):   # "salve este número": sai por um chip que posta Status
                with db() as c:
                    alt = [r[0] for r in c.execute('SELECT instancia FROM grupo_chips WHERE jid=?', (jid,))
                           if r[0] in (sc.get('chips') or []) and estado_chip(r[0]) == 'open']
                if alt and inst not in alt:
                    inst_it = random.choice(alt)
            if (sc.get('ativo') and sc.get('lembrete_ativo') and it['origem'] != 'aviso' and inst
                    and inst in (sc.get('chips') or []) and not json.loads(it.get('dados') or '{}').get('enquete')):
                with db() as c:
                    n = c.execute('SELECT COUNT(*) FROM envios WHERE jid=? AND ok=1', (jid,)).fetchone()[0]
                if (n + 1) % max(1, int(sc.get('lembrete_cada') or 5)) == 0:   # 1 a cada N posts neste grupo
                    envio['texto'] = (envio['texto'] or '').rstrip() + '\n\n' + sc['lembrete_texto']
            ok, erro, msg_id, wa = 1, None, None, ''
            if not inst_it:
                ok, erro = 0, 'nenhum chip conectado está neste grupo'
            else:
                try:
                    res = enviar_item(inst_it, jid, envio)
                    msg_id = (res or {}).get('key', {}).get('id') if isinstance(res, dict) else None
                    wa = str((res or {}).get('status') or '') if isinstance(res, dict) else ''
                    it['_usados'][inst_it] = it['_usados'].get(inst_it, 0) + 1
                    anterior, enviou = inst, True
                    log.info(f"Fila {it['id']} → {nome} pelo chip {inst}")
                except Exception as e:
                    ok, erro = 0, str(e)[:300]
            if not ok:
                it['_erros'].append(f'{nome}: {erro}')
            with _lock, db() as c:
                c.execute('INSERT INTO envios (fila_id, jid, chave, quando, ok, erro, instancia, msg_id, wa_status) VALUES (?,?,?,?,?,?,?,?,?)',
                          (it['id'], jid, it['chave'], agora().isoformat(), ok, erro, inst_it, msg_id, wa))
        if enviou and gi < len(todos) - 1:
            time.sleep(random.randint(*r['entre_grupos']))
    for it in itens:
        erros, usados = it['_erros'], it['_usados']
        with _lock, db() as c:
            status = 'erro' if not usados and erros else 'enviado'
            c.execute('UPDATE fila SET status=?, enviado_em=?, erro=? WHERE id=?',
                      (status, agora().isoformat(), '\n'.join(erros) or None, it['id']))
        if usados and status_cfg().get('ativo'):
            try:
                postar_status(it)
            except Exception as e:
                log.warning(f'Status: {e}')
        if it['pedido_por']:
            resumo = ', '.join(f'{k}: {v}' for k, v in usados.items()) or 'nenhum'
            aviso = (f"✅ Postado: *{it['produto'][:60]}*\n{sum(usados.values())} grupo(s) · chips usados → {resumo}"
                     + (f"\n⚠️ {chr(10).join(erros)}" if erros else ''))
            responder(it['pedido_inst'], it['pedido_por'], aviso)


# ---------------------------------------------------------------- chamada automática (IA)

def chave_env(nome):
    """Chave do .env do PostZap; se não tiver, do .env do robô do Shopee Vídeo."""
    k = os.getenv(nome, '')
    if not k and Path(CFG['central_env']).exists():
        for line in Path(CFG['central_env']).read_text(encoding='utf-8').splitlines():
            a, _, v = line.partition('=')
            if a.strip() == nome:
                k = v.strip().strip('"\'')
    return k


def chave_openai():
    return chave_env('OPENAI_API_KEY')


def gerar_chamada(produto, loja=''):
    """Chamada curta em MAIÚSCULAS. Modo (app ✏️ Mensagens): ia | frases (as suas, por loja) | misto."""
    modo = get_cfg('chamada_modo', 'ia')
    frases_loja = get_json('chamadas', {})
    frases = [f for f in (frases_loja.get(loja) or frases_loja.get('Todas') or []) if f.strip()]
    if frases and (modo == 'frases' or (modo == 'misto' and random.random() < 0.5)):
        return random.choice(frases).strip()
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
    return random.choice(frases).strip() if frases else 'OFERTA IMPERDÍVEL! 🔥'


# ---------------------------------------------------------------- conversa no WhatsApp (mandar links)

def menu():
    nomes = ', '.join(l['nome'] for l in listas())
    estilos = ', '.join(modelos())
    return ("Responda com:\n*1* ✅ aprovar e postar agora" + (f"  (só numa lista: *1 {listas()[0]['nome'].lower()}* · listas: {nomes})" if nomes else '')
            + "\n*2* ✏️ trocar a chamada\n*3* 💸 colocar o preço \"De:\"\n*4* 💰 trocar o preço \"Por:\"\n"
            "*5* 🕒 agendar (ex.: *5 20h* ou *5 20:30*)\n*6* 🎟️ cupom (ex.: *6 PROMO10* · *6 0* tira)\n"
            f"*7* 🎨 estilo ({estilos}) ex.: *7 relâmpago*\n*0* 🗑️ descartar")


MENU_AVISO = "Responda com:\n*1* ✅ enviar agora (ou *1 nome-da-lista*)\n*5* 🕒 agendar (ex.: *5 20h*)\n*0* 🗑️ descartar"


def montar_texto(p):
    """Texto final pelo estilo escolhido. Linha com campos {..} todos vazios some (ex.: sem "De:", sem cupom)."""
    p = dict(p)
    if '{link_pedido}' in ''.join(modelos().values()) and eng_cfg().get('inbox_ativo'):
        p.setdefault('link_pedido', link_pedido())
    p['chamada'] = re.sub(r'\s+', ' ', str(p.get('chamada') or '').replace('*', '')).strip()   # o estilo já põe o negrito
    de, por = num(p.get('preco_de')), num(p.get('preco'))
    p['desconto'] = f"{round((1 - por / de) * 100)}% OFF" if de > por > 0 else ''
    m = modelos()
    tpl = m.get(p.get('estilo') or '') or m.get('Padrão') or MODELO_PADRAO
    saida = []
    for linha in tpl.split('\n'):
        campos = re.findall(r'\{(\w+)\}', linha)
        if campos and not any(str(p.get(k) or '').strip() for k in campos):
            continue
        saida.append(re.sub(r'\{(\w+)\}', lambda x: str(p.get(x.group(1)) or ''), linha).rstrip())
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(saida)).strip()


def listas():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM listas ORDER BY nome')]


def achar_lista(nome):
    n = (nome or '').strip().lower()
    for l in listas():
        if l['nome'].lower() == n or l['nome'].lower().startswith(n):
            return l
    return None


def digitos(x):
    return re.sub(r'\D', '', x or '')


def autorizado(numeros):
    for n in numeros:
        d = digitos(n)
        if len(d) >= 8 and any(a[-8:] == d[-8:] for a in CFG['autorizados']):
            return True
    return False


def responder(inst, para, texto, previa=False, fid=None):
    try:
        res = enviar_texto(inst, para, texto, previa)
        ligar_previa(res, fid)
        return res
    except Exception as e:
        log.warning(f'Resposta para {para} falhou: {e}')


def grupos_ativos():
    fila = grupos_fila()
    with db() as c:
        return [r[0] for r in c.execute('SELECT jid FROM grupos WHERE ativo=1') if r[0] not in fila]


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


def registrar_membros(inst, data):
    """Conta entradas e saídas por grupo por dia. Vários chips no mesmo grupo recebem o mesmo aviso: só um conta."""
    jid = data.get('id') or data.get('groupJid') or ''
    acao = str(data.get('action') or '').lower()
    pessoas = data.get('participants') or []
    if not jid.endswith('@g.us') or acao not in ('add', 'remove') or not pessoas:
        return
    with _lock, db() as c:
        chips = [r[0] for r in c.execute('SELECT instancia FROM grupo_chips WHERE jid=? ORDER BY instancia', (jid,))]
        abertos = [x for x in chips if estado_chip(x) == 'open']
        if abertos and inst != abertos[0]:
            return
        col = 'entradas' if acao == 'add' else 'saidas'
        dia = agora().date().isoformat()
        c.execute(f'INSERT INTO membros (dia, jid, {col}) VALUES (?,?,?) ON CONFLICT(dia, jid) DO UPDATE SET {col}={col}+?',
                  (dia, jid, len(pessoas), len(pessoas)))
        ult = c.execute('SELECT total FROM membros WHERE jid=? AND total IS NOT NULL ORDER BY dia DESC LIMIT 1', (jid,)).fetchone()
        if ult and ult[0]:
            c.execute('UPDATE membros SET total=? WHERE dia=? AND jid=?',
                      (max(0, ult[0] + (len(pessoas) if acao == 'add' else -len(pessoas))), dia, jid))


def receber_webhook(payload):
    evento = (payload.get('event') or '').lower().replace('_', '.')
    inst = payload.get('instance') or ''
    data = payload.get('data') or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    if evento == 'group.participants.update':   # alguém entrou/saiu de um grupo
        registrar_membros(inst, data)
        return
    if evento == 'messages.update':             # confirmação do WhatsApp: entregue / lido / erro
        mid = data.get('keyId') or (data.get('key') or {}).get('id') or data.get('messageId')
        st = str(data.get('status') or '').upper()
        if mid and st:
            ordem = {'ERROR': 9, 'PENDING': 1, 'SERVER_ACK': 2, 'DELIVERY_ACK': 3, 'READ': 4, 'PLAYED': 4}
            with _lock, db() as c:
                atual = (c.execute('SELECT wa_status FROM envios WHERE msg_id=?', (mid,)).fetchone() or [None])[0]
                if atual is not None and (st == 'ERROR' or ordem.get(st, 0) > ordem.get(str(atual).upper(), 0)):
                    c.execute('UPDATE envios SET wa_status=? WHERE msg_id=?', (st, mid))
    if registrar_voto(data):                     # voto em enquete (chega como update ou upsert, conforme a versão)
        return
    if evento != 'messages.upsert':
        return
    key = data.get('key') or {}
    jid = key.get('remoteJid') or ''
    if key.get('fromMe') and jid and not jid.endswith('@g.us') and not jid.endswith('@broadcast'):
        mid = key.get('id')
        if mid and mid not in _vistos:          # não foi o PostZap que mandou: é você conversando com a pessoa
            set_cfg(f'humano_{inst}_{digitos(jid)[-11:]}', str(time.time()))
        return
    if key.get('fromMe') or jid.endswith('@broadcast'):
        return
    msg0 = data.get('message') or {}
    texto0 = (msg0.get('conversation') or (msg0.get('extendedTextMessage') or {}).get('text')
              or (msg0.get('imageMessage') or {}).get('caption') or '').strip()
    if jid.endswith('@g.us') and jid in grupos_monitorados() and texto0:     # grupo de ofertas monitorado
        if key.get('id') and _marcar_visto(key['id']):
            return
        midia0 = {'key': key, 'inst': inst} if msg0.get('imageMessage') else None
        threading.Thread(target=processar_achado, args=(texto0, f'grupo {nome_grupo(jid)}', midia0), daemon=True).start()
        return
    if jid.endswith('@g.us'):                    # grupo: só o "FILA POST ZAP" vira lugar de comandos
        if jid not in grupos_fila():
            nome = ''
            try:
                nome = (evo('GET', f'/group/findGroupInfos/{inst}?groupJid={jid}') or {}).get('subject', '')
            except RuntimeError:
                pass
            if not e_grupo_fila(nome):
                return
            with _lock, db() as c:
                c.execute('INSERT INTO grupos (jid, nome, ativo) VALUES (?,?,0) ON CONFLICT(jid) DO UPDATE SET nome=excluded.nome',
                          (jid, nome))
        quem = [key.get('participant'), key.get('participantAlt'), key.get('participantPn'), data.get('participant')]
    else:
        quem = [jid, key.get('remoteJidAlt'), key.get('senderPn'), data.get('sender')]
    if not autorizado([x for x in quem if x]):
        if not jid.endswith('@g.us') and texto0 and inbox_deve_responder(inst, jid, texto0) and not (key.get('id') and _marcar_visto(key['id'])):
            threading.Thread(target=pedido_inbox, args=(inst, jid, texto0), daemon=True).start()   # alguém pedindo produto
        return
    if key.get('id') and _marcar_visto(key['id']):   # já tratada por outro chip, ou é resposta do próprio PostZap
        return
    msg = data.get('message') or {}
    midia = 'image' if msg.get('imageMessage') else 'video' if msg.get('videoMessage') else None
    texto = (msg.get('conversation') or (msg.get('extendedTextMessage') or {}).get('text')
             or (msg.get('imageMessage') or {}).get('caption') or (msg.get('videoMessage') or {}).get('caption') or '').strip()
    if texto:
        info = {'tipo': midia, 'key': key, 'mimetype': (msg.get(f'{midia}Message') or {}).get('mimetype')} if midia else None
        ctx = ((msg.get('extendedTextMessage') or {}).get('contextInfo') or (msg.get('imageMessage') or {}).get('contextInfo')
               or data.get('contextInfo') or {})
        citado = ctx.get('stanzaId') or ''         # respondeu em cima de qual mensagem
        threading.Thread(target=tratar_mensagem, args=(inst, jid, texto, info, citado), daemon=True).start()


_filas_conversa = {}


def tratar_mensagem(inst, numero, texto, midia=None, citado=''):
    lk = _filas_conversa.setdefault(numero, threading.Lock())   # um de cada vez por conversa (vários links seguidos)
    with lk:
        try:
            if re.match(r'/todos\b', texto, re.I):
                return novo_aviso(inst, numero, re.sub(r'^/todos\s*', '', texto, flags=re.I), midia)
            _tratar(inst, numero, texto, citado)
        except Exception as e:
            log.exception('Conversa')
            responder(inst, numero, f'⚠️ Deu erro: {str(e)[:150]}')


def novo_aviso(inst, numero, texto, midia=None):
    """/todos + texto (ou foto/vídeo com /todos na legenda): vai igualzinho para os grupos, depois da aprovação."""
    dados = {}
    if midia:
        r = evo('POST', f'/chat/getBase64FromMediaMessage/{inst}', {'message': {'key': midia['key']}, 'convertToMp4': False},
                timeout=120)
        b64 = r.get('base64') or ''
        if not b64:
            return responder(inst, numero, '⚠️ Não consegui baixar a foto/vídeo. Tente mandar de novo.')
        MIDIA_DIR.mkdir(exist_ok=True)
        arq = MIDIA_DIR / f"{int(time.time() * 1000)}.b64"
        arq.write_text(b64)
        dados = {'midia': str(arq), 'midia_tipo': midia['tipo'], 'mimetype': r.get('mimetype') or midia.get('mimetype')}
    if not texto and not dados:
        return responder(inst, numero, '📢 Mande assim: */todos* seu recado (pode ser legenda de foto ou vídeo).')
    grupos = grupos_ativos()
    with _lock, db() as c:
        cur = c.execute('INSERT INTO fila (origem, chave, produto, texto, grupos, criado_em, dados, pedido_por, pedido_inst) '
                        'VALUES (?,?,?,?,?,?,?,?,?)', ('aviso', '', '📢 ' + (texto.splitlines()[0][:50] if texto else 'Aviso com mídia'),
                                                       texto, json.dumps(grupos), agora().isoformat(), json.dumps(dados), numero, inst))
        fid = cur.lastrowid
    conversa_set(numero, fid)
    tipo = {'image': ' + 📷 foto', 'video': ' + 🎬 vídeo'}.get(dados.get('midia_tipo'), '')
    responder(inst, numero, f"📢 *Aviso #{fid} pronto*{tipo}\n\n{texto}\n\n👆 Vai para {len(grupos)} grupo(s).\n\n{MENU_AVISO}", fid=fid)


def montar_post_do_link(url):
    """Link (Shopee ou outra loja) → dados do produto prontos (foto, preço, seu link de afiliado, chamada)."""
    ids = None
    if 'shopee' in url or 'shp.ee' in url:
        ids = ids_do_link_shopee(url)
        if not ids:
            raise ValueError('Não consegui descobrir qual é o produto desse link da Shopee. '
                             'Tente o link copiado de dentro do produto (Compartilhar → Copiar link).')
    if ids:
        p = {'origem': 'whatsapp', 'chave': ids, 'link': url if 's.shopee' in url else '', 'produto': ''}
        nodes = []
        try:
            a, b = ids.split(':')
            nodes = shopee_gql(f'{{productOfferV2(shopId:{a},itemId:{b},limit:1){{nodes{{productName}}}}}}')['productOfferV2']['nodes']
        except Exception:
            pass
        p['produto'] = nodes[0]['productName'] if nodes else ''
        if not nodes:
            p['avisos'] = ['A Shopee não devolveu os dados desse produto agora. Responda *2* (chamada) e *4* (preço).']
    else:
        p = ler_link(url)
        p['origem'] = 'whatsapp'
    p = preparar(p)
    if bloqueado(p.get('produto')):
        raise ValueError('🚫 Produto de suplementação: não posto esse tipo de produto.')
    if not p.get('produto'):
        p['produto'] = 'Oferta'
        p['avisos'] = [a for a in p['avisos'] if 'nome do produto' not in a] + [
            'Não consegui ler o nome do produto: responda *2* para escrever a chamada.']
    if not p.get('chamada'):
        p['chamada'] = gerar_chamada(p['produto'], p.get('loja', ''))
    p['produto'] = p['produto'][:120]
    return p


MENU_CURTO = ("↩️ *Responda em cima desta mensagem* (ou da foto) com: *1* postar · *1 vip* · *2* chamada · *3* De · "
              "*4* Por · *5 20h* · *6* cupom · *7* estilo · *8* nicho · *0* descartar\n"
              "Para liberar tudo de uma vez: *aprovar todos* (ou *aprovar todos vip*)")


def item_alvo(numero, texto, citado, conv):
    """Qual post o comando quer mexer: o da mensagem respondida (citado) → '#12 …' → o último montado."""
    if citado:
        with db() as c:
            r = c.execute('SELECT fila_id FROM previas WHERE msg_id=?', (citado,)).fetchone()
        if r:
            return item_fila(r[0]), texto
    m = re.match(r'#(\d{1,6})\s+(.+)$', texto.strip())
    if m:                                         # "#12 1" = comando 1 no post #12 (sem # é sempre comando)
        it = item_fila(int(m.group(1)))
        if it and it.get('pedido_por') == numero:
            return it, m.group(2)
    return (item_fila(conv['fila_id']) if conv['fila_id'] else None), texto


def destinos_do_item(item, lista=None):
    """Grupos para onde o post vai: a lista escolhida → os do próprio post → os marcados agora em 👥 Grupos."""
    fila = grupos_fila()
    if lista:
        gs = json.loads(lista['grupos'] or '[]')
    else:
        gs = json.loads(item['grupos'] or '[]') or grupos_ativos()
    return [g for g in gs if g not in fila]


def aprovar_itens(itens, lista=None):
    """Aprova vários posts de uma vez (mantém agendamentos). Devolve (aprovados, sem_grupo)."""
    ok, sem = [], []
    for it in itens:
        gs = destinos_do_item(it, lista)
        if not gs:
            sem.append(it['id'])
            continue
        with _lock, db() as c:
            c.execute("UPDATE fila SET status='aprovado', aprovado_em=?, erro=NULL, grupos=? WHERE id=? "
                      "AND status IN ('rascunho','erro')", (agora().isoformat(), json.dumps(gs), it['id']))
        ok.append(it['id'])
    return ok, sem


def pendentes(numero):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id, produto FROM fila WHERE pedido_por=? AND status IN ('rascunho','erro') "
                                           "ORDER BY id", (numero,))]


def _tratar(inst, numero, texto, citado=''):
    conv = conversa_get(numero)
    links = [u.rstrip('.,)') for u in re.findall(r'https?://\S+', texto)]
    if links:                                         # 1 ou vários links = 1 post para cada, montados em sequência
        if len(links) > 1:
            responder(inst, numero, f'⏳ Recebi {len(links)} links. Vou montar um por um — cada post chega com o número dele.')
        else:
            responder(inst, numero, '⏳ Montando a postagem…')
        for url in links:
            try:
                p = montar_post_do_link(url)
            except ValueError as e:
                responder(inst, numero, f'⚠️ {url[:60]}\n{e}')
                continue
            grupos = grupos_ativos()
            with _lock, db() as c:
                cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, comissao, link, texto, grupos, criado_em, '
                                'dados, pedido_por, pedido_inst) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                                ('whatsapp', p.get('chave'), p['produto'], p.get('preco'), p.get('comissao', ''), p['link'],
                                 montar_texto(p), json.dumps(grupos), agora().isoformat(), json.dumps(p), numero, inst))
                fid = cur.lastrowid
            conversa_set(numero, fid)
            mostrar_previa(inst, numero, fid)
            extra = ('\n⚠️ ' + '\n⚠️ '.join(p['avisos'])) if p.get('avisos') else ''
            sem_preco = '' if p.get('preco') else '\n⚠️ Sem preço: responda *4 99,90*.'
            responder(inst, numero, f"📌 *Post #{fid} pronto* · {' · '.join([p.get('nicho', '')] + p.get('focos', []))} · {p['produto'][:45]} · vai para {len(grupos)} grupo(s)"
                                    f"{extra}{sem_preco}\n\n{MENU_CURTO}", fid=fid)
        n = len(pendentes(numero))
        if len(links) > 1 and n:
            responder(inst, numero, f'✅ Terminei. {n} post(s) esperando sua resposta. Mande *pendentes* para ver a lista.')
        return

    t = texto.strip()
    m_todos = re.match(r'(?:aprovar|aprova|postar) tod[oa]s(?:\s+(.+))?$', t.strip(), re.I)
    if m_todos:
        lista = achar_lista(m_todos.group(1)) if m_todos.group(1) else None
        if m_todos.group(1) and not lista:
            return responder(inst, numero, f'⚠️ Não achei a lista "{m_todos.group(1)}".')
        itens = [item_fila(x['id']) for x in pendentes(numero)]
        if not itens:
            return responder(inst, numero, '📭 Nenhum post esperando aprovação.')
        ok, sem = aprovar_itens(itens, lista)
        conversa_set(numero, None)
        prev = proxima_saida()
        return responder(inst, numero, (f"✅ {len(ok)} post(s) aprovados ({', '.join('#' + str(i) for i in ok)})"
                                        f"{' para a lista ' + lista['nome'] if lista else ''}. Saem nas rajadas a partir de "
                                        f"{data_tela(prev.isoformat(), True)}." if ok else '')
                                       + (f"\n⚠️ Sem grupo (marque grupos em 👥 Grupos): {', '.join('#' + str(i) for i in sem)}" if sem else ''))
    if t.lower() in ('pendentes', 'fila', 'lista'):
        ps = pendentes(numero)
        return responder(inst, numero, ('📋 *Esperando sua resposta:*\n' + '\n'.join(f"#{x['id']} · {x['produto'][:50]}" for x in ps)
                                        + '\n\nResponda em cima da prévia, ou mande *#número comando* (ex.: *#' + str(ps[0]['id'])
                                        + ' 1*).') if ps else '📭 Nenhum post esperando resposta.')
    item, t = item_alvo(numero, t, citado, conv)
    if item and item['status'] == 'aprovado' and t.strip() == '0':        # cancelar um aprovado que ainda não saiu
        with _lock, db() as c:
            c.execute("UPDATE fila SET status='descartado' WHERE id=? AND status='aprovado'", (item['id'],))
        return responder(inst, numero, f"🗑️ Post #{item['id']} cancelado (não vai sair).")
    if not item or item['status'] not in ('rascunho', 'erro'):
        if item and item['status'] in ('aprovado', 'enviando', 'enviado'):
            return responder(inst, numero, f"ℹ️ O post #{item['id']} já foi aprovado ({item['status']}).")
        return responder(inst, numero, '📲 Me mande o link de um produto (Shopee, Magalu, Mercado Livre, Amazon…) '
                                       '— pode mandar vários de uma vez — que eu monto as postagens.')
    fid = item['id']
    esperando = conv['esperando'] if conv['fila_id'] == fid else ''
    if esperando and not re.match(r'^[0-7](\s|$)', t):
        conversa_set(numero, fid)
        campo = {'chamada': 'chamada', 'de': 'preco_de', 'por': 'preco'}[esperando]
        regravar(item, **{campo: t.upper() if campo == 'chamada' else br(t)})
        mostrar_previa(inst, numero, fid)
        return responder(inst, numero, f'👆 Post #{fid} atualizado.\n\n{MENU_CURTO}', fid=fid)
    cmd, _, resto = t.partition(' ')
    if item['origem'] == 'aviso' and cmd not in ('1', '5', '0'):
        return responder(inst, numero, MENU_AVISO, fid=fid)
    if cmd == '1' and resto.strip():
        lista = achar_lista(resto)
        if not lista:
            nomes = ', '.join(l['nome'] for l in listas()) or 'nenhuma (crie no app, 👥 Grupos)'
            return responder(inst, numero, f'⚠️ Não achei a lista "{resto}". Listas: {nomes}', fid=fid)
        with _lock, db() as c:
            c.execute('UPDATE fila SET grupos=? WHERE id=?', (lista['grupos'], fid))
        item = item_fila(fid)
    if cmd == '1':
        grupos = destinos_do_item(item)
        if grupos and not json.loads(item['grupos'] or '[]'):
            with _lock, db() as c:
                c.execute('UPDATE fila SET grupos=? WHERE id=?', (json.dumps(grupos), fid))
        if not grupos:
            return responder(inst, numero, '⚠️ Nenhum grupo marcado. Marque os grupos no app (👥 Grupos).', fid=fid)
        with _lock, db() as c:
            c.execute("UPDATE fila SET status='aprovado', aprovado_em=?, erro=NULL WHERE id=?", (agora().isoformat(), fid))
        conversa_set(numero, None)
        quando = item['agendado_para']
        with db() as c:
            na_frente = c.execute("SELECT COUNT(*) FROM fila WHERE status IN ('aprovado','enviando') AND id!=? AND "
                                  "(agendado_para IS NULL OR agendado_para='')", (fid,)).fetchone()[0]
        prev = proxima_saida()
        nicho = nicho_do_item(item)
        faixa = next((f"{f['de']}–{f['ate']}" for f in (ritmo().get('nichos_horario') or []) if nicho in f.get('nichos', [])), '')
        quando_txt = (f"sai em {data_tela(quando, True)}" if quando else
                      f"entrou na fila ({na_frente} na frente) · próxima rajada a partir de {data_tela(prev.isoformat(), True)}"
                      + (f" · {nicho} sai de preferência das {faixa}" if faixa and ritmo().get('nichos_ativo') else ''))
        return responder(inst, numero, f"✅ Post #{fid} aprovado! {quando_txt} · {len(grupos)} grupo(s). Aviso quando sair.")
    if cmd in ('2', '3', '4'):
        esp = {'2': 'chamada', '3': 'de', '4': 'por'}[cmd]
        conversa_set(numero, fid, esp)
        if resto.strip():
            return _tratar(inst, numero, resto)
        return responder(inst, numero, {'chamada': f'✏️ Post #{fid}: mande a nova chamada:',
                                        'de': f'💸 Post #{fid}: mande o preço "De:" (ex.: 149,90):',
                                        'por': f'💰 Post #{fid}: mande o preço "Por:" (ex.: 99,90):'}[esp], fid=fid)
    if cmd == '5':
        m = re.match(r'(\d{1,2})(?:[:h](\d{2}))?h?$', resto.strip().lower())
        if not m:
            return responder(inst, numero, '🕒 Mande assim: *5 20h* ou *5 20:30*', fid=fid)
        quando = agora().replace(hour=int(m.group(1)), minute=int(m.group(2) or 0), second=0, microsecond=0)
        if quando < agora():
            quando += timedelta(days=1)
        with _lock, db() as c:
            c.execute("UPDATE fila SET agendado_para=?, status='aprovado', aprovado_em=? WHERE id=?",
                      (quando.isoformat(), agora().isoformat(), fid))
        conversa_set(numero, None)
        return responder(inst, numero, f"🕒 Post #{fid} agendado para {data_sub(quando)} às {quando:%H:%M}. Aviso quando postar.")
    if cmd == '6':
        cod = resto.strip()
        regravar(item, cupom='' if cod in ('', '0') else cod.upper(), cupom_texto='')
        mostrar_previa(inst, numero, fid)
        return responder(inst, numero, f"👆 Post #{fid}: {'cupom removido' if cod in ('', '0') else 'cupom colocado'}.\n\n{MENU_CURTO}", fid=fid)
    if cmd == '7':
        nomes = list(modelos())
        alvo = next((n for n in nomes if n.lower().startswith(resto.strip().lower()) and resto.strip()), None)
        if not alvo:
            return responder(inst, numero, f"🎨 Estilos: {', '.join(nomes)}. Ex.: *7 {nomes[-1].lower()}*", fid=fid)
        regravar(item, estilo=alvo)
        mostrar_previa(inst, numero, fid)
        return responder(inst, numero, f'👆 Post #{fid}: estilo "{alvo}".\n\n{MENU_CURTO}', fid=fid)
    if cmd == '8':
        alvo = next((n for n in NICHOS if resto.strip() and normalizar(resto) in normalizar(n)), None)
        if not alvo:
            return responder(inst, numero, '🗂️ Nichos: ' + ', '.join(NICHOS) + '. Ex.: *8 cozinha*', fid=fid)
        regravar(item, nicho=alvo)
        return responder(inst, numero, f'🗂️ Post #{fid} agora é do nicho {alvo}.', fid=fid)
    if cmd == '0':
        with _lock, db() as c:
            ja_foi = c.execute('SELECT COUNT(*) FROM envios WHERE fila_id=? AND ok=1', (fid,)).fetchone()[0]
            c.execute("UPDATE fila SET status=? WHERE id=?", ('enviado' if ja_foi else 'descartado', fid))
        conversa_set(numero, None)
        return responder(inst, numero, f'🗑️ Post #{fid} descartado.' + (f' (já tinha ido para {ja_foi} grupo(s): fica no histórico)' if ja_foi else ''))
    responder(inst, numero, MENU_AVISO if item['origem'] == 'aviso' else f'Post #{fid}:\n{menu()}', fid=fid)


# ---------------------------------------------------------------- divulgador (minera ofertas sozinho)

DIVULGADOR_PADRAO = {
    'ativo': False,
    'modo': 'aprovar',                      # aprovar: manda as sugestões ao FILA POST ZAP | automatico: já aprova (rajadas)
    'horarios': ['05:40', '09:40', '11:40', '14:40', '17:40', '19:40'],   # 20 min antes de cada faixa de nicho
    'por_rodada': 4,                        # quantos posts novos por rodada
    # O que mais vende nos seus pedidos (Ago25–Jul26): vestido, conjunto e calça lideram de longe
    'palavras': ['vestido feminino', 'conjunto feminino', 'calça feminina', 'legging', 'sutiã', 'moletom feminino', 'pijama feminino',
                 'secador de cabelo', 'escova secadora', 'perfume feminino', 'shampoo',
                 'jogo de lençol', 'cortina', 'tapete sala', 'organizador', 'toalha de banho', 'cobertor', 'travesseiro',
                 'cadeira', 'colchão', 'guarda-roupa', 'penteadeira', 'gaveteiro', 'estante',
                 'aspirador', 'ventilador', 'climatizador', 'air fryer', 'jogo de panelas', 'brinquedo infantil'],
    # Focos (público/ocasião): palavras próprias, ligar/desligar e prioridade no ranking (os grupos são de plus size)
    'focos_ativos': [n for n, v in TEMAS_PRONTOS.items() if v[2]],
    'palavras_foco': {n: list(v[1]) for n, v in TEMAS_PRONTOS.items()},
    'peso_foco': 1.6,                       # produto com foco ativo vale 60% a mais no ranking
    'comissao_min': 9.0,                    # R$ por venda (piso do Garimpo)
    'comissao_min_moda': 4.0,               # exceção: público do WhatsApp gosta de moda barata (decisão 18Nov26)
    'nota_min': 4.6, 'vendas_min': 300,
    'nao_repetir_dias': 7,
}


def piso_comissao(nicho, d=None):
    """Piso de comissão (R$ por venda): R$ 9 em geral; 👗 Moda tem piso próprio (padrão R$ 4)."""
    d = d or divulgador_cfg()
    if nicho == '👗 Moda':
        return float(d.get('comissao_min_moda', 4.0))
    return float(d.get('comissao_min', 9.0))


def divulgador_cfg():
    d = dict(DIVULGADOR_PADRAO)
    d.update(get_json('divulgador', {}))
    pf = dict(d.get('palavras_foco') or {})
    for n, v in TEMAS_PRONTOS.items():      # temas prontos novos aparecem (desligados) para quem já tinha salvo
        pf.setdefault(n, list(v[1]))
    d['palavras_foco'] = pf
    return d


def comissao_reais(prod):
    rate = float(prod.get('commissionRate') or 0)
    rate = rate / 100 if rate > 1 else rate
    return round(float(prod.get('priceMin') or 0) * rate, 2)


def minerar(d=None, limite_busca=20):
    """Busca nas palavras-chave (mais vendidos e maior comissão), aplica os filtros e devolve os melhores."""
    d = d or divulgador_cfg()
    campos = 'itemId shopId productName shopName priceMin priceMax ratingStar sales commissionRate imageUrl'
    vistos, achados = set(), []
    corte = (agora() - timedelta(days=int(d['nao_repetir_dias']))).isoformat()
    with db() as c:
        recentes = {r[0] for r in c.execute("SELECT chave FROM fila WHERE criado_em>=? AND status!='descartado'", (corte,))}
    todas = list(d['palavras']) + [w for f in d.get('focos_ativos', []) for w in (d.get('palavras_foco') or {}).get(f, [])]
    for palavra in dict.fromkeys(todas):
        for ordem in (2, 5):                   # 2 = mais vendidos · 5 = maior comissão
            try:
                nodes = shopee_gql(f'{{productOfferV2(keyword:{json.dumps(palavra, ensure_ascii=False)},'
                                   f'limit:{limite_busca},sortType:{ordem}){{nodes{{{campos}}}}}}}')['productOfferV2']['nodes']
            except Exception as e:
                log.warning(f'Divulgador: busca "{palavra}" falhou: {e}')
                continue
            for n in nodes:
                chave = f"{n.get('shopId')}:{n.get('itemId')}"
                if chave in vistos or chave in recentes:
                    continue
                vistos.add(chave)
                com, nota, vendas = comissao_reais(n), float(n.get('ratingStar') or 0), int(n.get('sales') or 0)
                if bloqueado(n.get('productName')) or com < piso_comissao(classificar_nicho(n.get('productName'), palavra), d) \
                        or nota < float(d['nota_min']) \
                        or vendas < int(d['vendas_min']):
                    continue
                piso = piso_comissao(classificar_nicho(n.get('productName'), palavra), d)
                focos = [f for f in classificar_focos(n.get('productName'), palavra) if f in d.get('focos_ativos', [])]
                n.update({'chave': chave, 'comissao_rs': com, 'palavra': palavra, 'focos': focos,  # relativo ao piso do nicho
                          'pontos': (com / piso) * (1 + min(vendas, 20000) / 2000) * (nota / 5)
                                    * (float(d.get('peso_foco', 1.6)) if focos else 1)
                                    * peso_votado(classificar_nicho(n.get('productName'), palavra), focos)})
                achados.append(n)
    achados.sort(key=lambda x: -x['pontos'])
    escolhidos, por_palavra = [], {}
    for n in achados:                          # variedade: no máximo 1 por palavra-chave na rodada
        if por_palavra.get(n['palavra']):
            continue
        por_palavra[n['palavra']] = 1
        escolhidos.append(n)
        if len(escolhidos) >= int(d['por_rodada']):
            break
    return escolhidos


def destino_fila():
    """(grupo FILA POST ZAP, chip conectado nele) para mandar as sugestões."""
    for jid in grupos_fila():
        with db() as c:
            chips = [r[0] for r in c.execute('SELECT instancia FROM grupo_chips WHERE jid=?', (jid,))]
        for inst in chips + instancias():
            if estado_chip(inst) == 'open':
                return jid, inst
    return None, None


def rodar_divulgador(manual=False):
    d = divulgador_cfg()
    jid, inst = destino_fila()
    if not jid:
        log.warning('Divulgador: sem grupo FILA POST ZAP com chip conectado')
        return 0, 'Crie o grupo FILA POST ZAP com um chip conectado dentro.'
    r = ritmo()
    alvo = nichos_da_hora(r, agora() + timedelta(minutes=40))     # o nicho da faixa que vai começar
    if alvo and not manual:
        palavras = [w for w in d['palavras'] if classificar_nicho(w) in alvo]
        focos_alvo = [f for f in d.get('focos_ativos', []) if f in alvo]      # foco escolhido para a faixa
        if palavras or focos_alvo:
            d = dict(d, palavras=palavras, focos_ativos=focos_alvo or d.get('focos_ativos', []))
    escolhidos = minerar(d)
    if not escolhidos:
        return 0, 'Nenhum produto novo passou nos filtros agora.'
    auto = d['modo'] == 'automatico' and not manual
    responder(inst, jid, f"🤖 *Divulgador* · {len(escolhidos)} oferta(s) nova(s) "
                         f"({'já aprovadas, saem nas rajadas' if auto else 'responda em cima de cada uma'})")
    feitos = 0
    for n in escolhidos:
        try:
            p = preparar({'origem': 'divulgador', 'chave': n['chave'], 'produto': n['productName'], 'palavra': n['palavra'],
                          'focos': classificar_focos(n['productName'], n['palavra']),
                          'imagem': n.get('imageUrl', ''), 'preco': br(n.get('priceMin'))})
        except Exception as e:
            log.warning(f'Divulgador: preparar falhou: {e}')
            continue
        if not p.get('link') or any('NÃO convertido' in a for a in p.get('avisos', [])):
            continue                            # nunca sugere sem o seu link de afiliado
        p['produto'] = p['produto'][:120]
        grupos = grupos_ativos()
        with _lock, db() as c:
            cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, comissao, link, texto, grupos, criado_em, dados, '
                            'pedido_por, pedido_inst, status, aprovado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            ('divulgador', p['chave'], p['produto'], p.get('preco'), br(n['comissao_rs']), p['link'],
                             montar_texto(p), json.dumps(grupos), agora().isoformat(), json.dumps(p), jid, inst,
                             'aprovado' if auto else 'rascunho', agora().isoformat() if auto else None))
            fid = cur.lastrowid
        mostrar_previa(inst, jid, fid)
        info = (f"🤖 *Post #{fid}* · {' · '.join([p.get('nicho', '')] + p.get('focos', []))} · comissão R$ {br(n['comissao_rs'])} · {int(n.get('sales') or 0)} vendas · "
                f"⭐ {n.get('ratingStar')} · busca \"{n['palavra']}\"")
        responder(inst, jid, info + ('\n✅ Já aprovado (sai na próxima rajada). Responda *0* em cima para cancelar.'
                                     if auto else f'\n\n{MENU_CURTO}'), fid=fid)
        feitos += 1
    return feitos, ''


def agenda_divulgador():
    """Roda nos horários escolhidos (uma vez por horário por dia)."""
    while True:
        try:
            d = divulgador_cfg()
            if d['ativo']:
                hoje, hm = agora().date().isoformat(), agora().strftime('%H:%M')
                for h in d['horarios']:
                    marca = f'div_{hoje}_{h}'
                    if hm >= h and hm < (datetime.strptime(h, '%H:%M') + timedelta(minutes=30)).strftime('%H:%M') \
                            and not get_cfg(marca):
                        set_cfg(marca, '1')
                        n, msg = rodar_divulgador()
                        log.info(f'Divulgador {h}: {n} post(s) {msg}')
        except Exception:
            log.exception('Divulgador')
        time.sleep(60)


# ---------------------------------------------------------------- engajamento (mensagem do dia, enquete, inbox, monitor)

ENG_PADRAO = {
    'msg_ativo': False, 'msg_hora': '09:30', 'msg_imagem': True,
    'noite_ativo': False, 'noite_hora': '21:00', 'noite_imagem': True,
    'convite_ativo': False, 'convite_dias': [2, 5], 'convite_hora': '19:30',   # convite de pedidos automático (0=seg … 6=dom)
    'amiga_ativo': False, 'amiga_dias': [0, 3], 'amiga_hora': '12:30', 'amiga_grupos': [],   # 👭 convide uma amiga (links dos grupos)
    'imagem_ordem': 'gemini,openai',        # quem gera as imagens, em ordem (gemini | openai | pollinations)
    'enquete_hora_modo': 'aleatorio',       # aleatorio: um horário sorteado por dia dentro da janela | fixo: enquete_hora
    'enquete_janela': ['19:00', '22:00'],
    'enquete_ativo': False, 'enquete_hora': '19:30',
    'enquete_pergunta': 'O que vocês querem ver mais aqui no grupo amanhã? 💜',
    'enquete_opcoes': ['👗 Moda', '➕ Plus Size', '👟 Calçados', '👙 Moda íntima', '💇 Beleza e cabelo', '🏠 Casa e decoração',
                       '🍳 Cozinha e utensílios', '🎄 Natal', '🎁 Presentes', '🧸 Infantil'],
    'enquete_modo': 'rodizio',             # rodizio: pacotes de opções que combinam, trocando a cada N dias | fixa: as opções escolhidas
    'enquete_troca_dias': 2,
    'peso_votos': 1.5,                      # o mais votado vale até 50% a mais no Divulgador (proporcional aos votos)
    'aprovar': True,                        # mensagem do dia e enquete vão ao FILA POST ZAP para você aprovar
    'inbox_ativo': False, 'inbox_max_dia': 5,
    'inbox_gatilho': 'quero',               # só responde mensagem que COMEÇA com uma dessas palavras (separadas por vírgula)
    'inbox_chips': [],                      # chips que atendem pedidos (vazio = todos); desmarque o seu WhatsApp pessoal
    'inbox_silencio_h': 12,                 # se VOCÊ falou com a pessoa nas últimas X horas, o robô fica quieto
    'monitor_ativo': False, 'monitor_grupos': [], 'monitor_telegram': [],
}


def eng_cfg():
    d = dict(ENG_PADRAO)
    d.update(get_json('engajamento', {}))
    return d


def chat_ia(prompt, max_len=900):
    """Texto pela IA (OpenAI). Tenta o modelo do .env e, se falhar ou vier vazio, um modelo reserva. Erro explica o motivo."""
    key = chave_openai()
    if not key:
        raise RuntimeError('sem chave da OpenAI (OPENAI_API_KEY no .env do PostZap ou do robô do Shopee Vídeo)')
    erros = []
    for modelo in dict.fromkeys([CFG['openai_model'], os.getenv('OPENAI_MODEL_RESERVA', 'gpt-4o-mini')]):
        try:
            req = urllib.request.Request('https://api.openai.com/v1/chat/completions', headers={
                'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                data=json.dumps({'model': modelo, 'messages': [{'role': 'user', 'content': prompt}]}).encode())
            with urllib.request.urlopen(req, timeout=90) as r:
                msg = json.load(r)['choices'][0]['message']
            c = msg.get('content')
            if isinstance(c, list):                    # alguns modelos devolvem partes
                c = ''.join(p.get('text', '') for p in c if isinstance(p, dict))
            c = (c or '').strip()
            if c:
                return c[:max_len]
            erros.append(f'{modelo}: resposta vazia' + (f" ({msg.get('refusal')})" if msg.get('refusal') else ''))
        except urllib.error.HTTPError as e:
            try:
                erros.append(f"{modelo}: {json.loads(e.read().decode()).get('error', {}).get('message', '')[:140]}")
            except Exception:
                erros.append(f'{modelo}: HTTP {e.code}')
        except Exception as e:
            erros.append(f'{modelo}: {str(e)[:140]}')
    raise RuntimeError(' | '.join(erros))


_ultimo_erro_imagem = ['']


def _erro_http(e):
    try:
        d = json.loads(e.read().decode())
        return (d.get('error', {}) or {}).get('message', '') or str(d)[:140]
    except Exception:
        return str(e)


def _img_gemini(prompt, erros):
    """Google Gemini ("Nano Banana") e Imagen. Chave grátis em aistudio.google.com → GEMINI_API_KEY no .env."""
    key = chave_env('GEMINI_API_KEY') or chave_env('GOOGLE_API_KEY')
    if not key:
        erros.append('Gemini: sem chave (GEMINI_API_KEY)')
        return ''
    base = 'https://generativelanguage.googleapis.com/v1beta/models/'
    hdr = {'x-goog-api-key': key, 'Content-Type': 'application/json'}
    for modelo in dict.fromkeys([os.getenv('GEMINI_IMAGE_MODEL', ''), 'gemini-2.5-flash-image', 'imagen-4.0-generate-001']):
        if not modelo:
            continue
        try:
            if modelo.startswith('imagen'):
                corpo = {'instances': [{'prompt': prompt[:3000]}], 'parameters': {'sampleCount': 1, 'aspectRatio': '1:1'}}
                req = urllib.request.Request(base + modelo + ':predict', data=json.dumps(corpo).encode(), headers=hdr)
                with urllib.request.urlopen(req, timeout=180) as r:
                    for pr in json.load(r).get('predictions', []):
                        if pr.get('bytesBase64Encoded'):
                            return pr['bytesBase64Encoded']
            else:
                corpo = {'contents': [{'parts': [{'text': prompt[:3800]}]}],
                         'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': '1:1'}}}
                req = urllib.request.Request(base + modelo + ':generateContent', data=json.dumps(corpo).encode(), headers=hdr)
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.load(r)
                for cand in d.get('candidates', []):
                    for part in (cand.get('content') or {}).get('parts', []):
                        dado = (part.get('inlineData') or part.get('inline_data') or {}).get('data')
                        if dado:
                            return dado
            erros.append(f'{modelo}: veio sem imagem')
        except urllib.error.HTTPError as e:
            erros.append(f'{modelo}: {_erro_http(e)[:140]}')
        except Exception as e:
            erros.append(f'{modelo}: {str(e)[:140]}')
    return ''


def _img_openai(prompt, erros):
    """OpenAI (o mesmo gerador de imagens do ChatGPT). gpt-image-1 pede a organização verificada na OpenAI."""
    import base64
    key = chave_openai()
    if not key:
        erros.append('OpenAI: sem chave')
        return ''
    for modelo in dict.fromkeys([os.getenv('OPENAI_IMAGE_MODEL', ''), 'gpt-image-1', 'gpt-image-1-mini', 'dall-e-3']):
        if not modelo:
            continue
        corpo = {'model': modelo, 'prompt': prompt[:3800], 'size': '1024x1024', 'n': 1}
        if modelo.startswith('dall-e'):
            corpo.update(response_format='b64_json', quality='hd', style='natural')
        else:
            corpo['quality'] = 'high'
        try:
            req = urllib.request.Request('https://api.openai.com/v1/images/generations', data=json.dumps(corpo).encode(),
                                         headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.load(r)['data'][0]
            if d.get('b64_json'):
                return d['b64_json']
            if d.get('url'):
                with urllib.request.urlopen(d['url'], timeout=60) as r2:
                    return base64.b64encode(r2.read()).decode()
        except urllib.error.HTTPError as e:
            erros.append(f'{modelo}: {_erro_http(e)[:140]}')
        except Exception as e:
            erros.append(f'{modelo}: {str(e)[:140]}')
    return ''


def _img_pollinations(prompt, erros):
    import base64
    try:
        url = ('https://image.pollinations.ai/prompt/' + urllib.parse.quote(prompt[:900]) +
               f'?width=1024&height=1024&nologo=true&model=flux&enhance=true&seed={random.randint(1, 10**6)}')
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=180) as r:
            tipo, dados_img = r.headers.get('Content-Type', ''), r.read()
        if tipo.startswith('image/') and len(dados_img) > 5000:
            return base64.b64encode(dados_img).decode()
        erros.append(f'pollinations: resposta inválida ({tipo}, {len(dados_img)} bytes)')
    except Exception as e:
        erros.append(f'pollinations: {str(e)[:140]}')
    return ''


GERADORES_IMG = {'gemini': _img_gemini, 'openai': _img_openai, 'pollinations': _img_pollinations}


def reduzir_imagem(b64):
    """PNG grande da IA (1–3 MB) → JPEG ~1080px (bem mais leve pro WhatsApp). Sem a Pillow, devolve como veio."""
    try:
        import base64, io
        from PIL import Image
        im = Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')
        im.thumbnail((1080, 1080))
        out = io.BytesIO()
        im.save(out, 'JPEG', quality=85, optimize=True)
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return b64


def imagem_ia(prompt):
    """Imagem quadrada pela IA. Ordem em ✏️/💬 (cfg imagem_ordem), padrão: Gemini → ChatGPT/OpenAI.
    A reserva grátis (Pollinations) vem desligada: qualidade ruim — melhor sair sem imagem.
    Devolve base64 ou '' — o motivo da falha fica em _ultimo_erro_imagem."""
    ordem = [x.strip() for x in str(eng_cfg().get('imagem_ordem') or 'gemini,openai').split(',') if x.strip() in GERADORES_IMG]
    erros = []
    for nome in ordem or ['gemini', 'openai']:
        b64 = GERADORES_IMG[nome](prompt, erros)
        if b64:
            _ultimo_erro_imagem[0] = ''
            _ultimo_gerador[0] = nome
            return reduzir_imagem(b64)
    _ultimo_erro_imagem[0] = ' | '.join(erros)
    log.warning(f'Imagem da IA falhou: {_ultimo_erro_imagem[0]}')
    return ''


_ultimo_gerador = ['']

CENAS_DIA = ['a cozy sunlit Brazilian living room with a cup of coffee, fresh flowers and a stylish dress on a hanger',
             'a smiling curvy Brazilian woman in a colorful midi dress holding shopping bags on a sunny street',
             'flat lay of a pastel outfit, sandals, a handbag and a coffee cup on a light wooden table, morning light',
             'two happy curvy Brazilian friends laughing while looking at a phone, bright café, morning',
             'a beautiful breakfast table with coffee, fruit and a small gift box with a lilac ribbon']
CENAS_NOITE = ['a calm bedroom at night with warm fairy lights, a soft blanket and a cup of tea',
               'a curvy Brazilian woman relaxing on a sofa at night smiling at her phone, warm lamp light',
               'a cozy window at night with a crescent moon, candles and a small Christmas tree with warm lights',
               'flat lay of a silk pajama, a book and a scented candle, warm evening light']


def prompt_imagem(periodo, tipo):
    cenas = CENAS_NOITE if periodo == 'noite' else CENAS_DIA
    cena = random.choice(cenas)
    if 'natal' in tipo.lower() or agora().month == 12:
        cena += ', subtle Christmas decorations'
    return (f"Professional lifestyle photograph, {cena}. Natural realistic skin and hands, correct anatomy, soft natural light, "
            "shallow depth of field, shot on a full-frame camera, 50mm lens, warm pastel color palette with lilac and pink accents, "
            "Instagram-quality, clean composition with space at the top. Absolutely no text, letters, words, logos or watermarks.")


TIPOS_NOITE = ['boa noite carinhoso agradecendo quem acompanhou as ofertas do dia e avisando que amanhã tem mais',
               'pergunta leve para responder antes de dormir (ex.: qual achadinho de hoje você mais gostou?)',
               'lembrete gentil para ativar as notificações do grupo e não perder as ofertas da manhã',
               'frase de autoestima e descanso para mulheres reais, com carinho',
               'convite para chamar no privado mandando a palavra QUERO seguida do produto (ex.: "QUERO tênis confortável"), que a gente procura a melhor oferta',
               'contagem regressiva para a Black Friday/Natal, pedindo para deixar nos comentários o que querem ver']
TIPOS_MSG = ['bom dia animado com uma pergunta para o grupo responder', 'dica rápida de moda plus size (como combinar uma peça)',
             'contagem regressiva para a Black Friday ou o Natal, convidando a ficar de olho nas ofertas do grupo',
             'pergunta divertida de "isso ou aquilo" sobre moda/casa', 'frase motivacional de autoestima para mulheres reais',
             'convite para chamar no privado mandando a palavra QUERO seguida do produto que procura (ex.: "QUERO vestido plus size azul"), que a gente acha a melhor oferta']


BANCO_DIA = ['*Bom dia, lindas!* ☀️ Hoje tem achadinho novo chegando por aqui. Qual peça vocês mais querem ver hoje? 👇',
             '*Bom dia!* 💜 Café na mão e olho nas ofertas! Me conta: vocês preferem *vestido* ou *conjunto*? 👗',
             '*Bom dia, meninas!* 🌸 Lembrando que aqui é lugar de mulher real e preço bom. O que vocês estão precisando essa semana?',
             '*Bom dia!* ☀️ Faltam poucos dias pra *Black Friday*! Deixem aqui o que vocês querem que eu procure 🛍️',
             '*Bom dia, lindas!* 💖 Sabiam que dá pra pedir um produto? Me chama no privado escrevendo *QUERO* + o produto (ex.: _QUERO vestido plus size azul_) que eu procuro a melhor oferta!']
BANCO_NOITE = ['*Boa noite, lindas!* 🌙 Obrigada por acompanharem as ofertas de hoje. Amanhã tem mais! Qual achadinho vocês mais amaram? 💜',
               '*Boa noite!* ✨ Antes de dormir: ativem as notificações do grupo pra não perder as ofertas da manhã 🔔',
               '*Boa noite, meninas!* 🌙 Vocês merecem descanso e autoestima lá em cima. Amanhã a gente garimpa mais coisa boa! 💖',
               '*Boa noite!* 🎄 O Natal tá chegando! Me contem nos comentários o que vocês querem ver por aqui 👇',
               '*Boa noite, lindas!* 💜 Tá procurando algo? Me chama no privado escrevendo *QUERO* + o produto (ex.: _QUERO jogo de lençol_) que eu procuro a melhor oferta!']
_motivo_texto = ['']


def mensagem_do_dia(periodo='dia'):
    """Texto + imagem de engajamento (não é oferta): o grupo sente que tem gente de verdade cuidando dele."""
    e = eng_cfg()
    hoje = agora()
    tipos = TIPOS_NOITE if periodo == 'noite' else TIPOS_MSG
    tipo = tipos[hoje.toordinal() % len(tipos)]
    if 'privado' in tipo and not e.get('inbox_ativo'):
        tipo = tipos[0]
    contexto = (f"Hoje é {data_sub(hoje)}. Black Friday: 27Nov26. Natal: 25Dez26. O grupo é de ofertas da Shopee para mulheres, "
                "a maioria do público é plus size; também há público evangélico.")
    try:
        texto = chat_ia(f"{contexto}\nEscreva uma mensagem curta (máx. 5 linhas) para o grupo de WhatsApp, em português do Brasil, "
                        f"tom acolhedor e animado, com emojis na medida, do tipo: {tipo}. Termine com uma pergunta ou convite para "
                        "interagir. Não fale de preço, não invente promoções, sem hashtags. Use *negrito* do WhatsApp em 1 trecho.")
        _motivo_texto[0] = ''
    except Exception as ex:                      # IA fora: usa um texto pronto (nunca manda vazio)
        banco = (e.get('banco_noite') or BANCO_NOITE) if periodo == 'noite' else (e.get('banco_dia') or BANCO_DIA)
        texto = banco[hoje.toordinal() % len(banco)]
        _motivo_texto[0] = str(ex)[:200]
        log.warning(f'Texto da IA falhou, usando texto pronto: {ex}')
    convite = False
    if ('privado' in tipo or 'QUERO' in texto) and e.get('inbox_ativo'):
        link = link_pedido()
        if link:
            texto = texto.rstrip() + f'\n\n👉 *Toque aqui pra pedir:* {link}'
            convite = True
    img = ''
    if convite and imagens_convite():
        return texto, 'CONVITE'
    if e.get('noite_imagem' if periodo == 'noite' else 'msg_imagem'):
        img = imagem_ia(prompt_imagem(periodo, tipo))
    return texto, img


def criar_post_engajamento(origem, texto, dados, produto):
    jid_fila, inst_fila = destino_fila()
    e = eng_cfg()
    grupos = grupos_ativos()
    status = 'rascunho' if e.get('aprovar') else 'aprovado'
    with _lock, db() as c:
        cur = c.execute('INSERT INTO fila (origem, chave, produto, texto, grupos, criado_em, dados, pedido_por, pedido_inst, status, '
                        'aprovado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (origem, '', produto, texto, json.dumps(grupos), agora().isoformat(), json.dumps(dados, ensure_ascii=False),
                         jid_fila, inst_fila, status, None if status == 'rascunho' else agora().isoformat()))
        fid = cur.lastrowid
    if jid_fila:
        mostrar_previa(inst_fila, jid_fila, fid)
        responder(inst_fila, jid_fila, f"💬 *{produto} #{fid}* · " + ('responda *1* em cima para enviar aos grupos (ou *0*)'
                  if status == 'rascunho' else 'já aprovado, sai na próxima rajada (responda *0* em cima para cancelar)'), fid=fid)
    return fid


def rodar_mensagem_do_dia(periodo='dia'):
    texto, img = mensagem_do_dia(periodo)
    dados = {}
    if img == 'CONVITE':
        dados, img = dados_convite(), ''
        _ultimo_erro_imagem[0] = ''
    if img:
        MIDIA_DIR.mkdir(exist_ok=True)
        arq = MIDIA_DIR / f"eng_{int(time.time())}.b64"
        arq.write_text(img)
        dados = {'midia': str(arq), 'midia_tipo': 'image', 'mimetype': 'image/jpeg' if img.startswith('/9j') else 'image/png'}
    titulo = '🌙 Mensagem da noite' if periodo == 'noite' else '☀️ Mensagem do dia'
    if _motivo_texto[0]:
        titulo += ' (texto pronto, a IA falhou: ' + _motivo_texto[0][:120] + ')'
    if eng_cfg().get('noite_imagem' if periodo == 'noite' else 'msg_imagem') and not img and not dados:
        titulo += ' (sem imagem: ' + (_ultimo_erro_imagem[0] or 'erro desconhecido')[:160] + ')'
    return criar_post_engajamento('aviso', texto, dados, titulo)


# Pacotes de opções que fazem sentido juntas (rodízio): cada pacote fica N dias e depois troca
PACOTES_ENQUETE = [
    ('Qual dessas vocês querem ver mais amanhã? 👗', ['👗 Moda', '➕ Plus Size', '👙 Moda íntima', '👟 Calçados', '👜 Bolsas e acessórios', '🏋️ Fitness']),
    ('Pra casa, o que vocês mais estão precisando? 🏠', ['🏠 Casa e decoração', '🍳 Cozinha e utensílios', '🔌 Eletrodomésticos', '🛋️ Móveis', '🎄 Natal']),
    ('Qual desses achadinhos vocês querem que eu procure? 💖', ['💇 Beleza e cabelo', '🎁 Presentes', '🧸 Infantil', '🐶 Pet', '🎧 Eletrônicos']),
    ('Pras festas de fim de ano, o que vocês querem ver? 🎄', ['🎄 Natal', '🎆 Réveillon', '🎁 Presentes', '➕ Plus Size', '✝️ Evangélica', '☀️ Verão e praia']),
]


def enquete_de_hoje():
    """(pergunta, opções) da enquete de hoje: rodízio de pacotes ou as opções fixas escolhidas."""
    e = eng_cfg()
    if e.get('enquete_modo', 'rodizio') != 'rodizio':
        return e['enquete_pergunta'], [o for o in e['enquete_opcoes'] if o.strip()][:12]
    troca = max(1, int(e.get('enquete_troca_dias', 2)))
    pac = [p for p in PACOTES_ENQUETE if not (p[1][0] == '🎄 Natal' and p[1][1] == '🎆 Réveillon' and agora().month not in (11, 12))]
    pergunta, opcoes = pac[(agora().toordinal() // troca) % len(pac)]
    return pergunta, opcoes


def rodar_enquete():
    e = eng_cfg()
    pergunta, opcoes = enquete_de_hoje()
    e = dict(e, enquete_pergunta=pergunta)
    if len(opcoes) < 2:
        raise RuntimeError('a enquete precisa de pelo menos 2 opções')
    return criar_post_engajamento('aviso', '', {'enquete': {'pergunta': e['enquete_pergunta'], 'opcoes': opcoes}},
                                  '📊 Enquete: ' + e['enquete_pergunta'][:40])


def _achar(obj, chave):
    """Procura uma chave em qualquer nível do JSON (o formato do voto muda entre versões da Evolution)."""
    if isinstance(obj, dict):
        if chave in obj:
            yield obj[chave]
        for v in obj.values():
            yield from _achar(v, chave)
    elif isinstance(obj, list):
        for v in obj:
            yield from _achar(v, chave)


def registrar_voto(data):
    sel = next(_achar(data, 'selectedOptions'), None)
    if sel is None:
        return False
    poll_key = next(_achar(data, 'pollCreationMessageKey'), None) or next(_achar(data, 'pollUpdateMessageKey'), None) or {}
    mid = poll_key.get('id') if isinstance(poll_key, dict) else None
    key = data.get('key') or {}
    eleitor = key.get('participant') or key.get('participantAlt') or key.get('remoteJid') or ''
    nomes = [o.get('name') if isinstance(o, dict) else str(o) for o in (sel or [])]
    with db() as c:
        if not mid or not c.execute('SELECT 1 FROM enquetes WHERE msg_id=?', (mid,)).fetchone():
            return True
    with _lock, db() as c:
        if nomes:
            c.execute('INSERT OR REPLACE INTO votos VALUES (?,?,?,?)', (mid, eleitor, json.dumps(nomes, ensure_ascii=False), agora().isoformat()))
        else:
            c.execute('DELETE FROM votos WHERE msg_id=? AND eleitor=?', (mid, eleitor))   # tirou o voto
    return True


def resultado_votos(dias=2):
    corte = (agora() - timedelta(days=dias)).isoformat()
    cont = {}
    with db() as c:
        for (ops,) in c.execute('SELECT opcoes FROM votos WHERE quando>=?', (corte,)):
            for o in json.loads(ops):
                cont[o] = cont.get(o, 0) + 1
    return dict(sorted(cont.items(), key=lambda x: -x[1]))


def peso_votado(nicho, focos):
    """Prioridade extra no Divulgador para o que o grupo votou (proporcional aos votos dos últimos 2 dias)."""
    r = resultado_votos()
    if not r:
        return 1.0
    top = max(r.values())
    v = max([r.get(nicho, 0)] + [r.get(f, 0) for f in focos or []])
    return 1 + (float(eng_cfg().get('peso_votos', 1.5)) - 1) * v / top


def link_pedido():
    """Link "toque aqui pra pedir": abre o privado de um chip que atende pedidos com "QUERO " já escrito."""
    e = eng_cfg()
    chips = e.get('inbox_chips') or instancias()
    for inst in chips:
        if estado_chip(inst) != 'open':
            continue
        num = get_cfg(f'numero_{inst}')
        if not num:
            try:
                num = numero_do_chip(inst)
                if num:
                    set_cfg(f'numero_{inst}', num)
            except Exception:
                num = ''
        if num:
            gat = (str(e.get('inbox_gatilho') or 'quero').split(',')[0].strip() or 'quero').upper()
            return f"https://wa.me/{num}?text={urllib.parse.quote(gat + ' ')}"
    return ''


CONVITE_PEDIDOS = ('🛍️ *Tá procurando alguma coisa específica?*\n\n'
                   'Toque no link abaixo, escreva o produto depois do *QUERO* e me manda — eu procuro as *melhores ofertas* '
                   'da Shopee e te respondo rapidinho! 💜\n\n'
                   'Ex.: _QUERO vestido plus size azul_ · _QUERO jogo de lençol queen_\n\n'
                   '👉 *Toque aqui pra pedir:* {link}')


CONVITE_DIR = BASE / 'convite'


def imagens_convite():
    """Imagens fixas do convite "me chama no privado": as suas (enviadas no app) ou as prontas (A e D), em rodízio."""
    suas = [x for x in get_json('convite_imgs', []) if Path(x).exists()]
    return suas or [str(p) for p in sorted(CONVITE_DIR.glob('*.jpg')) if p.name != 'amiga.jpg']


def dados_convite():
    import base64
    imgs = imagens_convite()
    if not imgs:
        return {}
    n = int(get_cfg('convite_vez', '0') or 0)
    set_cfg('convite_vez', str(n + 1))
    arq = Path(imgs[n % len(imgs)])
    MIDIA_DIR.mkdir(exist_ok=True)
    b64 = MIDIA_DIR / f"convite_{int(time.time())}.b64"
    b64.write_text(base64.b64encode(arq.read_bytes()).decode())
    return {'midia': str(b64), 'midia_tipo': 'image', 'mimetype': 'image/png' if arq.suffix == '.png' else 'image/jpeg'}


def _grupos_admin():
    with db() as c:
        return sorted(((r[0], r[1]) for r in c.execute('SELECT jid, nome FROM grupos WHERE admin=1') if r[0] not in grupos_fila()), key=lambda x: x[1])


def grupos_para_amiga():
    """Grupos que entram na lista do "convide uma amiga": os escolhidos, ou todos onde algum chip é admin."""
    e = eng_cfg()
    fora = grupos_fila() | set(e.get('monitor_grupos') or [])
    with db() as c:
        todos = {r[0]: r[1] for r in c.execute('SELECT jid, nome FROM grupos WHERE admin=1')}
        cheios = {r[0] for r in c.execute("SELECT m.jid FROM membros m WHERE m.total>=1000 AND m.dia=(SELECT MAX(dia) FROM membros "
                                           "WHERE jid=m.jid AND total IS NOT NULL)")}
    with db() as c:
        usados = {r[0] for r in c.execute("SELECT DISTINCT jid FROM envios WHERE ok=1 AND quando>=?",
                                          ((agora() - timedelta(days=30)).isoformat(),))}
    escolhidos = ([j for j in (e.get('amiga_grupos') or []) if j in todos] or [j for j in todos if j in usados] or list(todos))
    lista = [(j, todos[j]) for j in escolhidos if j not in fora and j not in cheios]
    return sorted(lista, key=lambda x: x[1])


def link_convite_grupo(jid):
    """Link chat.whatsapp.com do grupo (precisa de um chip admin). Guarda por 1 dia."""
    cache = get_json('links_grupo', {})
    if cache.get(jid, {}).get('dia') == agora().date().isoformat():
        return cache[jid]['url']
    with db() as c:
        chips = [r[0] for r in c.execute('SELECT instancia FROM grupo_chips WHERE jid=? ORDER BY admin DESC', (jid,))]
    for inst in chips:
        if estado_chip(inst) != 'open':
            continue
        try:
            r = evo('GET', f'/group/inviteCode/{inst}?groupJid={urllib.parse.quote(jid)}', timeout=60)
            url = r.get('inviteUrl') or (f"https://chat.whatsapp.com/{r['inviteCode']}" if r.get('inviteCode') else '')
            if url:
                cache[jid] = {'url': url, 'dia': agora().date().isoformat()}
                set_cfg('links_grupo', json.dumps(cache))
                return url
        except Exception as ex:
            log.warning(f'Link do grupo {jid} pelo {inst}: {ex}')
    return ''


def texto_convide_amiga():
    linhas = []
    for i, (jid, nome) in enumerate(grupos_para_amiga(), 1):
        url = link_convite_grupo(jid)
        if not url:
            continue
        m = re.match(r'\s*#?(\d+)', nome)
        rot = f'GRUPO {int(m.group(1)):02d}' if m else f'GRUPO {i:02d}'
        linhas.append(f'🔗 *{rot}* → {url}')
    if not linhas:
        raise RuntimeError('não consegui o link de nenhum grupo (algum chip precisa ser admin e estar conectado)')
    abre = random.choice([
        '👭 *Achadinho bom a gente divide!*\n\nTem uma amiga, irmã ou prima que ama uma promoção? Chama ela pra cá! 💜',
        '💌 *Sabe aquela amiga que vive perguntando onde você comprou?*\n\nManda pra ela um dos links abaixo e deixa ela garimpar com a gente! ✨',
        '🛍️ *Quanto mais amigas, mais achadinhos!*\n\nCompartilhe um dos nossos grupos com quem você gosta, a entrada é grátis! 💜'])
    return (abre + '\n\n📲 *Escolha um grupo e encaminhe o link:*\n\n' + '\n'.join(linhas) +
            '\n\n💡 Se um grupo estiver lotado, é só tentar o próximo da lista. O conteúdo é o mesmo em todos!\n\n'
            'Obrigada por espalhar o amor pelas ofertas! 🥰')


PROMPT_AMIGAS = ("Professional lifestyle photograph of three happy Brazilian women friends of different body types, including "
                 "curvy plus size, laughing together on a sofa while looking at a smartphone and holding colorful shopping bags, "
                 "cozy bright living room, warm natural light, lilac and pink accents, genuine joyful expressions, correct anatomy and hands, "
                 "shallow depth of field, 50mm lens, Instagram quality. Absolutely no text, letters, logos or watermarks.")
AMIGA_IA = MIDIA_DIR / 'amiga_ia.b64'


def gerar_imagem_amiga():
    """Imagem das amigas pela IA (Gemini → ChatGPT). Fica guardada e é reusada em todos os convites."""
    img = imagem_ia(PROMPT_AMIGAS)
    if not img:
        raise RuntimeError('a IA não gerou a imagem: ' + (_ultimo_erro_imagem[0] or 'erro desconhecido')[:200])
    MIDIA_DIR.mkdir(exist_ok=True)
    AMIGA_IA.write_text(img)
    return _ultimo_gerador[0]


def rodar_convite_amiga():
    import base64
    dados = {}
    arq = BASE / 'convite' / 'amiga.jpg'
    if not AMIGA_IA.exists():
        try:
            gerar_imagem_amiga()
        except Exception as ex:
            log.warning(f'Imagem das amigas: {ex}')
    if AMIGA_IA.exists():
        MIDIA_DIR.mkdir(exist_ok=True)
        b64 = MIDIA_DIR / f"amiga_{int(time.time())}.b64"
        conteudo = AMIGA_IA.read_text()
        b64.write_text(conteudo)
        dados = {'midia': str(b64), 'midia_tipo': 'image', 'mimetype': 'image/jpeg' if conteudo.startswith('/9j') else 'image/png'}
    elif arq.exists():
        MIDIA_DIR.mkdir(exist_ok=True)
        b64 = MIDIA_DIR / f"amiga_{int(time.time())}.b64"
        b64.write_text(base64.b64encode(arq.read_bytes()).decode())
        dados = {'midia': str(b64), 'midia_tipo': 'image', 'mimetype': 'image/jpeg'}
    return criar_post_engajamento('aviso', texto_convide_amiga(), dados, '👭 Convide uma amiga')


def rodar_convite_pedidos():
    link = link_pedido()
    if not link:
        raise RuntimeError('nenhum chip que atende pedidos está conectado (veja 💌 "Me chama no privado")')
    return criar_post_engajamento('aviso', CONVITE_PEDIDOS.format(link=link), dados_convite(), '💌 Convite de pedidos')


def gatilhos_inbox(e=None):
    e = e or eng_cfg()
    return [normalizar(g) for g in str(e.get('inbox_gatilho') or '').split(',') if normalizar(g)]


def inbox_deve_responder(inst, jid, texto):
    """Só responde pedido quando: está ligado, o chip atende pedidos, a mensagem começa com a palavra-gatilho
    e você não conversou com essa pessoa há pouco (para não falar com seus amigos)."""
    e = eng_cfg()
    if not e.get('inbox_ativo'):
        return False
    if e.get('inbox_chips') and inst not in e['inbox_chips']:
        return False
    gat = gatilhos_inbox(e)
    primeira = normalizar(texto.strip().split()[0]) if texto.strip() else ''
    if gat and primeira not in gat:
        return False
    ultimo = float(get_cfg(f'humano_{inst}_{digitos(jid)[-11:]}', '0') or 0)
    if time.time() - ultimo < float(e.get('inbox_silencio_h', 12)) * 3600:
        return False
    return True


def pedido_inbox(inst, jid, texto):
    """Alguém do grupo chamou no privado dizendo o que procura: devolve as 3 melhores ofertas com o seu link (Sub ID inbox)."""
    e = eng_cfg()
    hoje = agora().date().isoformat()
    with db() as c:
        n = c.execute('SELECT COUNT(*) FROM pedidos_inbox WHERE numero=? AND quando>=?', (jid, hoje)).fetchone()[0]
    if n >= int(e.get('inbox_max_dia', 5)):
        return
    termo = re.sub(r'https?://\S+', '', texto)
    for g in str(e.get('inbox_gatilho') or '').split(','):     # tira a palavra-gatilho ("QUERO vestido…" → "vestido…")
        if g.strip():
            termo = re.sub(rf'^\s*#?{re.escape(g.strip())}\b[\s:,-]*', '', termo, flags=re.I)
    termo = re.sub(r'(?i)\b(oi|ol[aá]|bom dia|boa tarde|boa noite|tudo bem|por favor|queria|quero|procuro|preciso de?|'
                   r'estou procurando|tem|voc[eê]s? t[eê]m|um|uma|uns|umas)\b[,!.?]*', ' ', termo)
    termo = re.sub(r'\s+', ' ', termo).strip(' ,.!?')[:60]
    if len(termo) < 3 or bloqueado(termo):
        if len(termo) < 3:
            responder(inst, jid, 'Oi! 💜 Me manda *QUERO* + o nome do produto (ex.: "QUERO vestido plus size azul") '
                                 'que eu procuro a melhor oferta pra você!')
        return
    try:
        nodes = shopee_gql(f'{{productOfferV2(keyword:{json.dumps(termo, ensure_ascii=False)},limit:30,sortType:2)'
                           '{nodes{itemId shopId productName priceMin ratingStar sales commissionRate imageUrl}}}')['productOfferV2']['nodes']
    except Exception as ex:
        log.warning(f'Inbox: busca falhou: {ex}')
        return
    bons = [x for x in nodes if not bloqueado(x.get('productName')) and float(x.get('ratingStar') or 0) >= 4.5]
    bons.sort(key=lambda x: -(int(x.get('sales') or 0) ** 0.5 * float(x.get('ratingStar') or 0) * (1 + comissao_reais(x) / 10)))
    linhas = []
    for x in bons[:3]:
        try:
            link = shopee_gql(f'mutation{{generateShortLink(input:{{originUrl:'
                              f'{json.dumps(f"https://shopee.com.br/product/{x["shopId"]}/{x["itemId"]}")},'
                              f'subIds:{json.dumps([CFG["sub_id"], "inbox", data_sub(agora())])}}}){{shortLink}}}}')['generateShortLink']['shortLink']
        except Exception:
            continue
        linhas.append(f"🛍️ *{x['productName'][:70]}*\n💰 R$ {br(x.get('priceMin'))} · ⭐ {x.get('ratingStar')} · {int(x.get('sales') or 0)} vendidos\n👉 {link}")
    with _lock, db() as c:
        c.execute('INSERT INTO pedidos_inbox (numero, texto, resultado, quando) VALUES (?,?,?,?)',
                  (jid, texto[:200], f'{len(linhas)} oferta(s) para "{termo}"', agora().isoformat()))
    if linhas:
        responder(inst, jid, f'Achei essas ofertas pra *{termo}* 💜\n\n' + '\n\n'.join(linhas) +
                  '\n\n⚠️ Preços podem mudar a qualquer momento. Se quiser outra coisa, é só me mandar!')
    else:
        responder(inst, jid, f'Procurei *{termo}* e não achei uma oferta boa agora 😕 Tenta descrever de outro jeito '
                             '(ex.: "conjunto plus size linho") que eu procuro de novo!')


# ---- monitor de grupos (WhatsApp) e canais públicos (Telegram)

def grupos_monitorados():
    e = eng_cfg()
    return set(e.get('monitor_grupos') or []) - grupos_fila() if e.get('monitor_ativo') else set()


def nome_grupo(jid):
    with db() as c:
        r = c.execute('SELECT nome FROM grupos WHERE jid=?', (jid,)).fetchone()
    return r[0] if r else jid


CUPOM_RE = re.compile(r'(?i)\bcupom\b|\bcupons\b|\bcódigo\b|\bcodigo\b')


def stat_monitor(fonte, **inc):
    """Painel do monitor: por fonte, quando leu pela última vez, quantas mensagens/achados e o último erro."""
    with _lock:
        st = get_json('monitor_stat', {})
        f = st.setdefault(fonte, {'msgs': 0, 'achados': 0, 'cupons': 0})
        f['visto'] = agora().strftime('%Y-%m-%dT%H:%M')
        for k, v in inc.items():
            if k == 'erro':
                f['erro'] = v
            else:
                f[k] = f.get(k, 0) + v
        if 'erro' not in inc:
            f.pop('erro', None)
        set_cfg('monitor_stat', json.dumps(st, ensure_ascii=False))


def cupom_do_texto(texto):
    m = re.search(r'(?i)(?:cupom|c[oó]digo)\s*[:\-]?\s*\*?([A-Z0-9]{4,20})\b', texto)
    return m.group(1).upper() if m else ''


def produto_pelo_nome(texto):
    """Achado sem link: tenta achar o produto na Shopee pelo nome escrito na mensagem → 'loja:item' ou ''."""
    linhas = [re.sub(r'[*_~]', '', l).strip() for l in texto.splitlines()]
    candidatas = [l for l in linhas if len(l) >= 12 and not re.search(r'(?i)cupom|c[oó]digo|r\$|compre|link|http|corre+', l)]
    if not candidatas:
        return ''
    nome = max(candidatas, key=len)[:80]
    try:
        nodes = shopee_gql(f'{{productOfferV2(keyword:{json.dumps(nome, ensure_ascii=False)},limit:10,sortType:2)'
                           '{nodes{itemId shopId productName}}}')['productOfferV2']['nodes']
    except Exception:
        return ''
    alvo = set(normalizar(nome).split())
    for x in nodes:                              # só aceita se o nome bater bem (pelo menos 60% das palavras)
        pal = set(normalizar(x.get('productName') or '').split())
        if alvo and len(alvo & pal) / len(alvo) >= 0.6 and not bloqueado(x.get('productName')):
            return f"{x['shopId']}:{x['itemId']}"
    return ''


def processar_achado(texto, fonte, midia=None):
    """Oferta/cupom achado num grupo ou canal monitorado → post para você aprovar no FILA POST ZAP (com o SEU link)."""
    stat_monitor(fonte, msgs=1)
    jid_fila, inst_fila = destino_fila()
    if not jid_fila:
        return
    if re.search(r'chat\.whatsapp\.com/|t\.me/(?:joinchat|\+)', texto) or re.search(r'(?i)convidar uma amiga|nossos grupos', texto):
        return                                   # convite pros grupos de outra pessoa: não é oferta nem cupom
    links = [u.rstrip('.,)') for u in re.findall(r'https?://\S+', texto)]
    achados = []                                 # qualquer link (encurtadores, sites de divulgação) que termine na Shopee
    for url in links[:4]:
        try:
            ids = ids_do_link_shopee(url)
        except Exception:
            ids = ''
        if ids:
            achados.append(ids)
    pelo_nome = False
    if not achados and CUPOM_RE.search(texto):
        ids = produto_pelo_nome(texto)
        if ids:
            achados, pelo_nome = [ids], True
    shopee = achados
    for ids in achados[:3]:
        try:
            with _lock, db() as c:
                if c.execute('SELECT 1 FROM monitor_vistos WHERE chave=?', (ids,)).fetchone():
                    continue
                c.execute('INSERT INTO monitor_vistos VALUES (?,?)', (ids, agora().isoformat()))
            p = montar_post_do_link(f'https://shopee.com.br/product/{ids.replace(":", "/")}')
            p['origem'] = 'monitor'
            if cupom_do_texto(texto) and not p.get('cupom'):
                p['cupom'] = cupom_do_texto(texto)
            grupos = grupos_ativos()
            with _lock, db() as c:
                cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, link, texto, grupos, criado_em, dados, pedido_por, '
                                'pedido_inst) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                ('monitor', p.get('chave'), p['produto'], p.get('preco'), p['link'], montar_texto(p),
                                 json.dumps(grupos), agora().isoformat(), json.dumps(p), jid_fila, inst_fila))
                fid = cur.lastrowid
            mostrar_previa(inst_fila, jid_fila, fid)
            stat_monitor(fonte, achados=1)
            extra = ' (achei o produto pelo nome: confira se é o mesmo)' if pelo_nome else ''
            responder(inst_fila, jid_fila, f"🔭 *Achado #{fid}* em {fonte} · já com o SEU link de afiliado{extra}\n\n{MENU_CURTO}", fid=fid)
        except ValueError:
            continue
        except Exception as e:
            log.warning(f'Monitor: {e}')
    if not shopee and CUPOM_RE.search(texto):     # cupom/bug sem link da Shopee: vira aviso para revisar (sem links de outros)
        limpo = re.sub(r'https?://\S+', '', texto).strip()
        dados_c = {}
        if midia:                                # mantém a foto da mensagem original pra você conseguir avaliar
            try:
                r = evo('POST', f"/chat/getBase64FromMediaMessage/{midia['inst']}", {'message': {'key': midia['key']}, 'convertToMp4': False}, timeout=120)
                if r.get('base64'):
                    MIDIA_DIR.mkdir(exist_ok=True)
                    arq = MIDIA_DIR / f"cupom_{int(time.time() * 1000)}.b64"
                    arq.write_text(r['base64'])
                    dados_c = {'midia': str(arq), 'midia_tipo': 'image', 'mimetype': r.get('mimetype') or 'image/jpeg'}
            except Exception as e:
                log.warning(f'Monitor: foto do cupom: {e}')
        chave = 'cupom:' + hashlib.sha1(limpo.lower().encode()).hexdigest()[:16]
        with _lock, db() as c:
            if c.execute('SELECT 1 FROM monitor_vistos WHERE chave=?', (chave,)).fetchone():
                return
            c.execute('INSERT INTO monitor_vistos VALUES (?,?)', (chave, agora().isoformat()))
            cur = c.execute('INSERT INTO fila (origem, chave, produto, texto, grupos, criado_em, dados, pedido_por, pedido_inst) '
                            'VALUES (?,?,?,?,?,?,?,?,?)', ('aviso', chave, '🎟️ Cupom achado', limpo[:1500], json.dumps(grupos_ativos()),
                                                           agora().isoformat(), json.dumps(dados_c), jid_fila, inst_fila))
            fid = cur.lastrowid
        stat_monitor(fonte, cupons=1)
        responder(inst_fila, jid_fila, f"🎟️ *Cupom achado #{fid}* em {fonte} (revise antes: cupom exclusivo de outro afiliado não funciona "
                                       f"para o seu público)\n\n{limpo[:700]}\n\n{MENU_AVISO}", fid=fid)


def ler_telegram(canal):
    """Canal PÚBLICO do Telegram (t.me/s/<canal>): devolve [(id, texto)] dos posts recentes."""
    import html as h
    canal = canal.strip().lstrip('@').split('/')[-1]
    req = urllib.request.Request(f'https://t.me/s/{canal}', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        pg = r.read().decode('utf-8', 'ignore')
    posts = []
    for m in re.finditer(r'data-post="([^"]+)".*?<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', pg, re.S):
        bruto = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>.*?</a>', r' \1 ', m.group(2))
        bruto = re.sub(r'<br\s*/?>', '\n', bruto)
        posts.append((m.group(1), h.unescape(re.sub(r'<[^>]+>', '', bruto)).strip()))
    return posts


def hora_da_enquete():
    """Horário de hoje: fixo, ou sorteado (uma vez por dia) na janela da noite, longe da mensagem da noite."""
    e = eng_cfg()
    if e.get('enquete_hora_modo') != 'aleatorio':
        return e['enquete_hora']
    chave = f"enq_hora_{agora().date().isoformat()}"
    if get_cfg(chave):
        return get_cfg(chave)
    a, b = e.get('enquete_janela') or ['19:00', '22:00']
    m = lambda t: int(t[:2]) * 60 + int(t[3:5])
    noite = m(e.get('noite_hora', '21:00')) if e.get('noite_ativo') else -999
    opcoes = [x for x in range(m(a), max(m(a) + 1, m(b)), 5) if abs(x - noite) >= 40] or [m(a)]
    x = random.choice(opcoes)
    h = f'{x // 60:02d}:{x % 60:02d}'
    set_cfg(chave, h)
    return h


_tg_ultimo = [0.0]


DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']


def agenda_de_hoje():
    """📅 O que sai hoje (para o topo da aba): hora, o quê, ligado e se já foi gerado."""
    e = eng_cfg()
    hoje = agora().date().isoformat()
    itens = [('☀️ Bom dia', e['msg_hora'], e['msg_ativo'], 'msg'),
             ('📊 Enquete', hora_da_enquete(), e['enquete_ativo'], 'enq'),
             ('🌙 Boa noite', e['noite_hora'], e['noite_ativo'], 'noite')]
    conv_hoje = agora().weekday() in (e.get('convite_dias') or [])
    if e.get('convite_ativo') and e.get('inbox_ativo'):
        if conv_hoje:
            itens.append(('💌 Convite de pedidos', e.get('convite_hora', '19:30'), True, 'convite'))
    if e.get('amiga_ativo') and agora().weekday() in (e.get('amiga_dias') or []):
        itens.append(('👭 Convide uma amiga', e.get('amiga_hora', '12:30'), True, 'amiga'))
    out = [{'nome': n, 'hora': h, 'ativo': bool(a), 'feito': bool(get_cfg(f'eng_{k}_{hoje}')), 'tipo': k} for n, h, a, k in itens]
    prox = ''
    if e.get('convite_ativo') and e.get('inbox_ativo') and not conv_hoje and e.get('convite_dias'):
        d = agora().weekday()
        prox = DIAS_SEMANA[min(e['convite_dias'], key=lambda x: (x - d) % 7)]
    return {'itens': sorted(out, key=lambda x: x['hora']), 'convite_proximo': prox}


def agenda_engajamento():
    while True:
        try:
            e = eng_cfg()
            hoje, hm = agora().date().isoformat(), agora().strftime('%H:%M')
            for ativo, hora, nome, func in ((e['msg_ativo'], e['msg_hora'], 'msg', rodar_mensagem_do_dia),
                                            (e['noite_ativo'], e['noite_hora'], 'noite', lambda: rodar_mensagem_do_dia('noite')),
                                            (e['enquete_ativo'], hora_da_enquete(), 'enq', rodar_enquete),
                                            (e.get('convite_ativo') and e.get('inbox_ativo') and agora().weekday() in (e.get('convite_dias') or []),
                                             e.get('convite_hora', '19:30'), 'convite', rodar_convite_pedidos),
                                            (e.get('amiga_ativo') and agora().weekday() in (e.get('amiga_dias') or []),
                                             e.get('amiga_hora', '12:30'), 'amiga', rodar_convite_amiga)):
                marca = f'eng_{nome}_{hoje}'
                if ativo and hm >= hora and not get_cfg(marca):
                    set_cfg(marca, '1')
                    try:
                        func()
                    except Exception as ex:
                        log.warning(f'Engajamento ({nome}): {ex}')
            if e.get('monitor_ativo') and e.get('monitor_telegram') and time.time() - _tg_ultimo[0] >= 540:   # a cada ~10 min
                _tg_ultimo[0] = time.time()
                for canal in e['monitor_telegram']:
                    try:
                        num = lambda pid: int(re.sub(r'\D', '', pid.split('/')[-1]) or 0)
                        ultimo = int(get_cfg(f'tg_{canal}', '0') or 0)
                        posts = ler_telegram(canal)
                        novos = [p for p in posts if num(p[0]) > ultimo] if ultimo else posts[-3:]   # 1ª vez: só os 3 últimos
                        for pid, txt in novos[-10:]:
                            processar_achado(txt, f'Telegram @{canal}')
                        if posts:
                            set_cfg(f'tg_{canal}', str(max(num(p[0]) for p in posts)))
                        else:
                            stat_monitor(f'Telegram @{canal.strip().lstrip("@")}', erro='nenhum post lido (canal privado ou nome errado?)')
                        if not novos and posts:
                            stat_monitor(f'Telegram @{canal.strip().lstrip("@")}')
                    except Exception as ex:
                        stat_monitor(f'Telegram @{canal.strip().lstrip("@")}', erro=str(ex)[:120])
                        log.warning(f'Telegram {canal}: {ex}')
        except Exception:
            log.exception('Engajamento')
        time.sleep(60)


# ---------------------------------------------------------------- status dos chips

def status_cfg():
    d = {'ativo': False, 'max_dia': 5, 'ofertas': True, 'engajamento': True,
         'lembrete_ativo': True, 'lembrete_cada': 5,
         'lembrete_texto': '📲 *Salve este número nos seus contatos* pra ver as ofertas relâmpago no Status!'}
    d.update(get_json('status', {}))
    if not d.get('chips'):                       # padrão: todos os chips
        d['chips'] = instancias()
    return d


def contatos_status(inst):
    """Quem pode ver o Status: contatos do chip + membros dos grupos onde ele está (só vê quem também salvou o número).
    Guarda a lista por 6h (buscar os membros de todos os grupos demora)."""
    cache = get_json(f'status_lista_{inst}', {})
    if cache.get('ts', 0) > time.time() - 6 * 3600 and cache.get('jids'):
        return cache['jids']
    jids = set()
    try:
        for ct in evo('POST', f'/chat/findContacts/{inst}', {}, timeout=60) or []:
            j = ct.get('remoteJid') or ct.get('id') or ''
            if j.endswith('@s.whatsapp.net'):
                jids.add(j)
    except Exception:
        pass
    try:
        for g in evo('GET', f'/group/fetchAllGroups/{inst}?getParticipants=true', timeout=240) or []:
            for pt in g.get('participants') or []:
                j = pt.get('phoneNumber') or pt.get('id') or ''
                if j.endswith('@s.whatsapp.net'):
                    jids.add(j)
    except Exception:
        pass
    set_cfg(f'status_lista_{inst}', json.dumps({'ts': time.time(), 'jids': sorted(jids)}))
    return sorted(jids)


def enviar_status(inst, corpo):
    """Evolution v2: /message/sendStatus. Manda a lista de quem pode ver (statusJidList); sem ela, alguns servidores
    não entregam a ninguém."""
    lista = contatos_status(inst)
    payload = dict(corpo, allContacts=not lista, statusJidList=lista)
    r = evo('POST', f'/message/sendStatus/{inst}', payload, timeout=180)
    return f'ok · {len(lista)} contato(s) na lista' + ('' if lista else ' (allContacts)')


AVISO_SALVAR = ('📲 *Novidade no grupo!*\n\n'
                'Agora tem *oferta relâmpago no Status* deste número ⚡ — umas aparecem só lá e acabam rapidinho!\n\n'
                'Pra ver, é só *salvar este número nos seus contatos* (pode chamar de "Achadinhos 💜"). '
                'Sem salvar, o WhatsApp não mostra o Status pra você.\n\n'
                'Depois é só abrir a aba *Atualizações* e ficar de olho! 👀')


def rodar_aviso_salvar():
    return criar_post_engajamento('aviso', AVISO_SALVAR, {'so_status': True}, '📲 Salve este número')


def testar_status():
    for inst in status_cfg().get('chips') or instancias():
        if estado_chip(inst) != 'open':
            marcar_status(inst, False, 'teste', 'chip desconectado')
            continue
        marcar_status(inst, None, 'teste', 'postando…')
        corpo = {'type': 'text', 'content': f'💜 Teste do PostZap · {data_sub(agora())} {agora().strftime("%H:%M")}',
                 'backgroundColor': '#7c3aed', 'font': 1}
        try:
            marcar_status(inst, True, 'teste', enviar_status(inst, corpo))
        except Exception as e:
            marcar_status(inst, False, 'teste', 'falhou: ' + str(e)[:300])


def marcar_status(inst, ok, oque, info):
    st = get_json('status_ultimo', {})
    st[inst] = {'quando': agora().strftime('%Y-%m-%dT%H:%M'), 'ok': ok, 'oque': oque, 'info': str(info)[:300]}
    set_cfg('status_ultimo', json.dumps(st, ensure_ascii=False))


def postar_status(item):
    """Depois de sair nos grupos, a oferta (ou a mensagem do dia) vai também para o Status dos chips conectados."""
    cfg = status_cfg()
    dados = json.loads(item.get('dados') or '{}')
    aviso = item.get('origem') == 'aviso'
    if (aviso and not cfg.get('engajamento')) or (not aviso and not cfg.get('ofertas')) or dados.get('enquete'):
        return
    img = ''
    if dados.get('midia') and Path(dados['midia']).exists() and dados.get('midia_tipo', 'image') == 'image':
        img = Path(dados['midia']).read_text()
    elif dados.get('imagem'):
        img = dados['imagem']
    texto = item.get('texto') or ''
    hoje = agora().date().isoformat()
    for inst in instancias():
        if inst not in cfg.get('chips', []) or estado_chip(inst) != 'open':
            continue
        chave = f'status_{inst}_{hoje}'
        feitos = int(get_cfg(chave, '0') or 0)
        if feitos >= int(cfg.get('max_dia', 5)):
            continue
        corpo = ({'type': 'image', 'content': img, 'caption': texto[:700], 'allContacts': True} if img else
                 {'type': 'text', 'content': texto[:650], 'backgroundColor': '#7c3aed', 'font': 1, 'allContacts': True})
        try:
            resp = enviar_status(inst, corpo)
            set_cfg(chave, str(feitos + 1))
            marcar_status(inst, True, f"post #{item.get('id')}", resp)
            log.info(f"Status do {inst}: post #{item.get('id')}")
        except Exception as e:
            marcar_status(inst, False, f"post #{item.get('id')}", str(e)[:300])
            log.warning(f'Status do {inst}: {e}')


# ---------------------------------------------------------------- vendas por post e grupo (relatório da Shopee)

def coletar_vendas(dias=10):
    """Lê o relatório de conversões da Shopee e liga cada venda ao post e ao grupo pelos Sub IDs do PostZap."""
    agora_ts = int(time.time())
    inicio = agora_ts - dias * 86400
    scroll, total = None, 0
    with db() as c:
        gid_jid = {str(r[0]): r[1] for r in c.execute('SELECT rowid, jid FROM grupos')}
    for _ in range(40):
        arg = f', scrollId: "{scroll}"' if scroll else ''
        d = shopee_gql('{conversionReport(purchaseTimeStart: %d, purchaseTimeEnd: %d, limit: 100%s){nodes{purchaseTime '
                       'conversionId utmContent orders{orderId orderStatus items{itemId shopId itemName actualAmount itemCommission}}}'
                       'pageInfo{hasNextPage scrollId}}}' % (inicio, agora_ts, arg))['conversionReport']
        for n in d.get('nodes') or []:
            partes = [p for p in (n.get('utmContent') or '').split('-') if p]
            if not partes or partes[0] != CFG['sub_id']:
                continue                         # venda que não veio do PostZap
            g = next((p[1:] for p in partes[1:] if re.fullmatch(r'g\d+', p)), None)
            jid = gid_jid.get(g) if g else None
            quando = datetime.fromtimestamp(int(n.get('purchaseTime') or 0), BRT).isoformat()
            for o in n.get('orders') or []:
                for it in o.get('items') or []:
                    chave_item = f"{it.get('shopId')}:{it.get('itemId')}"
                    with db() as c:              # o post desse produto que foi para esse grupo (o mais recente antes da compra)
                        q = ('SELECT f.id FROM fila f JOIN envios e ON e.fila_id=f.id AND e.ok=1 WHERE f.chave=? '
                             + ('AND e.jid=? ' if jid else '') + 'AND e.quando<=? ORDER BY e.quando DESC LIMIT 1')
                        r = c.execute(q, (chave_item, jid, quando) if jid else (chave_item, quando)).fetchone()
                    with _lock, db() as c:
                        c.execute('INSERT OR REPLACE INTO vendas VALUES (?,?,?,?,?,?,?,?,?,?)',
                                  (f"{o.get('orderId')}:{chave_item}", r[0] if r else None, jid, chave_item, it.get('itemName', '')[:150],
                                   num(it.get('actualAmount')), num(it.get('itemCommission')), o.get('orderStatus', ''), quando,
                                   '-'.join(partes)))
                    total += 1
        pi = d.get('pageInfo') or {}
        if not pi.get('hasNextPage') or not pi.get('scrollId'):
            break
        scroll = pi['scrollId']
        time.sleep(3)
    set_cfg('vendas_atualizado', agora().isoformat())
    return total


def agenda_vendas():
    n = 0
    while True:
        if n % 3 == 0:                           # a cada ~6h: tamanho de cada grupo (para entradas/saídas)
            try:
                atualizar_grupos()
            except Exception as e:
                log.warning(f'Tamanho dos grupos: {e}')
        n += 1
        try:
            coletar_vendas()
        except Exception as e:
            log.warning(f'Vendas da Shopee: {e}')
        time.sleep(2 * 3600)                     # a cada 2 horas


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
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pg = pagina_link(p[3:], (qs.get('g') or [None])[0], self.headers.get('User-Agent', ''))
            if isinstance(pg, tuple):
                self.send_response(302)
                self.send_header('Location', pg[1])
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return
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
                        r['fila'] = e_grupo_fila(r['nome'])
                        r['chips'] = [{'chip': x[0], 'admin': x[1]} for x in
                                      c.execute('SELECT instancia, admin FROM grupo_chips WHERE jid=?', (r['jid'],))]
                return self.send_json({'grupos': rows, 'listas': listas()})
            if p == '/api/divulgador':
                return self.send_json(dict(divulgador_cfg(), prontos=FOCOS, temas_pai=temas_pai(), nichos=NICHOS))
            if p == '/api/engajamento':
                with db() as c:
                    pedidos = [dict(r) for r in c.execute('SELECT texto, resultado, quando FROM pedidos_inbox ORDER BY id DESC LIMIT 30')]
                pq, po = enquete_de_hoje()
                return self.send_json(dict(eng_cfg(), votos=resultado_votos(7), pedidos=pedidos, enquete_hoje={'pergunta': pq, 'opcoes': po},
                                           link_pedido=link_pedido() if eng_cfg().get('inbox_ativo') else '',
                                           chips=[{'chip': i, **{k: v for k, v in historico_chip(i).items() if k == 'eventos'}} for i in instancias()],
                                           enquete_hora_hoje=hora_da_enquete(), convite_imgs=[Path(x).name for x in imagens_convite()], convite_suas=bool(get_json('convite_imgs', [])), monitor_stat=get_json('monitor_stat', {}), agenda_hoje=agenda_de_hoje(), amiga_img=AMIGA_IA.exists(), amiga_img_status=get_cfg('amiga_img_status', ''), grupos_admin=[{'jid': j, 'nome': n} for j, n in _grupos_admin()], amiga_lista=[j for j, _ in grupos_para_amiga()], banco_padrao={'dia': BANCO_DIA, 'noite': BANCO_NOITE},
                                           pacotes=[{'pergunta': a, 'opcoes': o} for a, o in PACOTES_ENQUETE],
                                           opcoes_possiveis=NICHOS + focos_nomes()))
            if p == '/api/historico':
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                return self.send_json(historico((qs.get('periodo') or ['7'])[0], (qs.get('mes') or [''])[0]))
            if p == '/api/amiga_img':
                import base64
                if AMIGA_IA.exists():
                    t = AMIGA_IA.read_text()
                    corpo = base64.b64decode(t)
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg' if t.startswith('/9j') else 'image/png')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
            if p.startswith('/api/convite_img/'):       # prévia das imagens fixas do convite
                imgs = imagens_convite()
                n = int(re.sub(r'\D', '', p.rsplit('/', 1)[-1]) or 0)
                if n < len(imgs):
                    corpo = Path(imgs[n]).read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png' if imgs[n].endswith('.png') else 'image/jpeg')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
            if p.startswith('/api/midia/'):              # miniatura do card: imagem que vai sair no post
                it = item_fila(int(re.sub(r'\D', '', p.rsplit('/', 1)[-1]) or 0))
                dados = json.loads((it or {}).get('dados') or '{}')
                if dados.get('midia') and Path(dados['midia']).exists():
                    import base64
                    corpo = base64.b64decode(Path(dados['midia']).read_text())
                    self.send_response(200)
                    self.send_header('Content-Type', dados.get('mimetype') or 'image/png')
                    self.send_header('Cache-Control', 'max-age=86400')
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
                if dados.get('imagem'):
                    self.send_response(302)
                    self.send_header('Location', dados['imagem'])
                    self.end_headers()
                    return
                return self.send_json({'erro': 'sem imagem'}, 404)
            if p == '/api/cupons':
                with db() as c:
                    return self.send_json({'cupons': [dict(r) for r in c.execute('SELECT * FROM cupons ORDER BY ativo DESC, id DESC')]})
            if p == '/api/fila':
                with db() as c:
                    rows = [dict(r) for r in c.execute(
                        "SELECT * FROM fila WHERE status!='descartado' ORDER BY id DESC LIMIT 200")]
                    for r in rows:                      # cliques de pessoas, total e por grupo
                        cod = (r.get('link') or '').rsplit('/l/', 1)[-1] if '/l/' in (r.get('link') or '') else ''
                        r['cliques'] = c.execute('SELECT COUNT(*) FROM cliques WHERE codigo=?', (cod,)).fetchone()[0] if cod else 0
                        r['cliques_grupo'] = [dict(x) for x in c.execute(
                            "SELECT COALESCE(g.nome, '(sem grupo)') nome, "
                            'COUNT(*) n FROM cliques k LEFT JOIN grupos g '
                            'ON g.rowid=k.grupo WHERE k.codigo=? GROUP BY k.grupo ORDER BY n DESC', (cod,))] if cod else []
                        r['sub_ids'] = (json.loads(r.get('dados') or '{}') or {}).get('sub_ids')
                        r['nicho'] = nicho_do_item(r) if r.get('origem') != 'aviso' else ''
                        r['focos'] = focos_do_item(r) if r.get('origem') != 'aviso' else []
                        _d = json.loads(r.get('dados') or '{}')
                        r['thumb'] = bool((_d.get('midia') and _d.get('midia_tipo', 'image') == 'image') or
                                          (_d.get('imagem') and modo_link() != 'previa'))
                        r['grupos_enviados'] = c.execute('SELECT COUNT(DISTINCT jid) FROM envios WHERE fila_id=? AND ok=1',
                                                         (r['id'],)).fetchone()[0]
                with db() as c:
                    descartados = [dict(r) for r in c.execute(
                        "SELECT f.id, f.produto, f.criado_em, (SELECT COUNT(*) FROM envios e WHERE e.fila_id=f.id AND e.ok=1) enviados "
                        "FROM fila f WHERE status='descartado' ORDER BY id DESC LIMIT 40")]
                return self.send_json({'fila': rows, 'descartados': descartados, 'pausado': get_cfg('pausado') == '1'})
            if p == '/api/config':
                return self.send_json({'modelo': get_cfg('modelo', MODELO_PADRAO), 'modelos': modelos(),
                                       'estilo_loja': get_json('estilo_loja', {}), 'lojas': LOJAS_NOMES,
                                       'chamadas': get_json('chamadas', {}), 'chamada_modo': get_cfg('chamada_modo', 'ia'),
                                       'ctas': get_json('ctas', CTAS_PADRAO), 'cta_modo': get_cfg('cta_modo', 'frases'),
                                       'temas_pai': temas_pai(), 'status': status_cfg(), 'chips_todos': instancias(), 'chips_num': {i: get_cfg(f'numero_{i}') for i in instancias()}, 'status_ultimo': get_json('status_ultimo', {}), 'modo_link': modo_link(),
                                       'ritmo': ritmo(), 'limite_hoje': limite_hoje(), 'nichos': NICHOS, 'focos': focos_nomes(),
                                       'nichos_agora': nichos_da_hora(), 'grupos_ativos': len(grupos_ativos()),
                                       'proxima_saida': proxima_saida().isoformat(), 'repetir_dias': CFG['repetir_dias']})
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
        if p == '/api/montar':
            return self.send_json({'texto': montar_texto(b)})
        if p == '/api/mensagens':                       # estilos, estilo por loja e frases de chamada
            if isinstance(b.get('modelos'), dict) and b['modelos']:
                m = {k.strip(): v for k, v in b['modelos'].items() if k.strip() and v.strip()}
                m.setdefault('Padrão', MODELO_PADRAO)
                set_cfg('modelos', json.dumps(m, ensure_ascii=False))
            if isinstance(b.get('estilo_loja'), dict):
                set_cfg('estilo_loja', json.dumps(b['estilo_loja'], ensure_ascii=False))
            if isinstance(b.get('chamadas'), dict):
                set_cfg('chamadas', json.dumps(b['chamadas'], ensure_ascii=False))
            if b.get('modo_link') in ('direto', 'previa'):
                set_cfg('modo_link', b['modo_link'])
            if isinstance(b.get('ctas'), list):
                set_cfg('ctas', json.dumps([c.strip() for c in b['ctas'] if c.strip()][:40], ensure_ascii=False))
            if b.get('cta_modo') in ('frases', 'ia', 'misto', 'nenhum'):
                set_cfg('cta_modo', b['cta_modo'])
            if b.get('chamada_modo') in ('ia', 'frases', 'misto'):
                set_cfg('chamada_modo', b['chamada_modo'])
            return self.send_json({'ok': True})
        if p == '/api/listas/salvar':
            nome = (b.get('nome') or '').strip()
            if not nome:
                return self.send_json({'erro': 'Dê um nome para a lista.'}, 400)
            with _lock, db() as c:
                if b.get('id'):
                    c.execute('UPDATE listas SET nome=?, grupos=? WHERE id=?', (nome, json.dumps(b.get('grupos') or []), b['id']))
                else:
                    c.execute('INSERT INTO listas (nome, grupos) VALUES (?,?)', (nome, json.dumps(b.get('grupos') or [])))
            return self.send_json({'ok': True})
        if p == '/api/listas/excluir':
            with _lock, db() as c:
                c.execute('DELETE FROM listas WHERE id=?', (b['id'],))
            return self.send_json({'ok': True})
        if p == '/api/cupons/salvar':
            if not (b.get('codigo') or '').strip():
                return self.send_json({'erro': 'Informe o código do cupom.'}, 400)
            with _lock, db() as c:
                vals = (b.get('loja') or 'Todas', b['codigo'].strip().upper(), (b.get('texto') or '').strip(),
                        b.get('validade') or '', 1 if b.get('ativo', True) else 0)
                if b.get('id'):
                    c.execute('UPDATE cupons SET loja=?, codigo=?, texto=?, validade=?, ativo=? WHERE id=?', vals + (b['id'],))
                else:
                    c.execute('INSERT INTO cupons (loja, codigo, texto, validade, ativo) VALUES (?,?,?,?,?)', vals)
            return self.send_json({'ok': True})
        if p == '/api/cupons/excluir':
            with _lock, db() as c:
                c.execute('DELETE FROM cupons WHERE id=?', (b['id'],))
            return self.send_json({'ok': True})
        if p == '/api/ritmo':
            r = ritmo()
            if isinstance(b.get('nichos_horario'), list):
                r['nichos_horario'] = sorted(
                    [{'de': f['de'], 'ate': f['ate'], 'nichos': [n for n in f.get('nichos', []) if n in NICHOS + focos_nomes()]}
                     for f in b['nichos_horario'] if re.fullmatch(r'\d{2}:\d{2}', f.get('de', '')) and
                     re.fullmatch(r'\d{2}:\d{2}', f.get('ate', ''))], key=lambda f: f['de'])
            for k in ('nichos_ativo', 'nicho_estrito'):
                if k in b:
                    r[k] = bool(b[k])
            for k in ('inicio', 'fim'):
                if re.fullmatch(r'\d{2}:\d{2}', str(b.get(k, ''))):
                    r[k] = b[k]
            for k in ('rajada', 'pausa', 'entre_grupos'):
                v = b.get(k)
                if isinstance(v, list) and len(v) == 2 and all(str(x).isdigit() for x in v):
                    a1, a2 = sorted(int(x) for x in v)
                    r[k] = [max(1, a1), max(1, a2)]
            for k in ('aquec_inicio', 'aquec_passo', 'aquec_max', 'trava'):
                if str(b.get(k, '')).isdigit():
                    r[k] = int(b[k])
            if b.get('reiniciar_aquecimento'):
                r['aquec_desde'] = agora().date().isoformat()
            set_cfg('ritmo', json.dumps(r))
            return self.send_json({'ok': True, 'limite_hoje': limite_hoje(r)})
        if p == '/api/divulgador':
            d = divulgador_cfg()
            for k in ('ativo',):
                if k in b:
                    d[k] = bool(b[k])
            if b.get('modo') in ('aprovar', 'automatico'):
                d['modo'] = b['modo']
            if isinstance(b.get('horarios'), list):
                d['horarios'] = sorted(h for h in b['horarios'] if re.fullmatch(r'\d{2}:\d{2}', h))
            if isinstance(b.get('focos_ativos'), list):
                d['focos_ativos'] = [f.strip() for f in b['focos_ativos'] if f.strip()]
            if isinstance(b.get('palavras_foco'), dict):         # inclui temas novos criados por ela (máx. 20)
                d['palavras_foco'] = {f.strip()[:40]: [w.strip() for w in v if w.strip()][:20]
                                      for f, v in list(b['palavras_foco'].items())[:20] if f.strip()}
                for n, v in TEMAS_PRONTOS.items():
                    d['palavras_foco'].setdefault(n, list(v[1]))
                d['focos_ativos'] = [f for f in d['focos_ativos'] if f in d['palavras_foco']]
            if isinstance(b.get('temas_pai'), dict):
                d['temas_pai'] = {k: v for k, v in b['temas_pai'].items() if v in NICHOS and k not in TEMAS_PRONTOS}
            if str(b.get('peso_foco', '')).replace('.', '', 1).isdigit():
                d['peso_foco'] = min(5.0, max(1.0, float(b['peso_foco'])))
            if isinstance(b.get('palavras'), list):
                d['palavras'] = [x.strip() for x in b['palavras'] if x.strip()][:40]
            for k, tipo in (('por_rodada', int), ('comissao_min', float), ('comissao_min_moda', float), ('nota_min', float), ('vendas_min', int),
                            ('nao_repetir_dias', int)):
                if str(b.get(k, '')).replace('.', '', 1).replace(',', '', 1).isdigit():
                    d[k] = tipo(str(b[k]).replace(',', '.'))
            d['comissao_min'] = max(9.0, d['comissao_min'])          # piso do Garimpo: nunca abaixo de R$ 9
            d['comissao_min_moda'] = max(1.0, d.get('comissao_min_moda', 4.0))
            set_cfg('divulgador', json.dumps(d, ensure_ascii=False))
            return self.send_json({'ok': True})
        if p == '/api/divulgador/rodar':
            n, msg = rodar_divulgador(manual=True)
            return self.send_json({'feitos': n, 'msg': msg})
        if p == '/api/divulgador/testar':
            return self.send_json({'produtos': [{'produto': n['productName'], 'comissao': br(n['comissao_rs']), 'focos': n.get('focos', []),
                                                 'nicho': classificar_nicho(n['productName'], n['palavra']),
                                                 'vendas': n.get('sales'), 'nota': n.get('ratingStar'), 'palavra': n['palavra'],
                                                 'preco': br(n.get('priceMin'))} for n in minerar()]})
        if p == '/api/engajamento':
            e = eng_cfg()
            for k in ('msg_ativo', 'msg_imagem', 'noite_ativo', 'noite_imagem', 'enquete_ativo', 'aprovar', 'inbox_ativo', 'monitor_ativo', 'convite_ativo', 'amiga_ativo'):
                if k in b:
                    e[k] = bool(b[k])
            if b.get('enquete_hora_modo') in ('aleatorio', 'fixo'):
                e['enquete_hora_modo'] = b['enquete_hora_modo']
            if isinstance(b.get('enquete_janela'), list) and all(re.fullmatch(r'\d{2}:\d{2}', str(x)) for x in b['enquete_janela'][:2]):
                e['enquete_janela'] = sorted(b['enquete_janela'][:2])
            if b.get('enquete_modo') in ('rodizio', 'fixa'):
                e['enquete_modo'] = b['enquete_modo']
            if str(b.get('enquete_troca_dias', '')).isdigit():
                e['enquete_troca_dias'] = max(1, min(14, int(b['enquete_troca_dias'])))
            if isinstance(b.get('amiga_dias'), list):
                e['amiga_dias'] = sorted({int(x) for x in b['amiga_dias'] if str(x).isdigit() and int(x) < 7})
            if isinstance(b.get('amiga_grupos'), list):
                e['amiga_grupos'] = [str(x) for x in b['amiga_grupos'] if str(x).endswith('@g.us')][:40]
            if isinstance(b.get('convite_dias'), list):
                e['convite_dias'] = sorted({int(x) for x in b['convite_dias'] if str(x).isdigit() and int(x) < 7})
            for k in ('banco_dia', 'banco_noite'):
                if isinstance(b.get(k), list):
                    e[k] = [str(x).strip()[:1000] for x in b[k] if str(x).strip()][:30]
            for k in ('msg_hora', 'noite_hora', 'enquete_hora', 'convite_hora', 'amiga_hora'):
                if re.fullmatch(r'\d{2}:\d{2}', str(b.get(k, ''))):
                    e[k] = b[k]
            if b.get('enquete_pergunta'):
                e['enquete_pergunta'] = str(b['enquete_pergunta'])[:250]
            for k, lim in (('enquete_opcoes', 12), ('monitor_grupos', 50), ('monitor_telegram', 20)):
                if isinstance(b.get(k), list):
                    e[k] = [str(x).strip()[:100] for x in b[k] if str(x).strip()][:lim]
            if re.fullmatch(r'[a-z,]{3,40}', str(b.get('imagem_ordem', ''))):
                e['imagem_ordem'] = b['imagem_ordem']
            if 'inbox_gatilho' in b:
                e['inbox_gatilho'] = str(b['inbox_gatilho'])[:80]
            if isinstance(b.get('inbox_chips'), list):
                e['inbox_chips'] = [x for x in b['inbox_chips'] if x in instancias()]
            if str(b.get('inbox_silencio_h', '')).isdigit():
                e['inbox_silencio_h'] = int(b['inbox_silencio_h'])
            for k in ('inbox_max_dia', 'peso_votos'):
                if str(b.get(k, '')).replace('.', '', 1).isdigit():
                    e[k] = float(b[k]) if k == 'peso_votos' else int(b[k])
            set_cfg('engajamento', json.dumps(e, ensure_ascii=False))
            return self.send_json({'ok': True})
        if p == '/api/engajamento/convite_img':          # trocar a imagem fixa do convite (ou voltar às prontas)
            import base64
            if b.get('padrao'):
                for x in get_json('convite_imgs', []):
                    Path(x).unlink(missing_ok=True)
                set_cfg('convite_imgs', '[]')
                return self.send_json({'ok': True})
            m = re.match(r'data:image/(png|jpeg|jpg|webp);base64,(.+)', str(b.get('imagem', '')), re.S)
            if not m:
                return self.send_json({'erro': 'mande uma imagem PNG ou JPG'}, 400)
            dados_img = base64.b64decode(m.group(2))
            if len(dados_img) > 5_000_000:
                return self.send_json({'erro': 'imagem grande demais (máx. 5 MB)'}, 400)
            MIDIA_DIR.mkdir(exist_ok=True)
            arq = MIDIA_DIR / f"convite_sua_{int(time.time())}.{'png' if m.group(1) == 'png' else 'jpg'}"
            arq.write_bytes(dados_img)
            lista = [] if not b.get('somar') else [x for x in get_json('convite_imgs', []) if Path(x).exists()]
            if not b.get('somar'):
                for x in get_json('convite_imgs', []):
                    Path(x).unlink(missing_ok=True)
            set_cfg('convite_imgs', json.dumps(lista + [str(arq)]))
            return self.send_json({'ok': True})
        if p == '/api/engajamento/teste_ia':               # diagnóstico: texto e imagem, com o motivo de cada falha
            r = {}
            try:
                r['texto'] = 'ok: ' + chat_ia('Responda só: tudo certo! 💜', 60)
            except Exception as ex:
                r['texto'] = 'falhou: ' + str(ex)[:300]
            img = imagem_ia(prompt_imagem('dia', 'teste'))
            r['imagem'] = f'ok (imagem gerada pelo {_ultimo_gerador[0]})' if img else 'falhou: ' + (_ultimo_erro_imagem[0] or 'erro desconhecido')[:400]
            r['chave'] = 'encontrada' if chave_openai() else 'NÃO encontrada'
            r['gemini'] = 'encontrada' if (chave_env('GEMINI_API_KEY') or chave_env('GOOGLE_API_KEY')) else 'NÃO encontrada'
            r['previa'] = ('data:' + ('image/jpeg' if img.startswith('/9j') else 'image/png') + ';base64,' + img) if img else ''
            return self.send_json(r)
        if p == '/api/engajamento/amiga_img':           # gera outra imagem das amigas (em segundo plano)
            def _g():
                try:
                    set_cfg('amiga_img_status', 'ok: gerada pelo ' + gerar_imagem_amiga())
                except Exception as ex:
                    set_cfg('amiga_img_status', 'falhou: ' + str(ex)[:200])
            set_cfg('amiga_img_status', 'gerando')
            threading.Thread(target=_g, daemon=True).start()
            return self.send_json({'ok': True})
        if p == '/api/engajamento/agora':
            fid = (rodar_mensagem_do_dia() if b.get('tipo') == 'msg' else rodar_mensagem_do_dia('noite') if b.get('tipo') == 'noite'
                   else rodar_convite_pedidos() if b.get('tipo') == 'convite' else rodar_convite_amiga() if b.get('tipo') == 'amiga'
                   else rodar_enquete())
            return self.send_json({'id': fid})
        if p == '/api/status/testar':                # posta um Status de teste (em segundo plano: pode levar minutos)
            threading.Thread(target=testar_status, daemon=True).start()
            return self.send_json({'ok': True})
        if p == '/api/status/aviso_salvar':
            return self.send_json({'id': rodar_aviso_salvar()})
        if p == '/api/status/testar_velho':
            res = {}
            for inst in status_cfg().get('chips') or instancias():
                if estado_chip(inst) != 'open':
                    res[inst] = 'desconectado'
                    continue
                corpo = {'type': 'text', 'content': f'💜 Teste do PostZap · {data_sub(agora())} {agora().strftime("%H:%M")}',
                         'backgroundColor': '#7c3aed', 'font': 1}
                try:
                    res[inst] = enviar_status(inst, corpo)
                    marcar_status(inst, True, 'teste', res[inst])
                except Exception as e:
                    res[inst] = 'falhou: ' + str(e)[:300]
                    marcar_status(inst, False, 'teste', res[inst])
            return self.send_json(res)
        if p == '/api/status':
            cfg = status_cfg()
            for k in ('ativo', 'ofertas', 'engajamento'):
                if k in b:
                    cfg[k] = bool(b[k])
            if str(b.get('max_dia', '')).isdigit():
                cfg['max_dia'] = max(1, min(30, int(b['max_dia'])))
            if isinstance(b.get('chips'), list):
                cfg['chips'] = [x for x in b['chips'] if x in instancias()]
            if 'lembrete_ativo' in b:
                cfg['lembrete_ativo'] = bool(b['lembrete_ativo'])
            if str(b.get('lembrete_cada', '')).isdigit():
                cfg['lembrete_cada'] = max(1, min(50, int(b['lembrete_cada'])))
            if str(b.get('lembrete_texto', '')).strip():
                cfg['lembrete_texto'] = str(b['lembrete_texto']).strip()[:300]
            set_cfg('status', json.dumps(cfg))
            return self.send_json({'ok': True})
        if p == '/api/vendas/atualizar':
            return self.send_json({'lidas': coletar_vendas()})
        if p == '/api/pausar':
            set_cfg('pausado', '1' if b.get('pausado') else '0')
            return self.send_json({'ok': True})
        if p == '/api/fila/criar':
            if bloqueado(b.get('produto')):
                return self.send_json({'erro': 'Produto de suplementação não pode ser postado.'}, 400)
            with _lock, db() as c:
                dados = {k: v for k, v in b.items() if k not in ('texto', 'grupos', 'agendado_para', 'midia')}
                cur = c.execute('INSERT INTO fila (origem, chave, produto, preco, comissao, link, texto, grupos, '
                                'agendado_para, criado_em, dados) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                (b.get('origem'), b.get('chave'), b.get('produto'), b.get('preco'), b.get('comissao'),
                                 b.get('link'), b.get('texto'), json.dumps(b.get('grupos') or []),
                                 b.get('agendado_para') or '', agora().isoformat(), json.dumps(dados)))
            return self.send_json({'id': cur.lastrowid})
        if p == '/api/fila/editar':
            with _lock, db() as c:
                c.execute("UPDATE fila SET texto=?, grupos=?, agendado_para=? WHERE id=? AND status IN ('rascunho','erro','aprovado')",
                          (b.get('texto'), json.dumps(b.get('grupos') or []), b.get('agendado_para') or '', b['id']))
            return self.send_json({'ok': True})
        if p == '/api/fila/aprovar':
            it = item_fila(b['id'])
            ok, sem = aprovar_itens([it]) if it else ([], [])
            if sem or not it:
                return self.send_json({'erro': 'Nenhum grupo marcado: marque grupos em 👥 Grupos (ou escolha no ✏️ Editar).'}, 400)
            return self.send_json({'ok': True})
        if p == '/api/fila/definir_grupos':           # posts sem grupo (ou todos da fila) → lista escolhida / marcados
            lista = next((l for l in listas() if l['id'] == b.get('lista')), None)
            gs = [g for g in (json.loads(lista['grupos']) if lista else grupos_ativos()) if g not in grupos_fila()]
            if not gs:
                return self.send_json({'erro': 'Nenhum grupo: marque grupos em 👥 Grupos (ou crie a lista).'}, 400)
            with _lock, db() as c:
                ids = [r[0] for r in c.execute("SELECT id, grupos FROM fila WHERE status IN ('rascunho','erro','aprovado')")
                       if b.get('todos') or not json.loads(r[1] or '[]')]
                for i in ids:
                    c.execute('UPDATE fila SET grupos=? WHERE id=?', (json.dumps(gs), i))
            return self.send_json({'alterados': ids, 'grupos': len(gs)})
        if p == '/api/fila/aprovar_todos':
            lista = next((l for l in listas() if l['id'] == b.get('lista')), None)
            with db() as c:
                itens = [dict(r) for r in c.execute("SELECT * FROM fila WHERE status IN ('rascunho','erro') ORDER BY id")]
            ok, sem = aprovar_itens(itens, lista)
            return self.send_json({'aprovados': ok, 'sem_grupo': sem, 'proxima': proxima_saida().isoformat()})
        if p == '/api/fila/nicho':
            it = item_fila(b['id'])
            if it and b.get('nicho') in NICHOS:
                dados = json.loads(it.get('dados') or '{}')
                dados['nicho'] = b['nicho']
                with _lock, db() as c:
                    c.execute('UPDATE fila SET dados=? WHERE id=?', (json.dumps(dados), b['id']))
            return self.send_json({'ok': True})
        if p == '/api/fila/voltar':
            with _lock, db() as c:
                c.execute("UPDATE fila SET status='rascunho' WHERE id=? AND status='aprovado'", (b['id'],))
            return self.send_json({'ok': True})
        if p == '/api/fila/descartar':
            with _lock, db() as c:
                ja_foi = c.execute('SELECT COUNT(*) FROM envios WHERE fila_id=? AND ok=1', (b['id'],)).fetchone()[0]
                if ja_foi:      # já saiu para algum grupo: só tira da fila e fica no histórico como enviado
                    c.execute("UPDATE fila SET status='enviado', enviado_em=COALESCE(enviado_em, ?), erro=? WHERE id=? "
                              "AND status!='enviando'", (agora().isoformat(), f'Interrompido por você — já tinha ido para {ja_foi} grupo(s).', b['id']))
                else:
                    c.execute("UPDATE fila SET status='descartado' WHERE id=? AND status!='enviando'", (b['id'],))
            return self.send_json({'ok': True, 'ja_enviado': ja_foi})
        if p == '/api/fila/restaurar':
            with _lock, db() as c:
                ja_foi = c.execute('SELECT COUNT(*), MAX(quando) FROM envios WHERE fila_id=? AND ok=1', (b['id'],)).fetchone()
                if ja_foi[0]:
                    c.execute("UPDATE fila SET status='enviado', enviado_em=COALESCE(enviado_em, ?) WHERE id=? AND status='descartado'",
                              (ja_foi[1], b['id']))
                else:
                    c.execute("UPDATE fila SET status='rascunho' WHERE id=? AND status='descartado'", (b['id'],))
            return self.send_json({'ok': True, 'para': 'enviado' if ja_foi[0] else 'rascunho'})
        self.send_json({'erro': 'não encontrado'}, 404)


def main():
    if not CFG['senha']:
        raise SystemExit('Defina POSTZAP_SENHA no arquivo .env')
    init_db()
    with _lock, db() as c:   # envio interrompido por reinício volta para aprovado (não repete grupos já enviados)
        c.execute("UPDATE fila SET status='aprovado' WHERE status='enviando'")
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=monitor_chips, daemon=True).start()
    threading.Thread(target=agenda_divulgador, daemon=True).start()
    threading.Thread(target=agenda_engajamento, daemon=True).start()
    threading.Thread(target=agenda_vendas, daemon=True).start()
    if not CFG['autorizados']:
        log.warning('NUMEROS_AUTORIZADOS vazio: a conversa de links pelo WhatsApp fica desligada')
    srv = ThreadingHTTPServer(('127.0.0.1', CFG['porta']), H)
    log.info(f"PostZap em http://127.0.0.1:{CFG['porta']}/zap")
    srv.serve_forever()


if __name__ == '__main__':
    main()
