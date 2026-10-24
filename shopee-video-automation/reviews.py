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
