#!/usr/bin/env python3
"""
Diagnóstico do cartão de variações: abre a página do produto como o robô abre e manda para a pasta
Envios o print da página e o que foi encontrado.  Uso: .venv/bin/python diagnostico.py <link do produto>
"""

import html
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from product_page_capture import capture_variation_thumbs  # noqa: E402
from shopee_affiliate import ShopeeAffiliateClient  # noqa: E402
from shopee_session import COOKIES_FILE  # noqa: E402
from telegram_handler import TelegramBot  # noqa: E402


def main(link: str):
    from shopee_session import PAGES_ENABLED
    if not PAGES_ENABLED:
        sys.exit("Visitas às páginas da Shopee estão desligadas (SHOPEE_ACESSAR_PAGINAS=nao) para proteger a conta.")
    shopee = ShopeeAffiliateClient(os.environ['SHOPEE_AFFILIATE_APP_ID'], os.environ['SHOPEE_AFFILIATE_SECRET'])
    tg = TelegramBot(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'])
    envios = int(os.getenv('TELEGRAM_TOPIC_ENVIOS') or 0) or None

    products = shopee.find_candidates(link)
    if not products:
        print(f"Produto não encontrado (o link abriu em {shopee.last_final_url})")
        return
    p = products[0]
    url = f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"
    print(f"Produto: {p['productName']}\nPágina: {url}")

    shot = Path(tempfile.mkdtemp()) / 'pagina.png'
    debug = {'shot': shot, 'url': '-', 'title': '-', 'source': '-'}
    try:
        thumbs, total = capture_variation_thumbs(url, Path(tempfile.mkdtemp()), debug=debug)
    except Exception as e:
        thumbs, total = [], f"0 ({e.__class__.__name__})"
    resumo = (f"🔎 Diagnóstico das variações\n"
              f"Produto: {p['productName']}\n"
              f"Cookies de login: {'sim' if COOKIES_FILE.exists() else 'NÃO'}\n"
              f"Navegador: {os.getenv('SHOPEE_BROWSER_MODE', 'auto')}\n"
              f"Página aberta: {debug['url']}\n"
              f"Título: {debug['title']}\n"
              f"Origem das variações: {debug['source']}\n"
              f"Miniaturas capturadas: {len(thumbs)} de {total}")
    print(resumo)
    if shot.exists():
        tg.send_photo(envios, str(shot), html.escape(resumo)[:1024])
    else:
        tg.send_text(envios, html.escape(resumo))
    print("Print enviado para a pasta Envios.")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("Uso: .venv/bin/python diagnostico.py <link do produto>")
    main(sys.argv[1])
