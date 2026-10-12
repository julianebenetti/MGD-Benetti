"""
Miniaturas das "Variações Disponíveis" do produto (cor, modelo, voltagem, kit...), da página do vendedor.
Procura o bloco "N variações disponíveis" ou a linha de variação com imagens; se não achar,
a IA aponta as miniaturas no print.
"""

import base64
import io
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from ai_client import ask_json
from shopee_session import is_blocked, launch
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

# Acha as variações e devolve {total, items: [{src, x, y, w, h}]} num único instante
# (a página da Shopee se redesenha enquanto carrega, então nada é marcado no DOM).
# Prioridade: bloco "N variações disponíveis" > linha de variação com imagens > primeira linha rotulada.
FIND_VARIATIONS_JS = """
(labels) => {
  const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().toLowerCase();
  const bgUrl = n => { const m = getComputedStyle(n).backgroundImage.match(/url\\(["']?(.*?)["']?\\)/); return m ? m[1] : null; };
  const imgOf = el => {
    const img = el.tagName === 'IMG' ? el : el.querySelector('img');
    if (img) return {el: img, src: img.currentSrc || img.src || img.getAttribute('data-src') || ''};
    for (const n of [el, ...el.querySelectorAll('*')]) { const u = bgUrl(n); if (u) return {el: n, src: u}; }
    return null;
  };
  const isOption = b => imgOf(b) || !/(carrinho|comprar|^[-+]$|^$)/.test(norm(b.innerText || b.getAttribute('aria-label') || ''));
  const describe = (els, total) => ({total, items: els.map(o => {
    const im = imgOf(o); const target = im ? im.el : o;
    target.scrollIntoView({block: 'center'});
    const r = target.getBoundingClientRect();
    return {src: im ? im.src : '', x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
  })});
  const leaves = [...document.querySelectorAll('body *')].filter(el => !el.children.length);

  for (const el of leaves) {
    const m = norm(el.textContent || '').match(/^(\\d+)\\s+variac(oes|ao)\\s+disponive(is|l)$/);
    if (!m) continue;
    let box = el.parentElement;
    for (let i = 0; i < 4 && box; i++, box = box.parentElement) {
      const imgs = [...box.querySelectorAll('img')];
      if (imgs.length >= 2) return describe(imgs, parseInt(m[1]));
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
        const withImg = opts.filter(o => imgOf(o)).length;
        if (labels.includes(label) || withImg >= 2) rows.push({row, opts, withImg});
        break;
      }
    }
  }
  // fica só com as linhas mais internas (um bloco que contém várias linhas não é uma variação)
  const inner = rows.filter(r => !rows.some(o => o.row !== r.row && r.row.contains(o.row)));
  const chosen = inner.find(r => r.withImg >= 2) || inner[0];
  return chosen ? describe(chosen.opts, chosen.opts.length) : {total: 0, items: []};
}
"""
FIND_TIMEOUT_MS = 15000


def find_variations(page) -> dict:
    """Tenta por até FIND_TIMEOUT_MS: as variações costumam aparecer alguns segundos depois do resto."""
    waited, found = 0, {'total': 0, 'items': []}
    while waited <= FIND_TIMEOUT_MS:
        found = page.evaluate(FIND_VARIATIONS_JS, LABELS)
        if found['total']:
            page.wait_for_timeout(1000)  # deixa as miniaturas terminarem de carregar e lê de novo
            return page.evaluate(FIND_VARIATIONS_JS, LABELS) or found
        page.wait_for_timeout(1000)
        waited += 1000
    return found


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


def _download_original(page, src: str) -> Optional[bytes]:
    """Baixa a imagem da variação em resolução cheia (na Shopee, sem o sufixo _tn de miniatura)."""
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


IMAGE_CDN = 'https://down-br.img.susercontent.com/file/'


def _tiers_in_json(data) -> List[dict]:
    """Procura 'tier_variations' (nome, opções e imagens de cada variação) no JSON da página."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            tiers = node.get('tier_variations')
            if isinstance(tiers, list) and tiers and isinstance(tiers[0], dict):
                found.extend(tiers)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


def _pick_tier(tiers: List[dict]) -> Optional[dict]:
    with_images = [t for t in tiers if len([i for i in (t.get('images') or []) if i]) >= 2]
    with_options = [t for t in tiers if len(t.get('options') or []) >= 2]
    return (with_images or with_options or [None])[0]


def capture_variation_thumbs(product_url: str, out_dir: Path, wait_ms: int = 5000,
                             debug: Optional[dict] = None) -> Tuple[List[Path], int]:
    """
    Salva uma imagem por variação em `out_dir` (até MAX_OPTIONS).
    Devolve (imagens, total de variações). Lista vazia se o produto não tiver variações.
    Ordem: dados que a página recebe (tier_variations) > o que aparece na tela > IA no print.
    `debug` (opcional) recebe url, título, origem e o print da página em debug['shot'].
    """
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    shots: List[bytes] = []
    total, source = 0, 'nenhuma'
    tiers: List[dict] = []

    def on_response(response):
        if 'shopee' in response.url and 'json' in response.headers.get('content-type', ''):
            try:
                tiers.extend(_tiers_in_json(response.json()))
            except Exception:
                pass

    with sync_playwright() as p:
        context = launch(p, PROFILE_DIR, viewport=VIEWPORT, user_agent=USER_AGENT, device_scale_factor=2)
        page = context.new_page()
        page.on('response', on_response)
        try:
            page.goto(product_url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(wait_ms)
            if debug is not None:
                debug.update(url=page.url, title=page.title())
            if is_blocked(page.url):
                raise ShopeeBlocked(page.url)
            page.keyboard.press('Escape')

            tier = _pick_tier(tiers)
            if tier:
                total = len(tier.get('options') or [])
                for h in [i for i in (tier.get('images') or []) if i][:MAX_OPTIONS]:
                    img = _download_original(page, h if h.startswith('http') else IMAGE_CDN + h)
                    if img:
                        shots.append(img)
                source = f"dados da página ({tier.get('name', 'variação')})"

            if not shots:
                found = find_variations(page)
                if found['total']:
                    total = found['total']
                    for item in found['items'][:MAX_OPTIONS]:
                        original = _download_original(page, item['src'])
                        if original:
                            shots.append(original)
                        elif item['w'] > 4 and item['h'] > 4:
                            shots.append(page.screenshot(full_page=True, clip={
                                'x': item['x'], 'y': item['y'], 'width': item['w'], 'height': item['h']}))
                    source = 'tela'

            if not shots and not total:
                png = page.screenshot(clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': SEARCH_HEIGHT},
                                      full_page=True, scale='css')
                for b in _boxes_by_ai(png, VIEWPORT['width'], SEARCH_HEIGHT):
                    shots.append(page.screenshot(full_page=True, clip={
                        'x': b['x0'], 'y': b['y0'], 'width': b['x1'] - b['x0'], 'height': b['y1'] - b['y0']}))
                total = len(shots)
                source = 'IA' if shots else 'nenhuma'
        finally:
            if debug is not None:
                debug['source'] = source
                try:
                    page.evaluate('window.scrollTo(0, 0)')
                    page.screenshot(path=str(debug['shot']), scale='css', full_page=True,
                                    clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'], 'height': 1400})
                except Exception:
                    pass
            context.close()

    paths = []
    for i, png in enumerate(shots):
        path = out_dir / f"variacao_{i}.png"
        Image.open(io.BytesIO(png)).convert('RGB').save(path)
        paths.append(path)
    logger.info(f"{len(paths)} de {total} variação(ões) ({source})")
    return paths, max(total, len(paths))
