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

🏃‍♀️ Corre que acaba rápido!
🔗 {link}

⚠️ Todas as promoções estão sujeitas a alterações a qualquer momento.""",
    'Cupom': """🎟️ *CUPOM LIBERADO!*
*{chamada}*

🛍️ {produto}

Use o cupom: *{cupom}* {cupom_texto}
~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* ✅

🔗 *Compre aqui:* {link}

⚠️ Cupom sujeito a disponibilidade e às regras da loja.""",
    'VIP': """👑 *EXCLUSIVO DO GRUPO VIP* 👑
*{chamada}*

🛍️ {produto}

~De: {preco_de}~ 🔻{desconto}
*Por: {preco}* ✅
🎟️ Cupom: *{cupom}* {cupom_texto}

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
                         ('fila', 'pedido_inst TEXT'), ('grupo_chips', 'admin INTEGER'), ('grupos', 'admin INTEGER')):
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
    return m


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
        if bloqueado(p.get('produto')) or com < CFG['comissao_min'] or not p.get('link'):
            continue
        chave = f"{p.get('shop_id')}:{p.get('item_id')}" if p.get('item_id') else f"g{p['id']}"
        out.append({'origem': 'garimpo', 'chave': chave, 'produto': p.get('produto') or '', 'loja': p.get('loja') or '',
                    'preco': br(p.get('preco')), 'comissao': br(com), 'vendas': p.get('vendas') or 0,
                    'nota': p.get('nota') or '', 'link': p['link'],
                    'nicho': classificar_nicho(p.get('produto'), p.get('nicho')),
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
            if not r.get('link') or bloqueado(r.get('produto')) or num(r.get('comissao')) < CFG['comissao_min']:
                continue
            vistos.add(chave)
            out.append({'origem': 'central_ideias', 'chave': chave, 'produto': r.get('produto', ''),
                        'loja': r.get('loja', ''), 'preco': br(r.get('preco')), 'comissao': br(r.get('comissao')),
                        'vendas': r.get('vendas') or 0, 'nota': r.get('nota') or '', 'link': r['link'],
                        'nicho': classificar_nicho(r.get('produto'), f"{r.get('secao', '')} {r.get('tema', '')}"),
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
    ('🏠 Casa e decoração', r'tapete|cortina|almofada|quadro|espelho|vaso|lumin[aá]ria|jogo de cama|len[cç]ol|edredom|colcha|'
                           r'manta|cobertor|toalha|organizador|cabide|prateleira|decora|banheiro|travesseiro|lixeira|varal|'
                           r'cesto|jardim|abajur|porta-?retrato|casa'),
    ('👗 Moda', r'vestido|blusa|cal[cç]a|short|saia|macac[aã]o|legging|conjunto|suti[aã]|calcinha|cueca|t[eê]nis|sand[aá]lia|'
               r'chinelo|bolsa|mochila|carteira|biqu[ií]ni|mai[oô]|camis|jaqueta|moletom|pijama|meia|bon[eé]|[oó]culos|brinco|colar'),
]
_DICA_NICHO = {'casa': '🏠 Casa e decoração', 'decor': '🏠 Casa e decoração', 'moveis': '🛋️ Móveis', 'móveis': '🛋️ Móveis',
               'eletro': '🔌 Eletrodomésticos', 'beleza': '💇 Beleza e cabelo', 'cabelo': '💇 Beleza e cabelo',
               'moda': '👗 Moda', 'pet': '🐶 Pet', 'infantil': '🧸 Infantil', 'cozinha': '🍳 Cozinha e utensílios',
               'utens': '🍳 Cozinha e utensílios', 'eletron': '🎧 Eletrônicos', 'tapete': '🏠 Casa e decoração'}


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
    if not p.get('nicho') or p['nicho'] not in NICHOS:
        p['nicho'] = classificar_nicho(p.get('produto'), p.get('nicho') or p.get('palavra') or '')
    if 'cupom' not in p:
        p['cupom'], p['cupom_texto'] = cupom_para(p['loja'])
    if not p.get('chamada') and p.get('produto'):
        p['chamada'] = gerar_chamada(p['produto'], p['loja'])
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
            'byEvents': False, 'base64': False, 'events': ['MESSAGES_UPSERT']}})
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


def nicho_do_item(item):
    try:
        return (json.loads(item['dados'] or '{}') or {}).get('nicho') or classificar_nicho(item['produto'])
    except (ValueError, KeyError, TypeError):
        return '📦 Outros'


