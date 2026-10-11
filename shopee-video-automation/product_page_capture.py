"""
Print da variação de cores do produto na página do vendedor, recortado.
Primeiro localiza o bloco pelos rótulos da página; se não achar, a IA aponta a área no print.
"""

import base64
import io
import logging
import os
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageChops

from claude_client import ask_json
from video_page_reader import PROFILE_DIR

logger = logging.getLogger(__name__)

VIEWPORT = {'width': 1280, 'height': 900}
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
LABELS = ['cor', 'cores', 'cor do produto', 'cores disponiveis']
PADDING = 14
SEARCH_HEIGHT = 1600

FIND_ROWS_JS = """
(labels) => {
  const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().toLowerCase();
  const rects = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;
    if (!labels.includes(norm(el.textContent || '').replace(/:$/, ''))) continue;
    let row = el.parentElement;
    for (let i = 0; i < 3 && row; i++, row = row.parentElement) {
      if (row.querySelectorAll('button, [role=button]').length >= 2) break;
    }
    if (!row) continue;
    const r = row.getBoundingClientRect();
    if (r.width > 80 && r.height > 20 && r.height < 700)
      rects.push([r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY]);
  }
  return rects;
}
"""

BBOX_SCHEMA = {
    'type': 'object',
    'properties': {
        'encontrou': {'type': 'boolean'},
        'x0': {'type': 'integer'}, 'y0': {'type': 'integer'},
        'x1': {'type': 'integer'}, 'y1': {'type': 'integer'},
    },
    'required': ['encontrou', 'x0', 'y0', 'x1', 'y1'],
    'additionalProperties': False,
}


def _trim(img: Image.Image, margin: int = 24) -> Image.Image:
    """Corta as sobras de fundo liso (ex.: espaço vazio à direita das opções)."""
    bg = Image.new('RGB', img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg).convert('L').point(lambda v: 255 if v > 18 else 0)
    box = diff.getbbox()
    if not box:
        return img
    x0, y0, x1, y1 = box
    return img.crop((max(0, x0 - margin), max(0, y0 - margin),
                     min(img.width, x1 + margin), min(img.height, y1 + margin)))


def _union(rects: List[List[float]]):
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def _bbox_by_ai(png: bytes, width: int, height: int):
    data = ask_json([
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                     'data': base64.standard_b64encode(png).decode()}},
        {'type': 'text', 'text': (
            f"Print da página de um produto da Shopee ({width}x{height} px). "
            "Localize SOMENTE a linha de variação de COR do produto: o rótulo (ex.: Cor) com os botões "
            "das cores, incluindo as miniaturas. Não inclua tamanho, preço, frete, quantidade nem botões de compra. "
            "Responda as coordenadas em pixels desta imagem (canto superior esquerdo e inferior direito). "
            "Se o produto não tiver variação de cor, encontrou=false.")},
    ], BBOX_SCHEMA, max_tokens=2000)
    if not data['encontrou'] or data['x1'] <= data['x0'] or data['y1'] <= data['y0']:
        return None
    return data['x0'], data['y0'], data['x1'], data['y1']


def capture_variations(product_url: str, out_path: Path, wait_ms: int = 5000) -> Optional[Path]:
    """Salva o recorte das variações em `out_path` (PNG). None se não houver/achar."""
    from playwright.sync_api import sync_playwright

    headless = os.getenv('SHOPEE_BROWSER_HEADLESS', 'true').lower() != 'false'
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, locale='pt-BR',
            viewport=VIEWPORT, user_agent=USER_AGENT, device_scale_factor=2)
        page = context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(wait_ms)
            page.keyboard.press('Escape')
            rects = page.evaluate(FIND_ROWS_JS, LABELS)
            if rects:
                x0, y0, x1, y1 = _union(rects)
                source = 'rótulos da página'
            else:
                png = page.screenshot(clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': SEARCH_HEIGHT},
                                      full_page=True, scale='css')
                box = _bbox_by_ai(png, VIEWPORT['width'], SEARCH_HEIGHT)
                if not box:
                    logger.info("Produto sem variação de cor encontrada")
                    return None
                x0, y0, x1, y1 = box
                source = 'IA'
            clip = {'x': max(0, x0 - PADDING), 'y': max(0, y0 - PADDING),
                    'width': x1 - x0 + 2 * PADDING, 'height': y1 - y0 + 2 * PADDING}
            png = page.screenshot(clip=clip, full_page=True)
        finally:
            context.close()

    _trim(Image.open(io.BytesIO(png)).convert('RGB')).save(out_path)
    logger.info(f"Print das variações salvo ({source}): {out_path}")
    return out_path
