"""
Prompts para gerar os vídeos com IA (YouTube Create / Veo), no tópico 🎬 Prompts.

A IA olha a foto do anúncio e trava os detalhes que os geradores de vídeo costumam mudar (quantidade de peças,
estampas, flores, formato), para o vídeo não virar "Produto Irrelevante" na Shopee.
"""

import base64
import html
import io
from typing import Dict, Optional

import requests
from PIL import Image

from ai_client import ask_json

SCHEMA = {
    'type': 'object',
    'properties': {
        'detalhes_fixos': {'type': 'array', 'items': {'type': 'string'}},
        'prompt': {'type': 'string'},
        'evitar': {'type': 'string'},
        'cenas': {'type': 'array', 'items': {'type': 'string'}},
        'dica': {'type': 'string'},
    },
    'required': ['detalhes_fixos', 'prompt', 'evitar', 'cenas', 'dica'],
    'additionalProperties': False,
}

RULES = """Você cria prompts para gerar vídeos curtos de produto com IA (YouTube Create / Veo, imagem → vídeo) para o
perfil Achados Relâmpagos no Shopee Vídeo. A Shopee pune como "Produto Irrelevante" quando o produto do vídeo não é
EXATAMENTE o da foto do anúncio, e os geradores de vídeo costumam inventar detalhes. Então:

- detalhes_fixos: olhe a foto e liste, em português, tudo o que NÃO pode mudar: quantidade de peças/barras/
  prateleiras/ganchos (conte!), estampa, flores e desenhos (cor, tamanho, posição), formato, cores de cada parte,
  acessórios, textos/marcas visíveis.
- prompt: em INGLÊS (os geradores entendem melhor), para usar com a foto do anúncio como imagem inicial. Vertical 9:16,
  6 a 8 segundos. Produto parado e inteiro em quadro, câmera com movimento lento e suave (slow push-in ou leve
  orbit), sem cortes, sem transformações. Descreva o produto com os detalhes fixos (contagens e estampas exatas) e
  diga explicitamente para mantê-lo idêntico à imagem de referência. Ambiente coerente com o uso do produto,
  luz natural, visual de "achadinho" bonito. Sem pessoas mexendo no produto, sem texto na tela.
- evitar: em INGLÊS, lista para o campo de "o que evitar"/negative prompt (ex.: changing the print, extra bars,
  different flowers, morphing, extra objects, text, logos).
- cenas: 3 variações curtas do prompt (em inglês), cada uma com outro enquadramento/ambiente, todas com o produto
  idêntico.
- dica: 1 frase em português sobre o que conferir no vídeo gerado antes de mandar (o detalhe mais arriscado)."""


def _photo_b64(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert('RGB')
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode()


def build(product: Dict, notes: str = '', previous: Optional[Dict] = None, request: str = '') -> Dict:
    """Prompt novo (ou ajustado, com `previous` + `request`) a partir da foto e do nome do anúncio."""
    text = f"{RULES}\n\nPRODUTO DO ANÚNCIO: {product['productName']}"
    if notes:
        text += f"\nOBSERVAÇÕES DA JULIANE: {notes}"
    if previous:
        text += (f"\n\nPROMPT ANTERIOR:\n{previous.get('prompt', '')}\n\nAJUSTE PEDIDO: {request}\n"
                 "Refaça mantendo os detalhes fixos do produto.")
    content = [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                            'data': _photo_b64(product['imageUrl'])}},
               {'type': 'text', 'text': text}]
    return ask_json(content, SCHEMA, name='prompt_video')


def render(product: Dict, data: Dict, url: str) -> str:
    e = html.escape
    fixed = '\n'.join(f"• {e(d)}" for d in data['detalhes_fixos'])
    scenes = '\n\n'.join(f"<b>Cena {i}</b>\n<code>{e(c)}</code>" for i, c in enumerate(data['cenas'], 1))
    return (f"🎬 <b>{e(product['productName'][:90])}</b>\n{e(url)}\n\n"
            f"🔒 <b>Não pode mudar no vídeo</b>\n{fixed}\n\n"
            f"✍️ <b>Prompt</b> (use a foto do anúncio como imagem inicial; toque para copiar)\n<code>{e(data['prompt'])}</code>\n\n"
            f"🚫 <b>Evitar</b>\n<code>{e(data['evitar'])}</code>\n\n{scenes}\n\n"
            f"🔎 {e(data['dica'])}\n\n<i>Responda esta mensagem para ajustar (ex.: \"mais movimento\", \"fundo de sala\").</i>")[:4000]
