"""
Prompts para gerar os vídeos com IA no YouTube Create (tópico 🎬 Prompts), com as regras da Juliane:
até 900 caracteres, narração feminina em PT-BR (gancho → objeção → benefício → urgência responsável → CTA),
fidelidade visual à imagem do anúncio, movimentos POV naturais e nenhuma escrita na tela.
"""

import base64
import html
import io
from typing import Dict, Optional

import requests
from PIL import Image

from ai_client import ask_json

MAX_CHARS = 900   # limite do YouTube Create (instruções + narração)

SCHEMA = {
    'type': 'object',
    'properties': {
        'detalhes_fixos': {'type': 'array', 'items': {'type': 'string'}},
        'prompt': {'type': 'string'},
        'conferir': {'type': 'string'},
    },
    'required': ['detalhes_fixos', 'prompt', 'conferir'],
    'additionalProperties': False,
}

RULES = f"""Você cria o prompt de um vídeo promocional curto no YouTube Create para o perfil Achados Relâmpagos
(Shopee Vídeo). A imagem anexa é a foto principal do anúncio e será enviada como base do vídeo.

REGRAS OBRIGATÓRIAS DO PROMPT
1. No máximo {MAX_CHARS} caracteres no total (instruções + narração, contando espaços e pontuação).
2. Narração feminina em português brasileiro, natural, persuasiva, para vídeo curto.
3. Quebrar objeções (preço, praticidade, qualidade, conforto, durabilidade, facilidade de uso) só com informações
   reais do produto (nome, foto, nota e vendas abaixo). Sem citar valores, descontos ou cupons.
4. Começar com uma pergunta, situação do dia a dia ou frase que prenda a atenção.
5. Urgência sem inventar estoque limitado, desconto ou prazo.
6. Terminar a narração com CTA (conferir, aproveitar ou comprar).
7. Fidelidade visual absoluta: usar a imagem enviada como referência e preservar cores, formato, proporções, marca,
   detalhes e características; não inventar nem modificar o produto. Na frase "preserve …", cite os detalhes
   concretos que um gerador de vídeo mais costuma mudar neste produto (quantidade de peças/barras, tamanhos,
   estampa/flores, cores de cada parte, formato).
8. Movimentos POV suaves, realistas e coerentes com o uso do produto; sem gestos artificiais nem mudanças bruscas.
9. Nenhuma escrita na tela: proibir legendas, títulos, palavras, preços, logotipos ou texto sobreposto.
10. Mostrar benefícios práticos (como facilita a rotina), sem promessas exageradas.
11. Simples e direto: poucas cenas, nada contraditório, sem efeitos desnecessários.

ESTRUTURA DA NARRAÇÃO: 1) gancho; 2) quebra de objeção com um diferencial verdadeiro; 3) benefício e curiosidade;
4) urgência responsável; 5) CTA final.

FORMATO (o mesmo que a Juliane usa), em um parágrafo corrido:
"Crie um vídeo POV vertical 9:16, realista e natural, … Use a imagem enviada como referência fiel/obrigatória e preserve
<detalhes concretos: quantidade de peças, tamanhos, cores, estampa, materiais>. Não altere cores, proporções, textura,
quantidade de peças ou detalhes. Mostre <cena de uso real, com ações do dia a dia>, destacando <benefícios práticos>.
Movimentos suaves e realistas, iluminação natural, <ambiente>. Não adicione textos, legendas, títulos, preços ou
qualquer escrita na tela. Narração feminina em português brasileiro: “<narração>”"

EXEMPLO DA JULIANE (estilo e tamanho de referência, não copie o conteúdo):
Crie um vídeo promocional vertical 9:16, estilo POV natural, com movimentos suaves de câmera, como uma pessoa
mostrando o produto de perto. Use a imagem enviada como referência obrigatória e preserve a fidelidade visual absoluta
do conjunto de 3 frigideiras: formato, tamanhos de 14, 18 e 24 cm, exterior vermelho com pintinhas claras, interior
preto com revestimento salpicado e cabos pretos. Não altere cores, proporções, textura, quantidade de peças ou
detalhes. Mostre as frigideiras no fogão preparando ovo, panqueca e omelete, destacando o revestimento antiaderente,
o preparo prático, o uso de menos óleo e a facilidade de limpeza. Movimentos realistas, iluminação natural e cozinha
aconchegante. Narração feminina em português brasileiro: “Três frigideiras para facilitar sua rotina! Prepare ovos,
panquecas e muito mais com revestimento antiaderente e limpeza prática. Mais praticidade na sua cozinha! Toque no
carrinho e garanta seu conjunto!”

Se houver PRINTS DO ANÚNCIO anexos (depois da foto principal), use os dados deles (medidas, materiais, garantia,
certificações, itens do kit) como fatos reais para descrever o produto e quebrar objeções. Nunca use preço.

CAMPOS
- detalhes_fixos: os detalhes da foto que não podem mudar no vídeo (para a Juliane conferir), em português.
- prompt: o prompt final, pronto para copiar e colar, em português, com até {MAX_CHARS} caracteres.
- conferir: 1 frase dizendo o que conferir no vídeo gerado antes de mandar (o detalhe mais arriscado)."""


