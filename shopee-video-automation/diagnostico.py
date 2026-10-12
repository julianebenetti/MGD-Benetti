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

from product_page_capture import (USER_AGENT, VIEWPORT, capture_variation_thumbs,  # noqa: E402
                                  find_variations)
from shopee_affiliate import ShopeeAffiliateClient  # noqa: E402
from shopee_session import COOKIES_FILE, apply_session  # noqa: E402
from telegram_handler import TelegramBot  # noqa: E402
from video_page_reader import PROFILE_DIR  # noqa: E402


def main(link: str):
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

    from playwright.sync_api import sync_playwright
    shot = Path(tempfile.mkdtemp()) / 'pagina.png'
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=os.getenv('SHOPEE_BROWSER_HEADLESS', 'true').lower() != 'false',
            locale='pt-BR', viewport=VIEWPORT, user_agent=USER_AGENT)
        apply_session(ctx)
        page = ctx.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(5000)
        page.keyboard.press('Escape')
        final_url, title = page.url, page.title()
        found = find_variations(page)['total']
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(shot), clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': 1400},
                        full_page=True)
        ctx.close()

    try:
        thumbs, total = capture_variation_thumbs(url, Path(tempfile.mkdtemp()))
    except Exception as e:
        thumbs, total = [], f"0 ({e.__class__.__name__})"
    resumo = (f"🔎 Diagnóstico das variações\n"
              f"Produto: {p['productName']}\n"
              f"Cookies de login: {'sim' if COOKIES_FILE.exists() else 'NÃO'}\n"
              f"Página aberta: {final_url}\n"
              f"Título: {title}\n"
              f"Variações achadas na página: {found}\n"
              f"Miniaturas capturadas: {len(thumbs)} de {total}")
    print(resumo)
    tg.send_photo(envios, str(shot), html.escape(resumo)[:1024])
    print("Print enviado para a pasta Envios.")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("Uso: .venv/bin/python diagnostico.py <link do produto>")
    main(sys.argv[1])
