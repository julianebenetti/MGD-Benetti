"""
Shopee Affiliate Open API + conversão de links
Descobre o produto por trás de qualquer link recebido (produto, link curto ou
link de Shopee Video) e gera o link de afiliado do produto. Nunca devolve link de vídeo.
"""

import difflib
import hashlib
import json
import logging
import re
import time
import unicodedata
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

logger = logging.getLogger(__name__)

API_URL = 'https://open-api.affiliate.shopee.com.br/graphql'
PRODUCT_FIELDS = ('itemId shopId productName shopName price priceMin priceMax '
                  'ratingStar sales commissionRate offerLink productLink imageUrl')
MATCH_THRESHOLD = 0.90
URL_RE = re.compile(r'https?://\S+')

ID_PATTERNS = [
    re.compile(r'/product/(?P<shop>\d+)/(?P<item>\d+)'),
    re.compile(r'-i\.(?P<shop>\d+)\.(?P<item>\d+)'),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def extract_ids(url: str) -> Optional[Dict[str, int]]:
    for pattern in ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return {'shop_id': int(m['shop']), 'item_id': int(m['item'])}
    qs = parse_qs(urlparse(url).query)
    shop = qs.get('shopid') or qs.get('shop_id')
    item = qs.get('itemid') or qs.get('item_id')
    if shop and item and shop[0].isdigit() and item[0].isdigit():
        return {'shop_id': int(shop[0]), 'item_id': int(item[0])}
    return None


def is_video_link(url: str) -> bool:
    return 'sv.shopee' in urlparse(url).netloc or '/share-video/' in url


def product_name_from_text(text: str) -> str:
    """Nome do produto escrito na mensagem (sem links e sem 'Produto:')."""
    text = URL_RE.sub(' ', text or '')
    text = re.sub(r'(?i)\bproduto\s*:', ' ', text)
    return ' '.join(text.split())


def commission_value(product: Dict) -> float:
    """Comissão estimada em R$ (a API manda a taxa como fração, ex: '0.08')."""
    price = float(product.get('priceMin') or product.get('price') or 0)
    rate = float(product.get('commissionRate') or 0)
    if rate > 1:
        rate /= 100
    return round(price * rate, 2)


class ShopeeAffiliateClient:
    def __init__(self, app_id: str, secret: str):
        self.app_id = app_id
        self.secret = secret
        self.session = requests.Session()
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

    def _graphql(self, query: str, variables: Dict) -> Dict:
        payload = json.dumps({'query': query, 'variables': variables}, separators=(',', ':'))
        ts = str(int(time.time()))
        signature = hashlib.sha256(f'{self.app_id}{ts}{payload}{self.secret}'.encode()).hexdigest()
        resp = self.session.post(API_URL, data=payload, timeout=30, headers={
            'Content-Type': 'application/json',
            'Authorization': f'SHA256 Credential={self.app_id}, Timestamp={ts}, Signature={signature}',
        })
        resp.raise_for_status()
        data = resp.json()
        if data.get('errors'):
            raise RuntimeError(f"Shopee API: {data['errors']}")
        return data['data']

    def product_by_ids(self, shop_id: int, item_id: int) -> Optional[Dict]:
        query = (f'query($shopId:Int64,$itemId:Int64){{productOfferV2(shopId:$shopId,itemId:$itemId,limit:1)'
                 f'{{nodes{{{PRODUCT_FIELDS}}}}}}}')
        nodes = self._graphql(query, {'shopId': shop_id, 'itemId': item_id})['productOfferV2']['nodes']
        return nodes[0] if nodes else None

    def search(self, keyword: str, limit: int = 20) -> List[Dict]:
        query = (f'query($keyword:String,$limit:Int){{productOfferV2(keyword:$keyword,limit:$limit)'
                 f'{{nodes{{{PRODUCT_FIELDS}}}}}}}')
        return self._graphql(query, {'keyword': keyword, 'limit': limit})['productOfferV2']['nodes']

    def short_link(self, origin_url: str, sub_ids: Optional[List[str]] = None) -> str:
        query = 'mutation($input:ShortLinkInput!){generateShortLink(input:$input){shortLink}}'
        variables = {'input': {'originUrl': origin_url, 'subIds': sub_ids or []}}
        return self._graphql(query, variables)['generateShortLink']['shortLink']

    def find_by_name(self, name: str, shop_name: Optional[str] = None) -> Optional[Dict]:
        """Só aceita quando há um único produto com nome praticamente idêntico."""
        target = _normalize(name)
        if not target:
            return None
        scored = []
        for node in self.search(name):
            if shop_name and _normalize(node.get('shopName', '')) != _normalize(shop_name):
                continue
            ratio = difflib.SequenceMatcher(None, target, _normalize(node['productName'])).ratio()
            if ratio >= MATCH_THRESHOLD:
                scored.append((ratio, node))
        if len(scored) != 1:
            logger.warning(f"Busca por nome '{name}': {len(scored)} correspondências exatas")
            return None
        return scored[0][1]

    def resolve_url(self, url: str) -> str:
        """Segue redirecionamentos de links curtos (br.shp.ee, s.shopee.com.br)."""
        try:
            return self.session.get(url, allow_redirects=True, timeout=20).url
        except requests.RequestException as e:
            logger.warning(f"Não consegui abrir {url}: {e}")
            return url

    def _products_from_video_page(self, video_url: str, limit: int = 5) -> List[Dict]:
        from video_page_reader import read_video_products
        try:
            candidates = read_video_products(video_url)
        except Exception as e:
            logger.warning(f"Não consegui ler a página do vídeo: {e}")
            return []
        products = []
        for c in candidates[:limit]:
            product = self.product_by_ids(c['shop_id'], c['item_id'])
            if product:
                products.append(product)
        return products

    def find_candidates(self, url: str, message_text: str = '') -> List[Dict]:
        """
        Produtos possíveis para o link recebido, em ordem de prioridade.
        Link de produto: 1 candidato. Link de vídeo: os produtos vinculados ao vídeo.
        """
        final_url = self.resolve_url(url)
        ids = extract_ids(final_url) or extract_ids(url)
        if ids:
            product = self.product_by_ids(ids['shop_id'], ids['item_id'])
            return [product] if product else []

        candidates: List[Dict] = []
        if is_video_link(final_url) or is_video_link(url):
            candidates = self._products_from_video_page(final_url)
        if not candidates:
            name = product_name_from_text(message_text)
            product = self.find_by_name(name) if name else None
            if product:
                candidates = [product]
        return candidates

    def other_sellers(self, product: Dict, min_commission: float = 9.0,
                      min_rating: float = 4.5) -> List[Dict]:
        """Mesmo tipo de produto em outras lojas, ordenado por maior comissão (R$)."""
        keyword = ' '.join(product['productName'].split()[:8])
        others = []
        for node in self.search(keyword, limit=30):
            if str(node['itemId']) == str(product['itemId']) or str(node['shopId']) == str(product['shopId']):
                continue
            if float(node.get('ratingStar') or 0) < min_rating:
                continue
            node['commissionValue'] = commission_value(node)
            if node['commissionValue'] >= min_commission:
                others.append(node)
        return sorted(others, key=lambda n: n['commissionValue'], reverse=True)

    def affiliate_link(self, product: Dict, sub_id: str) -> str:
        product_url = f"https://shopee.com.br/product/{product['shopId']}/{product['itemId']}"
        return self.short_link(product_url, [sub_id])