def _photo_b64(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert('RGB')
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode()


def _facts(product: Dict) -> str:
    facts = [f"PRODUTO DO ANÚNCIO: {product['productName']}"]
    if product.get('ratingStar'):
        facts.append(f"Nota: {product['ratingStar']}")
    if product.get('sales'):
        facts.append(f"Vendidos: {product['sales']}")
    return '\n'.join(facts)


def _trim(prompt: str) -> str:
    """Último recurso: corta no fim de uma frase para caber nos 900 caracteres."""
    if len(prompt) <= MAX_CHARS:
        return prompt
    cut = prompt[:MAX_CHARS]
    end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return cut[:end + 1] if end > MAX_CHARS // 2 else cut.rstrip()


def _file_b64(path: str) -> str:
    img = Image.open(path).convert('RGB')
    img.thumbnail((1400, 1400))   # prints com texto: um pouco mais de resolução
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode()


def build(product: Dict, notes: str = '', previous: Optional[Dict] = None, request: str = '',
          prints: Optional[list] = None) -> Dict:
    """
    Prompt novo (ou ajustado, com `previous` + `request`) a partir da foto e dos dados do anúncio. `prints`:
    caminhos de prints do anúncio (medidas, garantia…) que a Juliane mandou, usados como fatos reais.
    """
    text = f"{RULES}\n\n{_facts(product)}"
    if notes:
        text += f"\nOBSERVAÇÕES DA JULIANE: {notes}"
    if previous:
        text += (f"\n\nPROMPT ANTERIOR:\n{previous.get('prompt', '')}\n\nAJUSTE PEDIDO: {request}\n"
                 "Refaça seguindo todas as regras.")
    images = [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                           'data': _photo_b64(product['imageUrl'])}}]
    for path in (prints or [])[:4]:
        images.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                                   'data': _file_b64(path)}})
    if len(images) > 1:
        text += f"\n\n(As {len(images) - 1} imagem(ns) depois da foto principal são PRINTS DO ANÚNCIO.)"
    data = ask_json([*images, {'type': 'text', 'text': text}], SCHEMA, name='prompt_video')
    if len(data['prompt']) > MAX_CHARS:   # passou do limite: pede para encurtar uma vez
        data = ask_json([*images, {'type': 'text', 'text': text + f"\n\nO prompt abaixo tem {len(data['prompt'])} "
                                 f"caracteres. Reescreva com no máximo {MAX_CHARS - 40}, mantendo todas as regras:\n"
                                 f"{data['prompt']}"}], SCHEMA, name='prompt_video')
    data['prompt'] = _trim(data['prompt'].strip())
    return data


def render(product: Dict, data: Dict, url: str) -> str:
    e = html.escape
    fixed = '\n'.join(f"• {e(d)}" for d in data['detalhes_fixos'])
    return (f"🎬 <b>{e(product['productName'][:90])}</b>\n{e(url)}\n\n"
            f"✍️ <b>Prompt</b> ({len(data['prompt'])}/{MAX_CHARS} caracteres · toque para copiar)\n"
            f"<code>{e(data['prompt'])}</code>\n\n"
            f"🔒 <b>Conferir no vídeo gerado</b>\n{fixed}\n🔎 {e(data['conferir'])}\n\n"
            f"<i>Use a foto principal do anúncio como base. Responda esta mensagem para ajustar "
            f"(ex.: \"mais curto\", \"gancho com pergunta\").</i>")[:4000]