def ritmo():
    r = dict(RITMO_PADRAO)
    r.update(get_json('ritmo', {}))
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
    return min(int(r['aquec_max']), int(r['aquec_inicio']) + int(r['aquec_passo']) * max(0, dias))


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


def proximo_item():
    """Agendados com hora marcada saem na hora; os outros saem em rajadas (1–3 posts, pausa 40–90 min) no horário."""
    r = ritmo()
    agora_iso = agora().isoformat()
    with db() as c:
        item = c.execute("SELECT * FROM fila WHERE status='aprovado' AND agendado_para!='' AND agendado_para IS NOT NULL "
                         "AND agendado_para<=? ORDER BY agendado_para LIMIT 1", (agora_iso,)).fetchone()
    if item:
        return item
    if not no_horario(r):
        return None
    prox = get_cfg('proxima_rajada')
    if prox and prox > agora_iso:
        return None
    with db() as c:
        candidatos = c.execute("SELECT * FROM fila WHERE status='aprovado' AND (agendado_para IS NULL OR agendado_para='') "
                               "ORDER BY aprovado_em").fetchall()
    da_hora = nichos_da_hora(r)
    if da_hora:                     # rajada do nicho da hora; sem nenhum desse nicho: outro (ou espera, se estrito)
        do_nicho = [x for x in candidatos if nicho_do_item(x) in da_hora]
        candidatos = do_nicho or ([] if r.get('nicho_estrito') else candidatos)
    item = candidatos[0] if candidatos else None
    if not item:
        return None
    restante = int(get_cfg('rajada_restante', '0') or 0)
    if restante <= 0:
        restante = random.randint(*r['rajada'])
    restante -= 1
    set_cfg('rajada_restante', str(restante))
    if restante <= 0:          # acabou a rajada: sorteia a pausa (conta a partir de agora; o envio leva alguns min)
        set_cfg('proxima_rajada', (agora() + timedelta(minutes=random.randint(*r['pausa']))).isoformat())
    else:                      # dentro da rajada: próximo post logo em seguida (3–8 min)
        set_cfg('proxima_rajada', (agora() + timedelta(minutes=random.randint(3, 8))).isoformat())
    return item


def processar_fila():
    if get_cfg('pausado') == '1':
        return
    item = proximo_item()
    if not item:
        return
    r = ritmo()
    limite = limite_hoje(r)
    with _lock, db() as c:
        c.execute("UPDATE fila SET status='enviando' WHERE id=?", (item['id'],))
    fila = grupos_fila()
    grupos = [g for g in json.loads(item['grupos'] or '[]') if g not in fila]   # o grupo da fila nunca recebe post
    random.shuffle(grupos)                     # ordem dos grupos também muda a cada postagem
    erros, usados, anterior = [], {}, None
    for i, jid in enumerate(grupos):
        if get_cfg('pausado') == '1':
            erros.append('pausado no meio do envio')
            break
        with db() as c:
            nome = (c.execute('SELECT nome FROM grupos WHERE jid=?', (jid,)).fetchone() or [jid])[0]
            if posts_hoje(c, jid) >= limite:
                erros.append(f'{nome}: limite de hoje ({limite} posts/grupo, aquecimento) atingido')
                continue
            ja = c.execute('SELECT 1 FROM envios WHERE fila_id=? AND jid=? AND ok=1', (item['id'], jid)).fetchone()
        if ja:
            continue
        inst = sortear_chip(jid, anterior)
        ok, erro = 1, None
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
        if not inst:
            ok, erro = 0, 'nenhum chip conectado está neste grupo'
        else:
            try:
                enviar_item(inst, jid, envio)
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
            time.sleep(random.randint(*r['entre_grupos']))
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


