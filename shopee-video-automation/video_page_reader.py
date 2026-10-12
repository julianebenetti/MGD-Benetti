"""
Video Page Reader
Abre a página de um Shopee Video num navegador automático e descobre os produtos vinculados.
Lê os dados JSON que a própria página recebe da Shopee (não depende do layout) e,
como reserva, os links de produto presentes na página.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent / '.browser-profile'
SHOP_KEYS = ('shopid', 'shop_id', 'shopId')
ITEM_KEYS = ('itemid', 'item_id', 'itemId')
NAME_KEYS = ('name', 'item_name', 'itemName', 'productName', 'title')
PRODUCT_HREF_RE = re.compile(r'(?:-i\.(\d+)\.(\d+))|(?:/product/(\d+)/(\d+))')


def _as_id(value: Any):
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def find_products_in_json(data: Any) -> List[Dict]:
    """Procura, em qualquer profundidade, objetos que tenham id de loja + id de item."""
    found: List[Dict] = []

    def walk(node: Any):
        if isinstance(node, dict):
            shop = next((_as_id(node[k]) for k in SHOP_KEYS if k in node), None)
            item = next((_as_id(node[k]) for k in ITEM_KEYS if k in node), None)
            if shop and item:
                name = next((node[k] for k in NAME_KEYS if isinstance(node.get(k), str)), '')
                found.append({'shop_id': shop, 'item_id': item, 'name': name})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


def _dedupe(products: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for p in products:
        key = (p['shop_id'], p['item_id'])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def read_video_products(url: str, wait_ms: int = 8000) -> List[Dict]:
    """Devolve os produtos vinculados ao vídeo, na ordem em que aparecem."""
    from playwright.sync_api import sync_playwright

    from_json: List[Dict] = []

    def on_response(response):
        if 'shopee' not in response.url or 'json' not in response.headers.get('content-type', ''):
            return
        try:
            from_json.extend(find_products_in_json(response.json()))
        except Exception:
            pass

    with sync_playwright() as p:
        from shopee_session import is_blocked, launch
        context = launch(p, PROFILE_DIR, viewport={'width': 430, 'height': 932}, is_mobile=True)
        page = context.new_page()
        page.on('response', on_response)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(wait_ms)
            if is_blocked(page.url):
                logger.warning(f"Shopee pediu login ao abrir o vídeo: {page.url[:120]}")
            hrefs = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
        finally:
            context.close()

    from_dom = []
    for href in hrefs:
        m = PRODUCT_HREF_RE.search(href)
        if m:
            shop, item = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            from_dom.append({'shop_id': int(shop), 'item_id': int(item), 'name': ''})

    products = _dedupe(from_json + from_dom)
    logger.info(f"Página do vídeo: {len(products)} produto(s) encontrado(s)")
    return products
