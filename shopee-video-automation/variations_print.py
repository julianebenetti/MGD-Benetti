"""
Miniaturas das variações a partir do print que a Juliane manda (app ou site da Shopee).
A IA localiza cada miniatura; o robô recorta da imagem original.
"""

import base64
import io
import logging
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from ai_client import ask_json

logger = logging.getLogger(__name__)

MAX_SIDE = 1600
MAX_OPTIONS = 8

SCHEMA = {
    'type': 'object',
    'properties': {
        'total': {'type': 'integer'},
        'miniaturas': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'x0': {'type': 'integer'}, 'y0': {'type': 'integer'},
                           'x1': {'type': 'integer'}, 'y1': {'type': 'integer'}},
            'required': ['x0', 'y0', 'x1', 'y1'], 'additionalProperties': False}},
    },
    'required': ['total', 'miniaturas'],
    'additionalProperties': False,
}

PROMPT = """Este é um print da Shopee (app ou site) mostrando as VARIAÇÕES de um produto
(ex.: "5 variações disponíveis", ou as opções de Cor/Modelo com miniaturas). A imagem tem {w}x{h} pixels.

- total: quantas variações o produto tem. Se aparecer o texto "N variações disponíveis", use N;
  senão, conte as opções visíveis.
- miniaturas: uma caixa por MINIATURA (a foto de cada opção), na ordem da tela, em pixels desta imagem.
  Só a foto, sem o nome da opção, sem bordas de seleção, sem preço ou botões.
Se não houver miniaturas de variação na imagem, devolva total 0 e lista vazia."""


def thumbs_from_print(image_path: str, out_dir: Path) -> Tuple[List[Path], int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(image_path).convert('RGB')
    scale = min(1.0, MAX_SIDE / max(original.size))
    small = original.resize((round(original.width * scale), round(original.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, 'JPEG', quality=90)

    data = ask_json([
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                     'data': base64.standard_b64encode(buf.getvalue()).decode()}},
        {'type': 'text', 'text': PROMPT.format(w=small.width, h=small.height)},
    ], SCHEMA, name='variacoes')

    paths = []
    for i, b in enumerate(data['miniaturas'][:MAX_OPTIONS]):
        x0, y0, x1, y1 = (round(v / scale) for v in (b['x0'], b['y0'], b['x1'], b['y1']))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(original.width, x1), min(original.height, y1)
        if x1 - x0 < 12 or y1 - y0 < 12:
            continue
        path = out_dir / f"variacao_{i}.png"
        original.crop((x0, y0, x1, y1)).save(path)
        paths.append(path)
    total = max(data['total'], len(paths))
    logger.info(f"Print das variações: {len(paths)} miniatura(s), total {total}")
    return paths, total
