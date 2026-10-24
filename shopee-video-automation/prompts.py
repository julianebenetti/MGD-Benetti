"""
Prompts para gerar os vídeos com IA no YouTube Create (tópico 🎬 Prompts), com as regras da Juliane:
até 900 caracteres, narração feminina em PT-BR (gancho → objeção → benefício → urgência responsável → CTA),
fidelidade visual à imagem do anúncio, movimentos POV naturais e nenhuma escrita na tela.
"""

import base64
import html
import io
import re
from typing import Dict, Optional

import requests
from PIL import Image

from ai_client import ask_json

MAX_CHARS = 900   # limite do YouTube Create (instruções + narração)
NARRATION_MAX = 320   # a narração precisa caber inteira (até o CTA); o resto fica para as instruções do vídeo
CTA_WORDS = ('carrinho', 'garanta', 'garante', 'confira', 'confere', 'aproveite', 'aproveita', 'compre', 'compra',
             'link', 'sacolinha', 'toque', 'toca', 'clique')

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
10. Mostrar e citar 2 ou 3 benefícios práticos REAIS do produto (ex.: antiaderente, usa menos óleo, fácil de
    limpar, monta sem ferramenta), na cena e na narração, sem promessas exageradas.
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

ESTILO ENXUTO: nas instruções do vídeo use abreviações claras para economizar caracteres (ex.: "Vídeo POV 9:16",
"ref. fiel", "mov. suaves", "luz natural", "nº de peças", "Sem textos/legendas/preços na tela", "Narração fem.
PT/BR:"). NUNCA abrevie dentro da narração (ela é falada em voz alta).

TAMANHO: instruções do vídeo com até 550 caracteres e narração com até 300 (as duas juntas nunca passam de
{MAX_CHARS}). A narração tem que vir INTEIRA, com as 5 partes, terminando no CTA e fechando as aspas.

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


# Abreviações nas INSTRUÇÕES do vídeo (nunca dentro da narração, que é falada): economizam caracteres sem
# perder o sentido. (padrão, troca)
ABBREVIATIONS = [
    (r'narra[çc][ãa]o feminina em portugu[êe]s (do )?brasileiro', 'Narração fem. PT/BR'),
    (r'narra[çc][ãa]o feminina em portugu[êe]s do brasil', 'Narração fem. PT/BR'),
    (r'crie um v[íi]deo (promocional )?(pov )?vertical 9:16', 'Vídeo POV 9:16'),
    (r'crie um v[íi]deo (promocional )?vertical 9:16, estilo pov', 'Vídeo POV 9:16'),
    (r'use a imagem enviada como refer[êe]ncia (obrigat[óo]ria|fiel)', 'Use a imagem enviada como ref. fiel'),
    (r'preserve a fidelidade visual absoluta d[oa]', 'preserve'),
    (r'n[ãa]o adicione textos?, legendas?, t[íi]tulos?, pre[çc]os?, logotipos? ou qualquer escrita na tela',
     'Sem textos/legendas/preços/logos na tela'),
    (r'n[ãa]o adicione textos?, legendas?, t[íi]tulos?, pre[çc]os? ou qualquer escrita na tela',
     'Sem textos/legendas/preços na tela'),
    (r'quantidade de pe[çc]as', 'nº de peças'),
    (r'movimentos suaves( de c[âa]mera| e realistas)?', 'mov. suaves'),
    (r'movimentos realistas', 'mov. realistas'),
    (r'ilumina[çc][ãa]o natural', 'luz natural'),
    (r'\bcent[íi]metros\b', 'cm'),
    (r'\bcom\b (?=\d)', 'c/ '),
]


def compact(prompt: str) -> str:
    """Aplica as abreviações nas instruções (e no rótulo da narração); a fala entre aspas fica intacta."""
    i = re.search(r'narra[çc][ãa]o[^:“"]*:', prompt, re.IGNORECASE)
    head, speech = (prompt[:i.end()], prompt[i.end():]) if i else (prompt, '')
    for pattern, short in ABBREVIATIONS:
        head = re.sub(pattern, short, head, flags=re.IGNORECASE)
    return (head + speech).strip()


def _split(prompt: str):
    """(instruções do vídeo, narração) — a narração começa em "Narração"."""
    i = prompt.find('Narração')
    return (prompt, '') if i < 0 else (prompt[:i].rstrip(), prompt[i:].strip())


def problems(prompt: str) -> list:
    """O que está errado no prompt: tamanho, narração faltando, sem CTA ou cortada."""
    found = []
    _, narration = _split(prompt)
    if len(prompt) > MAX_CHARS:
        found.append(f"tem {len(prompt)} caracteres (máximo {MAX_CHARS})")
    if not narration:
        found.append('falta a narração ("Narração feminina em português brasileiro: “…”")')
    else:
        quote = narration.split(':', 1)[-1]
        if not quote.rstrip().endswith(('”', '"')):
            found.append('a narração não termina fechando as aspas (está cortada)')
        if not any(w in quote.lower()[-160:] for w in CTA_WORDS):
            found.append('a narração não termina com um CTA (ex.: "Toque no carrinho e garanta o seu!")')
    return found


def _fit(prompt: str) -> str:
    """
    Último recurso para caber em MAX_CHARS sem nunca cortar a narração: encurta as instruções do vídeo (no fim de
    uma frase) e mantém a narração inteira, com o CTA.
    """
    if len(prompt) <= MAX_CHARS:
        return prompt
    instructions, narration = _split(prompt)
    budget = MAX_CHARS - len(narration) - 1
    if not narration or budget < 200:
        cut = prompt[:MAX_CHARS]
        end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
        return cut[:end + 1] if end > MAX_CHARS // 2 else cut.rstrip()
    sentences = re.split(r'(?<=[.!?])\s+', instructions)

    def priority(sentence: str) -> int:
        low = sentence.lower()
        if 'imagem enviada' in low or 'não adicione' in low or 'escrita' in low:
            return 0   # fidelidade ao produto e nada escrito na tela: nunca sai
        if low.startswith('mostre'):
            return 1   # a cena de uso: a última a sair
        if low.startswith('crie'):
            return 2   # abertura (tipo de vídeo)
        return 3       # o resto (ambiente, reforços) sai primeiro
    chosen = set(range(len(sentences)))
    for i in sorted(range(len(sentences)), key=lambda i: (-priority(sentences[i]), -i)):
        if len(' '.join(sentences[j] for j in sorted(chosen))) <= budget:
            break
        if priority(sentences[i]) > 0:
            chosen.discard(i)
    kept = [sentences[j] for j in sorted(chosen)]
    return f"{' '.join(kept)} {narration}"


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
    data['prompt'] = compact(data['prompt'])
    for _ in range(2):   # passou do limite ou a narração veio sem CTA/cortada: pede para corrigir
        issues = problems(data['prompt'].strip())
        if not issues:
            break
        data = ask_json([*images, {'type': 'text', 'text': text + "\n\nO prompt abaixo tem problemas: "
                                   + '; '.join(issues) + f". Reescreva com no máximo {MAX_CHARS - 80} caracteres, "
                                   "instruções do vídeo mais curtas e a narração INTEIRA (gancho, objeção, benefício, "
                                   f"urgência e CTA, fechando as aspas):\n{data['prompt']}"}], SCHEMA, name='prompt_video')
        data['prompt'] = compact(data['prompt'])
    data['prompt'] = _fit(data['prompt'].strip())
    return data


def render(product: Dict, data: Dict, url: str) -> str:
    """Mensagem de informações (o prompt vai sozinho na mensagem seguinte, para copiar só ele)."""
    e = html.escape
    fixed = '\n'.join(f"• {e(d)}" for d in data['detalhes_fixos'])
    return (f"🎬 <b>{e(product['productName'][:90])}</b>\n{e(url)}\n"
            f"Prompt com {len(data['prompt'])}/{MAX_CHARS} caracteres na mensagem abaixo: toque e segure → Copiar.\n\n"
            f"🔒 <b>Conferir no vídeo gerado</b>\n{fixed}\n🔎 {e(data['conferir'])}\n\n"
            f"<i>Use a foto principal do anúncio como base. Para ajustar, responda o prompt "
            f"(ex.: \"mais curto\", \"gancho com pergunta\").</i>")[:4000]


def prompt_only(data: Dict) -> str:
    """Só o prompt, sem nada junto: copiar a mensagem copia exatamente o prompt."""
    return html.escape(data['prompt'])
