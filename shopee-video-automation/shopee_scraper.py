"""
Shopee Scraper
Extrai informações de produtos da Shopee via web scraping
"""

import logging
import requests
import re
import json
from typing import Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class ShopeeScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def extract_product_info(self, product_url: str) -> Dict:
        """Extrai informações do produto a partir da URL"""
        try:
            logger.info(f"Extraindo informações de: {product_url}")

            # Parse URL para obter shop_id e item_id
            parsed = self._parse_shopee_url(product_url)

            if not parsed:
                logger.error(f"URL inválida: {product_url}")
                return {}

            shop_id = parsed['shop_id']
            item_id = parsed['item_id']

            # Buscar página do produto
            response = self.session.get(product_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extrair dados do JSON no script
            product_data = self._extract_json_data(response.text)

            if not product_data:
                # Fallback: extrair do HTML
                product_data = self._extract_from_html(soup)

            # Enriquecer com dados da API
            api_data = self._fetch_from_api(shop_id, item_id)

            return {
                'url': product_url,
                'name': product_data.get('name', ''),
                'price': product_data.get('price', 0),
                'description': product_data.get('description', ''),
                'category': product_data.get('category', ''),
                'brand': product_data.get('brand', ''),
                'rating': product_data.get('rating', 0),
                'sold': product_data.get('sold', 0),
                'shop_name': product_data.get('shop_name', ''),
                'images': product_data.get('images', []),
                'api_data': api_data
            }

        except Exception as e:
            logger.error(f"Erro ao extrair informações: {e}")
            return {}

    def _parse_shopee_url(self, url: str) -> Optional[Dict]:
        """Parse URL Shopee para extrair shop_id e item_id"""
        try:
            # Padrão: /p/SHOP_ID-ITEM_ID
            pattern = r'/p/(\d+)-(\d+)'
            match = re.search(pattern, url)

            if match:
                return {
                    'shop_id': match.group(1),
                    'item_id': match.group(2)
                }
            return None
        except Exception as e:
            logger.error(f"Erro ao fazer parse da URL: {e}")
            return None

    def _extract_json_data(self, html: str) -> Dict:
        """Extrai dados JSON do HTML da página"""
        try:
            # Procura por dados JSON no script
            pattern = r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>'
            match = re.search(pattern, html, re.DOTALL)

            if match:
                json_str = match.group(1)
                data = json.loads(json_str)

                # Extrair campos relevantes
                return {
                    'name': data.get('name', ''),
                    'price': float(data.get('offers', [{}])[0].get('price', 0)),
                    'description': data.get('description', ''),
                }

            return {}
        except Exception as e:
            logger.error(f"Erro ao extrair JSON: {e}")
            return {}

    def _extract_from_html(self, soup: BeautifulSoup) -> Dict:
        """Fallback: extrai dados do HTML usando BeautifulSoup"""
        try:
            data = {}

            # Nome do produto
            title = soup.find('h1', class_='product-name')
            if title:
                data['name'] = title.text.strip()

            # Preço
            price = soup.find(class_='product-price')
            if price:
                price_text = price.text.strip()
                price_match = re.search(r'[\d.,]+', price_text)
                if price_match:
                    data['price'] = float(price_match.group().replace('.', '').replace(',', '.'))

            # Descrição
            description = soup.find(class_='product-description')
            if description:
                data['description'] = description.text.strip()[:200]

            # Rating
            rating = soup.find(class_='product-rating')
            if rating:
                rating_text = rating.text.strip()
                rating_match = re.search(r'\d+(?:\.\d+)?', rating_text)
                if rating_match:
                    data['rating'] = float(rating_match.group())

            return data

        except Exception as e:
            logger.error(f"Erro ao extrair HTML: {e}")
            return {}

    def _fetch_from_api(self, shop_id: str, item_id: str) -> Dict:
        """Busca dados da API da Shopee (se disponível)"""
        try:
            # API endpoint (pode estar sujeito a mudanças)
            api_url = f"https://shopee.com.br/api/v2/item/get?itemid={item_id}&shopid={shop_id}"

            response = self.session.get(api_url)
            response.raise_for_status()

            data = response.json()

            if data.get('data'):
                item = data['data']['item']
                return {
                    'sold': item.get('sold', 0),
                    'rating': item.get('rating_star', 0),
                    'category_id': item.get('category', {}).get('catid', 0),
                }

            return {}

        except Exception as e:
            logger.debug(f"Erro ao buscar da API: {e}")
            return {}

    def favorite_product(self, product_url: str, username: str, password: str) -> bool:
        """Favorita um produto (requer autenticação)"""
        try:
            # Esta função requereria automação de browser (Selenium/Playwright)
            # Por enquanto, apenas log
            logger.info(f"Função de favoritar requer autenticação - implementar com Playwright")
            return False

        except Exception as e:
            logger.error(f"Erro ao favoritar produto: {e}")
            return False