def receber_webhook(payload):
    if (payload.get('event') or '').lower().replace('_', '.') != 'messages.upsert':
        return
    inst = payload.get('instance') or ''
    data = payload.get('data') or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    key = data.get('key') or {}
    jid = key.get('remoteJid') or ''
    if key.get('fromMe') or jid.endswith('@broadcast'):
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
              "*4* Por · *5 20h* · *6* cupom · *7* estilo · *8* nicho · *0* descartar")


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
            responder(inst, numero, f"📌 *Post #{fid} pronto* · {p.get('nicho', '')} · {p['produto'][:45]} · vai para {len(grupos)} grupo(s)"
                                    f"{extra}{sem_preco}\n\n{MENU_CURTO}", fid=fid)
        n = len(pendentes(numero))
        if len(links) > 1 and n:
            responder(inst, numero, f'✅ Terminei. {n} post(s) esperando sua resposta. Mande *pendentes* para ver a lista.')
        return

    t = texto.strip()
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
        grupos = [g for g in json.loads(item['grupos'] or '[]') if g not in grupos_fila()]
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
            c.execute("UPDATE fila SET status='descartado' WHERE id=?", (fid,))
        conversa_set(numero, None)
        return responder(inst, numero, f'🗑️ Post #{fid} descartado.')
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
    'comissao_min': 9.0,                    # R$ por venda (piso do Garimpo)
    'nota_min': 4.6, 'vendas_min': 300,
    'nao_repetir_dias': 7,
}


def divulgador_cfg():
    d = dict(DIVULGADOR_PADRAO)
    d.update(get_json('divulgador', {}))
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
    for palavra in d['palavras']:
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
                if bloqueado(n.get('productName')) or com < float(d['comissao_min']) or nota < float(d['nota_min']) \
                        or vendas < int(d['vendas_min']):
                    continue
                n.update({'chave': chave, 'comissao_rs': com, 'palavra': palavra,
                          'pontos': com * (1 + min(vendas, 20000) / 2000) * (nota / 5)})
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
        if palavras:
            d = dict(d, palavras=palavras)
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
        info = (f"🤖 *Post #{fid}* · {p.get('nicho', '')} · comissão R$ {br(n['comissao_rs'])} · {int(n.get('sales') or 0)} vendas · "
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
                return self.send_json(divulgador_cfg())
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
                return self.send_json({'fila': rows, 'pausado': get_cfg('pausado') == '1'})
            if p == '/api/config':
                return self.send_json({'modelo': get_cfg('modelo', MODELO_PADRAO), 'modelos': modelos(),
                                       'estilo_loja': get_json('estilo_loja', {}), 'lojas': LOJAS_NOMES,
                                       'chamadas': get_json('chamadas', {}), 'chamada_modo': get_cfg('chamada_modo', 'ia'), 'modo_link': modo_link(),
                                       'ritmo': ritmo(), 'limite_hoje': limite_hoje(), 'nichos': NICHOS,
                                       'nichos_agora': nichos_da_hora(),
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
                    [{'de': f['de'], 'ate': f['ate'], 'nichos': [n for n in f.get('nichos', []) if n in NICHOS]}
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
            for k in ('aquec_inicio', 'aquec_passo', 'aquec_max'):
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
            if isinstance(b.get('palavras'), list):
                d['palavras'] = [x.strip() for x in b['palavras'] if x.strip()][:40]
            for k, tipo in (('por_rodada', int), ('comissao_min', float), ('nota_min', float), ('vendas_min', int),
                            ('nao_repetir_dias', int)):
                if str(b.get(k, '')).replace('.', '', 1).replace(',', '', 1).isdigit():
                    d[k] = tipo(str(b[k]).replace(',', '.'))
            d['comissao_min'] = max(9.0, d['comissao_min'])          # piso do Garimpo: nunca abaixo de R$ 9
            set_cfg('divulgador', json.dumps(d, ensure_ascii=False))
            return self.send_json({'ok': True})
        if p == '/api/divulgador/rodar':
            n, msg = rodar_divulgador(manual=True)
            return self.send_json({'feitos': n, 'msg': msg})
        if p == '/api/divulgador/testar':
            return self.send_json({'produtos': [{'produto': n['productName'], 'comissao': br(n['comissao_rs']),
                                                 'vendas': n.get('sales'), 'nota': n.get('ratingStar'), 'palavra': n['palavra'],
                                                 'preco': br(n.get('priceMin'))} for n in minerar()]})
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
    threading.Thread(target=monitor_chips, daemon=True).start()
    threading.Thread(target=agenda_divulgador, daemon=True).start()
    if not CFG['autorizados']:
        log.warning('NUMEROS_AUTORIZADOS vazio: a conversa de links pelo WhatsApp fica desligada')
    srv = ThreadingHTTPServer(('127.0.0.1', CFG['porta']), H)
    log.info(f"PostZap em http://127.0.0.1:{CFG['porta']}/zap")
    srv.serve_forever()


if __name__ == '__main__':
    main()
