"""
Miniaturas da variação de cores do produto, recortadas da página do vendedor.
Primeiro localiza a linha "Cor" pelos rótulos da página; se não achar, a IA aponta as miniaturas no print.
"""

import base64
import io
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from PIL import Image

from claude_client import ask_json
from video_page_reader import PROFILE_DIR

logger = logging.getLogger(__name__)

VIEWPORT = {'width': 1280, 'height': 900}
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
LABELS = ['cor', 'cores', 'cor do produto', 'cores disponiveis']
MAX_OPTIONS = 8
SEARCH_HEIGHT = 1600

MARK_COLOR_ROW_JS = """
(labels) => {
  const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().toLowerCase();
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;
    if (!labels.includes(norm(el.textContent || '').replace(/:$/, ''))) continue;
    let row = el.parentElement;
    for (let i = 0; i < 3 && row; i++, row = row.parentElement) {
      if (row.querySelectorAll('button, [role=button]').length >= 2) {
        row.setAttribute('data-sv-cores', '1');
        return true;
      }
    }
  }
  return false;
}
"""

BOXES_SCHEMA = {
    'type': 'object',
    'properties': {
        'opcoes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'x0': {'type': 'integer'}, 'y0': {'type': 'integer'},
                           'x1': {'type': 'integer'}, 'y1': {'type': 'integer'}},
            'required': ['x0', 'y0', 'x1', 'y1'], 'additionalProperties': False}},
    },
    'required': ['opcoes'],
    'additionalProperties': False,
}


def _download_original(page, img) -> Optional[bytes]:
    """Baixa a imagem da cor em resolução cheia (na Shopee, sem o sufixo _tn de miniatura)."""
    src = img.evaluate('el => el.currentSrc || el.src') or ''
    if not src.startswith('http'):
        return None
    src = re.sub(r'_tn(?=$|[?.])', '', src)
    try:
        resp = page.request.get(src, timeout=20000)
        if resp.ok and resp.headers.get('content-type', '').startswith('image/'):
            return resp.body()
    except Exception as e:
        logger.debug(f"Imagem original indisponível ({src}): {e}")
    return None


def _boxes_by_ai(png: bytes, width: int, height: int) -> List[dict]:
    data = ask_json([
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                     'data': base64.standard_b64encode(png).decode()}},
        {'type': 'text', 'text': (
            f"Print da página de um produto da Shopee ({width}x{height} px). "
            "Na linha de variação de COR, localize a MINIATURA (imagem) de cada opção de cor, na ordem da página. "
            "Devolva uma caixa por miniatura, em pixels desta imagem, só a imagem (sem o texto do nome). "
            "Se não houver variação de cor com miniaturas, devolva a lista vazia.")},
    ], BOXES_SCHEMA, max_tokens=3000)
    return [b for b in data['opcoes'] if b['x1'] > b['x0'] and b['y1'] > b['y0']][:MAX_OPTIONS]


def capture_color_thumbs(product_url: str, out_dir: Path, wait_ms: int = 5000) -> List[Path]:
    """Salva uma imagem por opção de cor em `out_dir`. Lista vazia se o produto não tiver cores."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    headless = os.getenv('SHOPEE_BROWSER_HEADLESS', 'true').lower() != 'false'
    shots: List[bytes] = []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, locale='pt-BR',
            viewport=VIEWPORT, user_agent=USER_AGENT, device_scale_factor=2)
        page = context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(wait_ms)
            page.keyboard.press('Escape')
            if page.evaluate(MARK_COLOR_ROW_JS, LABELS):
                options = page.locator('[data-sv-cores] button, [data-sv-cores] [role=button]')
                for i in range(min(options.count(), MAX_OPTIONS)):
                    option = options.nth(i)
                    img = option.locator('img')
                    original = _download_original(page, img.first) if img.count() else None
                    if original:
                        shots.append(original)
                        continue
                    target = img.first if img.count() else option
                    target.scroll_into_view_if_needed()
                    shots.append(target.screenshot())
                source = 'rótulos da página'
            else:
                png = page.screenshot(clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': SEARCH_HEIGHT},
                                      full_page=True, scale='css')
                for b in _boxes_by_ai(png, VIEWPORT['width'], SEARCH_HEIGHT):
                    shots.append(page.screenshot(full_page=True, clip={
                        'x': b['x0'], 'y': b['y0'], 'width': b['x1'] - b['x0'], 'height': b['y1'] - b['y0']}))
                source = 'IA'
        finally:
            context.close()

    paths = []
    for i, png in enumerate(shots):
        path = out_dir / f"cor_{i}.png"
        Image.open(io.BytesIO(png)).convert('RGB').save(path)
        paths.append(path)
    logger.info(f"{len(paths)} miniatura(s) de cor ({source if shots else 'nenhuma'})")
    return paths
