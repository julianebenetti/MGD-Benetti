"""
Miniaturas das "Variações Disponíveis" do produto (cor, modelo, voltagem, kit...), da página do vendedor.
Procura o bloco "N variações disponíveis" ou a linha de variação com imagens; se não achar,
a IA aponta as miniaturas no print.
"""

import base64
import io
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from ai_client import ask_json
from shopee_session import apply_session, is_blocked
from video_page_reader import PROFILE_DIR

logger = logging.getLogger(__name__)

VIEWPORT = {'width': 1280, 'height': 900}
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
LABELS = ['cor', 'cores', 'modelo', 'modelos', 'variacao', 'variacoes', 'tipo', 'estampa', 'tamanho',
          'voltagem', 'kit', 'opcao', 'opcoes', 'sabor', 'medida', 'capacidade', 'potencia', 'estilo',
          'quantidade de pecas', 'acabamento', 'formato']
MAX_OPTIONS = 8
SEARCH_HEIGHT = 1600

# Marca as opções da variação com data-sv-opt e devolve quantas existem (0 se não achou).
# Prioridade: bloco "N variações disponíveis" > primeira linha de variação com imagens > primeira linha rotulada.
MARK_VARIATIONS_JS = """
(labels) => {
  const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().toLowerCase();
  const isOption = b => !/(carrinho|comprar|^[-+]$|^$)/.test(norm(b.innerText || b.getAttribute('aria-label') || ''))
                        || b.querySelector('img');
  const leaves = [...document.querySelectorAll('body *')].filter(el => !el.children.length);

  for (const el of leaves) {
    const t = norm(el.textContent || '');
    const m = t.match(/^(\\d+)\\s+variac(oes|ao)\\s+disponive(is|l)$/);
    if (!m) continue;
    let box = el.parentElement;
    for (let i = 0; i < 4 && box; i++, box = box.parentElement) {
      const imgs = box.querySelectorAll('img');
      if (imgs.length >= 2) {
        imgs.forEach(img => img.setAttribute('data-sv-opt', '1'));
        return parseInt(m[1]);
      }
    }
  }

  const rows = [];
  for (const el of leaves) {
    const label = norm(el.textContent || '').replace(/:$/, '');
    if (!label || label.length > 25) continue;
    let row = el.parentElement;
    for (let i = 0; i < 3 && row; i++, row = row.parentElement) {
      const opts = [...row.querySelectorAll('button, [role=button]')].filter(isOption);
      if (opts.length >= 2) {
        const withImg = opts.filter(o => o.querySelector('img')).length;
        if (labels.includes(label) || withImg >= 2) rows.push({row, opts, withImg});
        break;
      }
    }
  }
  // fica só com as linhas mais internas (um bloco que contém várias linhas não é uma variação)
  const inner = rows.filter(r => !rows.some(o => o.row !== r.row && r.row.contains(o.row)));
  const chosen = inner.find(r => r.withImg >= 2) || inner[0];
  if (!chosen) return 0;
  chosen.opts.forEach(o => o.setAttribute('data-sv-opt', '1'));
  return chosen.opts.length;
}
"""

class ShopeeBlocked(RuntimeError):
    """A Shopee mostrou 'Login Necessário' em vez da página (faltam os cookies de login)."""


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
    """Baixa a imagem da variação em resolução cheia (na Shopee, sem o sufixo _tn de miniatura)."""
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
            "Localize as VARIAÇÕES DISPONÍVEIS do produto (a linha de opções com miniaturas: cor, modelo, "
            "voltagem, kit etc.; se houver mais de uma linha, use a que tem imagens). Devolva uma caixa por "
            "miniatura, na ordem da página, em pixels desta imagem, só a imagem (sem o texto do nome). "
            "Se o produto não tiver variações com miniaturas, devolva a lista vazia.")},
    ], BOXES_SCHEMA)
    return [b for b in data['opcoes'] if b['x1'] > b['x0'] and b['y1'] > b['y0']][:MAX_OPTIONS]


def capture_variation_thumbs(product_url: str, out_dir: Path, wait_ms: int = 5000) -> Tuple[List[Path], int]:
    """
    Salva uma imagem por variação em `out_dir` (até MAX_OPTIONS).
    Devolve (imagens, total de variações). Lista vazia se o produto não tiver variações.
    """
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    headless = os.getenv('SHOPEE_BROWSER_HEADLESS', 'true').lower() != 'false'
    shots: List[bytes] = []
    total = 0
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, locale='pt-BR',
            viewport=VIEWPORT, user_agent=USER_AGENT, device_scale_factor=2)
        apply_session(context)
        page = context.new_page()
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(wait_ms)
            if is_blocked(page.url):
                raise ShopeeBlocked(page.url)
            page.keyboard.press('Escape')
            total = page.evaluate(MARK_VARIATIONS_JS, LABELS)
            if total:
                options = page.locator('[data-sv-opt]')
                for i in range(min(options.count(), MAX_OPTIONS)):
                    option = options.nth(i)
                    is_img = option.evaluate("el => el.tagName === 'IMG'")
                    img = option if is_img else option.locator('img').first
                    has_img = is_img or option.locator('img').count() > 0
                    original = _download_original(page, img) if has_img else None
                    if original:
                        shots.append(original)
                        continue
                    target = img if has_img else option
                    target.scroll_into_view_if_needed()
                    shots.append(target.screenshot())
                source = 'página'
            else:
                png = page.screenshot(clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': SEARCH_HEIGHT},
                                      full_page=True, scale='css')
                for b in _boxes_by_ai(png, VIEWPORT['width'], SEARCH_HEIGHT):
                    shots.append(page.screenshot(full_page=True, clip={
                        'x': b['x0'], 'y': b['y0'], 'width': b['x1'] - b['x0'], 'height': b['y1'] - b['y0']}))
                total = len(shots)
                source = 'IA'
        finally:
            context.close()

    paths = []
    for i, png in enumerate(shots):
        path = out_dir / f"variacao_{i}.png"
        Image.open(io.BytesIO(png)).convert('RGB').save(path)
        paths.append(path)
    logger.info(f"{len(paths)} de {total} variação(ões) ({source if shots else 'nenhuma'})")
    return paths, max(total, len(paths))
