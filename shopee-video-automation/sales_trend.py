"""
Vendas do mês (dica da comunidade, 12/11): escolher produto pelas unidades vendidas NO MÊS, não pelo total
(tem produto com 6 mil vendidos que hoje vende 10 por mês). A API da Shopee só dá o total ('sales'); então o robô
guarda o total de cada produto que vê (nas buscas das ideias e no datafeed diário) e calcula quanto ele vendeu
nos últimos dias: (total de hoje − total de N dias atrás) ÷ N × 30.

Datafeed: o CSV do catálogo da Shopee que o portal de afiliados gera (link próprio da conta, em SHOPEE_DATAFEED_URL
no .env). Baixado uma vez por dia; os produtos com vendas viram histórico e os que mais cresceram entram nas ideias
("📈 Vendendo agora").
"""

import csv
import gzip
import io
import logging
import os
import re
import zipfile
from datetime import date, timedelta
from typing import Dict, Iterable, Iterator, List, Optional

import requests

logger = logging.getLogger(__name__)

HISTORY_DAYS = 40
MIN_SPAN_DAYS = 5          # precisa de pelo menos 5 dias entre as duas leituras para estimar o mês
DEAD_MONTHLY = int(os.getenv('IDEIAS_MIN_VENDAS_MES', '30'))   # vendas/mês conhecidas abaixo disso: produto parado
DATAFEED_URL = os.getenv('SHOPEE_DATAFEED_URL', '').strip()
DATAFEED_MIN_SALES = int(os.getenv('DATAFEED_MIN_VENDAS', '300'))
DATAFEED_MAX_ROWS = int(os.getenv('DATAFEED_MAX_ITENS', '60000'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sales_hist (key TEXT, day TEXT, sales INTEGER, PRIMARY KEY (key, day));
CREATE TABLE IF NOT EXISTS datafeed_items (key TEXT PRIMARY KEY, name TEXT, rating REAL, price REAL, day TEXT);
"""


def setup(db):
    with db.lock:
        db.conn.executescript(SCHEMA)
        db.conn.commit()


def record(db, products: Iterable[Dict], day: Optional[date] = None):
    """Guarda o total de vendas de hoje de cada produto (o último do dia vale)."""
    day = (day or date.today()).isoformat()
    rows = [(f"{p['shopId']}:{p['itemId']}", day, int(p.get('sales') or 0))
            for p in products if p.get('shopId') and p.get('itemId') and p.get('sales') not in (None, '')]
    if not rows:
        return
    with db.lock:
        db.conn.executemany("INSERT OR REPLACE INTO sales_hist (key, day, sales) VALUES (?, ?, ?)", rows)
        db.conn.commit()


def prune(db, today: Optional[date] = None):
    cutoff = ((today or date.today()) - timedelta(days=HISTORY_DAYS)).isoformat()
    with db.lock:
        db.conn.execute("DELETE FROM sales_hist WHERE day < ?", (cutoff,))
        db.conn.execute("DELETE FROM datafeed_items WHERE day < ?", (cutoff,))
        db.conn.commit()


def monthly(db, key: str, sales_now: Optional[int] = None, today: Optional[date] = None) -> Optional[int]:
    """Vendas estimadas em 30 dias (None se ainda não há duas leituras com MIN_SPAN_DAYS dias de distância)."""
    today = today or date.today()
    with db.lock:
        rows = db.conn.execute("SELECT day, sales FROM sales_hist WHERE key = ? AND day >= ? ORDER BY day",
                               (key, (today - timedelta(days=HISTORY_DAYS)).isoformat())).fetchall()
    if not rows:
        return None
    last_day, last = date.fromisoformat(rows[-1][0]), rows[-1][1]
    if sales_now is not None:
        last_day, last = today, int(sales_now)
    # a leitura mais antiga com pelo menos MIN_SPAN_DAYS de distância (o mais perto de 30 dias possível)
    old = [(date.fromisoformat(d), s) for d, s in rows if (last_day - date.fromisoformat(d)).days >= MIN_SPAN_DAYS]
    if not old:
        return None
    first_day, first = old[0]
    span = (last_day - first_day).days
    return max(0, round((last - first) / span * 30))


class Trend:
    """O que as ideias usam: vendas do mês de um produto (com cache por execução) e o registro do que foi visto."""

    def __init__(self, db):
        self.db = db
        self.cache: Dict[str, Optional[int]] = {}
        setup(db)

    def month(self, p: Dict) -> Optional[int]:
        key = f"{p.get('shopId')}:{p.get('itemId')}"
        if key not in self.cache:
            self.cache[key] = monthly(self.db, key, p.get('sales') and int(p['sales']))
        return self.cache[key]

    def seen(self, products: List[Dict]):
        try:
            record(self.db, products)
        except Exception as e:
            logger.warning(f"Histórico de vendas: não gravei ({e})")


class RecordingClient:
    """Embrulha o cliente da Shopee: toda busca grava o total de vendas dos produtos que vieram."""

    def __init__(self, client, trend: Trend):
        self._client = client
        self._trend = trend

    def search(self, *args, **kwargs):
        results = self._client.search(*args, **kwargs)
        self._trend.seen(results)
        return results

    def __getattr__(self, name):
        return getattr(self._client, name)


# ---------- Datafeed ----------

COLUMNS = {
    'item': ['itemid', 'item_id', 'item id', 'product_id', 'id do item'],
    'shop': ['shopid', 'shop_id', 'shop id', 'seller_id', 'id da loja'],
    'name': ['title', 'product_name', 'item_name', 'name', 'nome', 'titulo', 'título'],
    'sales': ['item_sold', 'sold', 'historical_sold', 'sales', 'sold_count', 'vendas', 'total_sold'],
    'rating': ['item_rating', 'rating', 'rating_star', 'ratingstar', 'avaliacao', 'avaliação'],
    'price': ['sale_price', 'price', 'preco', 'preço', 'price_min'],
    'link': ['product_link', 'link', 'url', 'product_url'],
}


def _pick(header: List[str]) -> Dict[str, int]:
    low = [h.strip().lower() for h in header]
    out = {}
    for field, names in COLUMNS.items():
        for n in names:
            if n in low:
                out[field] = low.index(n)
                break
    if 'item' not in out or 'shop' not in out:   # sem colunas de id: tenta tirar do link do produto
        out.pop('item', None)
        out.pop('shop', None)
    return out


def _num(text: str) -> float:
    text = (text or '').strip().lower().replace('r$', '').replace(' ', '')
    mult = 1000 if text.endswith('mil') or text.endswith('k') else 1
    text = re.sub(r'(mil|k)$', '', text)
    if text.count(',') == 1 and text.count('.') >= 1:
        text = text.replace('.', '').replace(',', '.')
    elif text.count(',') == 1:
        text = text.replace(',', '.')
    try:
        return float(re.sub(r'[^0-9.]', '', text) or 0) * mult
    except ValueError:
        return 0.0


LINK_IDS = re.compile(r'(?:product/(\d+)/(\d+))|(?:-i\.(\d+)\.(\d+))')


def _lines(resp: requests.Response) -> Iterator[str]:
    """Linhas do CSV, seja ele puro, .gz ou .zip."""
    raw = resp.raw
    raw.decode_content = True
    head = raw.read(4)
    if head[:2] == b'\x1f\x8b':
        stream = gzip.GzipFile(fileobj=io.BufferedReader(_Prefixed(head, raw)))
    elif head[:2] == b'PK':
        data = head + raw.read()
        z = zipfile.ZipFile(io.BytesIO(data))
        stream = z.open(next((n for n in z.namelist() if n.lower().endswith(('.csv', '.txt'))), z.namelist()[0]))
    else:
        stream = io.BufferedReader(_Prefixed(head, raw))
    yield from io.TextIOWrapper(stream, encoding='utf-8-sig', errors='ignore', newline='')


class _Prefixed(io.RawIOBase):
    def __init__(self, prefix: bytes, rest):
        self.prefix, self.rest = prefix, rest

    def readable(self):
        return True

    def readinto(self, b):
        if self.prefix:
            n = min(len(b), len(self.prefix))
            b[:n] = self.prefix[:n]
            self.prefix = self.prefix[n:]
            return n
        data = self.rest.read(len(b))
        b[:len(data)] = data
        return len(data)


def import_datafeed(db, url: str = DATAFEED_URL, today: Optional[date] = None) -> Dict:
    """Baixa o datafeed, grava o total de vendas dos produtos com DATAFEED_MIN_SALES+ vendas. Devolve um resumo."""
    today = today or date.today()
    setup(db)
    resp = requests.get(url, stream=True, timeout=(30, 600))
    resp.raise_for_status()
    reader = csv.reader(_lines(resp))
    header = next(reader)
    cols = _pick(header)
    if 'sales' not in cols:
        raise RuntimeError(f"o datafeed não tem coluna de vendas (colunas: {', '.join(header[:25])})")
    hist, items, total = [], [], 0
    for row in reader:
        total += 1
        try:
            sales = int(_num(row[cols['sales']]))
            if sales < DATAFEED_MIN_SALES:
                continue
            if 'item' in cols:
                shop, item = row[cols['shop']].strip(), row[cols['item']].strip()
            else:
                m = LINK_IDS.search(row[cols['link']]) if 'link' in cols else None
                if not m:
                    continue
                shop, item = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            key = f"{int(float(shop))}:{int(float(item))}"
        except (IndexError, ValueError):
            continue
        hist.append((key, today.isoformat(), sales))
        items.append((key, row[cols['name']][:200] if 'name' in cols else '',
                      _num(row[cols['rating']]) if 'rating' in cols else 0.0,
                      _num(row[cols['price']]) if 'price' in cols else 0.0, today.isoformat()))
        if len(hist) >= DATAFEED_MAX_ROWS:
            break
    with db.lock:
        db.conn.executemany("INSERT OR REPLACE INTO sales_hist (key, day, sales) VALUES (?, ?, ?)", hist)
        db.conn.executemany("INSERT OR REPLACE INTO datafeed_items (key, name, rating, price, day) "
                            "VALUES (?, ?, ?, ?, ?)", items)
        db.conn.commit()
    prune(db, today)
    return {'linhas': total, 'gravados': len(hist), 'colunas': sorted(cols)}


def rising(db, limit: int = 40, today: Optional[date] = None) -> List[Dict]:
    """Os produtos do datafeed que mais venderam nos últimos dias (vendas/mês estimadas), do maior para o menor."""
    today = today or date.today()
    with db.lock:
        rows = db.conn.execute(
            "SELECT key, name, rating FROM datafeed_items WHERE day >= ?",
            ((today - timedelta(days=3)).isoformat(),)).fetchall()
    scored = []
    for key, name, rating in rows:
        m = monthly(db, key, today=today)
        if m:
            shop, item = key.split(':')
            scored.append({'shopId': int(shop), 'itemId': int(item), 'nome': name, 'nota': rating, 'mes': m})
    scored.sort(key=lambda r: r['mes'], reverse=True)
    return scored[:limit]
