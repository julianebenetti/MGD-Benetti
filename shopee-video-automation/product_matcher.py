"""
Conferência vídeo × produto por IA: quadros do vídeo + foto e nome do produto.
"""

import base64
import io
import logging
import subprocess
from typing import Dict, List, Tuple

import requests
from PIL import Image

from ai_client import ask_json

logger = logging.getLogger(__name__)

SCHEMA = {
    'type': 'object',
    'properties': {
        'resultado': {'type': 'string', 'enum': ['sim', 'variacao', 'nao', 'incerto']},
        'motivo': {'type': 'string'},
    },
    'required': ['resultado', 'motivo'],
    'additionalProperties': False,
}

PROMPT = """As primeiras imagens são quadros de um vídeo de divulgação. A última é a foto oficial do anúncio na Shopee.
Produto do anúncio: "{name}"

O produto que aparece em destaque no vídeo é este produto do anúncio?
Um anúncio da Shopee vende várias VARIAÇÕES do mesmo produto (cor, estampa, tamanho, modelo, voltagem, kit),
e a foto oficial mostra uma delas.
- "sim": é o mesmo produto, na mesma variação da foto (mesma cor/estampa/modelo)
- "variacao": é o mesmo produto (mesmo tipo e design), mas o vídeo mostra outra variação (outra cor, estampa ou modelo)
- "nao": é claramente outro tipo de produto ou outro design
- "incerto": não dá para afirmar
Em "variacao", diga no motivo qual variação aparece no vídeo e qual aparece na foto.

Em "motivo", explique em uma frase curta, em português."""


def _jpeg_b64(img: Image.Image, max_side: int = 768) -> str:
    img = img.convert('RGB')
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def _video_frames(video_path: str, count: int = 3) -> List[Image.Image]:
    duration = float(subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video_path],
        capture_output=True, text=True, check=True).stdout.strip())
    frames = []
    for i in range(count):
        t = duration * (i + 1) / (count + 1)
        png = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', video_path,
                              '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                             capture_output=True, check=True).stdout
        frames.append(Image.open(io.BytesIO(png)))
    return frames


def _image_block(b64: str) -> Dict:
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}}


def check_match(video_path: str, product: Dict) -> Tuple[str, str]:
    """Devolve (resultado, motivo); resultado é 'sim', 'variacao', 'nao' ou 'incerto'."""
    try:
        content = [_image_block(_jpeg_b64(f)) for f in _video_frames(video_path)]
        photo = requests.get(product['imageUrl'], timeout=30)
        photo.raise_for_status()
        content.append(_image_block(_jpeg_b64(Image.open(io.BytesIO(photo.content)))))
        content.append({'type': 'text', 'text': PROMPT.format(name=product['productName'])})
        data = ask_json(content, SCHEMA)
        logger.info(f"Conferência '{product['productName']}': {data['resultado']} ({data['motivo']})")
        return data['resultado'], data['motivo']
    except Exception as e:
        logger.error(f"Conferência vídeo × produto falhou: {e}")
        return 'incerto', f'não foi possível conferir ({e})'
