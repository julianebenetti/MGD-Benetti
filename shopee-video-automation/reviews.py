"""
Avaliações dos compradores para a narração dos prompts (🎬 Prompts), lidas SEM a conta da Juliane: pedido anônimo
(sem cookies nem login) à lista pública de avaliações da Shopee. A API de afiliados não traz o texto das avaliações.
A Shopee costuma barrar pedidos de servidor; aí volta lista vazia e valem os prints que ela mandar.
"""

import logging
import os
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

URL = 'https://shopee.com.br/api/v2/item/get_ratings'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
}


def enabled() -> bool:
    return (os.getenv('SHOPEE_AVALIACOES') or 'sim').strip().lower() in ('sim', 'true', '1')


def fetch(product: Dict, limit: int = 10) -> List[str]:
    """Até `limit` avaliações com texto (as primeiras que a Shopee mostra), como "★5 texto"; [] se não deu."""
    if not enabled() or not product.get('itemId') or not product.get('shopId'):
        return []
    params = {'itemid': product['itemId'], 'shopid': product['shopId'], 'limit': 20, 'offset': 0,
              'type': 0, 'filter': 1, 'flag': 1}   # filter 1: só as que têm comentário
    headers = {**HEADERS, 'Referer': f"https://shopee.com.br/product/{product['shopId']}/{product['itemId']}"}
    try:
        # sessão nova a cada vez: nenhum cookie, nada ligado à conta
        resp = requests.Session().get(URL, params=params, headers=headers, timeout=15)
        data = resp.json() if resp.ok else {}
    except (requests.RequestException, ValueError) as e:
        logger.info(f"Avaliações não vieram: {e}")
        return []
    ratings = ((data or {}).get('data') or {}).get('ratings') or []
    if not ratings:
        logger.info(f"Avaliações não vieram (HTTP {resp.status_code}, erro {(data or {}).get('error')})")
    found = []
    for r in ratings:
        text = ' '.join((r.get('comment') or '').split())
        if text:
            found.append(f"★{r.get('rating_star', '')} {text[:300]}")
        if len(found) >= limit:
            break
    return found


COMMENT_KEYS = ('comentario', 'comentário', 'comment', 'texto', 'text', 'review', 'avaliacao', 'avaliação')
STAR_KEYS = ('estrelas', 'stars', 'star', 'rating_star', 'rating', 'nota')
VARIATION_KEYS = ('variacao', 'variação', 'variation', 'model', 'modelo')


def _pick(row: Dict, keys) -> str:
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        if low.get(key) not in (None, ''):
            return ' '.join(str(low[key]).split())
    return ''


def _rows(data) -> List[Dict]:
    """A lista de avaliações dentro do JSON (lista solta ou dentro de "reviews"/"avaliacoes"/"ratings"/…)."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for value in data.values():
            rows = _rows(value) if isinstance(value, (list, dict)) else []
            if rows and any(_pick(r, COMMENT_KEYS) for r in rows):
                return rows
    return []


def parse_file(path: str, limit: int = 30) -> List[str]:
    """
    Avaliações do arquivo que a extensão "Shopee Reviews Grabber" baixa (JSON ou CSV: autor, estrelas,
    comentário, data, variação…), no mesmo formato de `fetch`: "★5 texto (variação)". Só as que têm texto.
    """
    import csv
    import io
    import json
    raw = open(path, 'rb').read().decode('utf-8-sig', errors='replace')
    if path.lower().endswith('.json') or raw.lstrip().startswith(('[', '{')):
        rows = _rows(json.loads(raw))
    else:
        sample = raw[:2000]
        delimiter = ';' if sample.count(';') > sample.count(',') else ','
        rows = list(csv.DictReader(io.StringIO(raw), delimiter=delimiter))
    found = []
    for row in rows:
        text = _pick(row, COMMENT_KEYS)
        if not text:
            continue
        stars = _pick(row, STAR_KEYS)
        variation = _pick(row, VARIATION_KEYS)
        found.append(f"★{stars} {text[:300]}" + (f" ({variation[:60]})" if variation else ''))
        if len(found) >= limit:
            break
    return found
