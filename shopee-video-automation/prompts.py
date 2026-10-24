"""
Prompts para gerar os vídeos com IA no YouTube Create (tópico 🎬 Prompts), com as regras da Juliane:
até 900 caracteres, narração feminina em PT-BR que vende o benefício principal do produto (curiosidade → objeção →
benefício → urgência verdadeira → CTA),
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
        'beneficios': {'type': 'array', 'items': {'type': 'string'}},
        'detalhes_fixos': {'type': 'array', 'items': {'type': 'string'}},
        'prompt': {'type': 'string'},
        'conferir': {'type': 'string'},
    },
    'required': ['beneficios', 'detalhes_fixos', 'prompt', 'conferir'],
    'additionalProperties': False,
}

RULES = f"""Você cria o prompt de um vídeo promocional curto no YouTube Create para o perfil Achados Relâmpagos
(Shopee Vídeo). A imagem anexa é a foto principal do anúncio e será enviada como base do vídeo.

REGRAS OBRIGATÓRIAS DO PROMPT
1. No máximo {MAX_CHARS} caracteres no total (instruções + narração, contando espaços e pontuação).
2. Narração feminina em português brasileiro, natural, persuasiva, para vídeo curto.
3. Quebra de objeções: responder às dúvidas que impedem a compra, como qualidade, praticidade, conforto ou
   custo-benefício, conforme o produto, só com informações reais (nome, foto, prints, nota e vendas abaixo).
   Sem citar valores, descontos ou cupons.
4. Curiosidade: despertar vontade de conhecer o produto (começar com uma pergunta ou situação do dia a dia).
5. Urgência e escassez: incentivar a compra com argumentos verdadeiros (ex.: nota alta, muitos vendidos), sem
   inventar promoções, desconto, prazo ou estoque limitado.
6. CTA no final: terminar com uma chamada direta para a pessoa conferir, aproveitar ou comprar o produto.
7. Fidelidade visual absoluta: usar a imagem enviada como referência e preservar cores, formato, proporções, marca,
   detalhes e características; não inventar nem modificar o produto. Na frase "preserve …", cite os detalhes
   concretos que um gerador de vídeo mais costuma mudar neste produto (quantidade de peças/barras, tamanhos,
   estampa/flores, cores de cada parte, formato).
8. Movimentos POV suaves, realistas e coerentes com o uso do produto; sem gestos artificiais nem mudanças bruscas.
9. Nenhuma escrita na tela: proibir legendas, títulos, palavras, preços, logotipos ou texto sobreposto.
10. Mostrar e citar 2 ou 3 benefícios práticos REAIS do produto (ex.: antiaderente, usa menos óleo, fácil de
    limpar, monta sem ferramenta), na cena e na narração, sem promessas exageradas.
11. Simples e direto: poucas cenas, nada contraditório, sem efeitos desnecessários.

A NARRAÇÃO VENDE O BENEFÍCIO, NÃO A FICHA TÉCNICA. Antes de escrever, liste em "beneficios" os 2 ou 3 benefícios
que fazem alguém comprar ESTE produto (o resultado na vida da pessoa), do mais forte para o menos forte. Ex.:
frigideira antiaderente → cozinhar sem óleo (ou quase), nada gruda, comida mais saudável, lava em segundos;
organizador → acaba a bagunça, acha tudo rápido; cadeira → conforto por horas, sem dor nas costas. O benefício
principal (o 1º) tem que estar na narração, dito de forma clara e concreta.
O BENEFÍCIO PRINCIPAL NUNCA É a variedade do kit (vários tamanhos, nº de peças, cores, modelos) nem "praticidade" ou
"organização" genéricas: é o que o produto FAZ por quem usa. Deduza pela foto e pelo nome (ex.: interior
salpicado/granito/preto liso numa panela = revestimento antiaderente → sem óleo, nada gruda, lava fácil). Medidas,
cores e nº de peças ficam nas instruções do vídeo; na narração, no máximo uma menção curta.
Fale com a pessoa sem adjetivo de gênero ("Sabe quando…", "Já pensou…", nunca "Cansado/Cansada").

EXEMPLO DE NARRAÇÃO BOA (jogo de frigideiras antiaderentes):
“Já pensou fritar um ovo sem uma gota de óleo? Nessas frigideiras antiaderentes nada gruda: a comida desliza e fica
mais leve. E a limpeza é num instante, só passar a esponja. Nota 4,8 e mais de 8 mil vendidos. Toque no carrinho e
garanta o seu!”

ESTRUTURA DA NARRAÇÃO: 1) gancho que desperta curiosidade (pergunta ou dor do dia a dia ligada ao benefício
principal); 2) quebra de objeção com o benefício principal (ex.: "sem óleo e nada gruda"); 3) mais 1 benefício
prático; 4) urgência e escassez verdadeiras (nota, vendidos); 5) CTA final direto.

FORMATO (o mesmo que a Juliane usa), em um parágrafo corrido:
"Crie um vídeo POV vertical 9:16, realista e natural, … Use a imagem enviada como referência fiel/obrigatória e preserve
<detalhes concretos: quantidade de peças, tamanhos, cores, estampa, materiais>. Não altere cores, proporções, textura,
quantidade de peças ou detalhes. Mostre <cena de uso real que PROVA o benefício principal (ex.: ovo deslizando na frigideira sem óleo)>,
destacando <benefícios práticos>.
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

Se houver PRINTS anexos (depois da foto principal), use-os como fatos reais. PRINTS DO ANÚNCIO: medidas,
materiais, garantia, certificações, itens do kit. PRINTS DAS AVALIAÇÕES: o que os compradores elogiam (o resultado
no uso, as dúvidas que tinham e foram resolvidas, "chegou certinho", "não gruda mesmo"…); são a melhor fonte para o
benefício principal e para quebrar objeções na narração, com as palavras de quem comprou. Nunca use preço.

ESTILO ENXUTO: nas instruções do vídeo use abreviações claras para economizar caracteres (ex.: "Vídeo POV 9:16",
"ref. fiel", "mov. suaves", "luz natural", "nº de peças", "Sem textos/legendas/preços na tela", "Narração fem.
PT/BR:"). NUNCA abrevie dentro da narração (ela é falada em voz alta).

TAMANHO: instruções do vídeo com até 550 caracteres e narração com até 300 (as duas juntas nunca passam de
{MAX_CHARS}). A narração tem que vir INTEIRA, com as 5 partes, terminando no CTA e fechando as aspas.

CAMPOS
- beneficios: os 2 ou 3 benefícios que fazem comprar o produto, do mais forte ao menos forte, em português.
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
    (r'crie (um )?v[íi]deo (promocional )?vertical 9:16,? (no )?estilo pov', 'Vídeo POV 9:16'),
    (r'crie (um )?v[íi]deo (promocional )?(pov )?vertical 9:16', 'Vídeo POV 9:16'),
    (r'use a imagem enviada como refer[êe]ncia (obrigat[óo]ria|fiel)', 'Use a imagem enviada como ref. fiel'),
    (r'preserve a fidelidade visual absoluta d[oa]', 'preserve'),
    (r'(n[ãa]o adicione|sem) textos?, legendas?, t[íi]tulos?, pre[çc]os?, (logotipos?|logos?|marcas?) ou '
     r'(qualquer )?escrita na tela', 'Sem textos/legendas/preços/logos na tela'),
    (r'(n[ãa]o adicione|sem) textos?, legendas?, t[íi]tulos?, pre[çc]os? ou (qualquer )?escrita na tela',
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
    head = re.sub(r'(^|[.!?]\s+)([a-zà-ú])', lambda m: _capitalize(m, head), head)   # início de frase
    return (head + speech).strip()


ABBREVIATED = re.compile(r'\b(mov|ref|fem|nº|n°|aprox|ex)\.\s+$', re.IGNORECASE)


def _capitalize(m, text: str) -> str:
    # o ponto de "mov." / "ref." / "fem." não termina a frase: "mov. suaves" continua minúsculo
    if ABBREVIATED.search(text[:m.start(2)]):
        return m.group(0)
    return m.group(1) + m.group(2).upper()


def _split(prompt: str):
    """(instruções do vídeo, narração) — a narração começa em "Narração"."""
    i = prompt.find('Narração')
    return (prompt, '') if i < 0 else (prompt[:i].rstrip(), prompt[i:].strip())


STOPWORDS = {'para', 'mais', 'menos', 'muito', 'muita', 'como', 'qualquer', 'fácil', 'facil', 'sempre', 'todo', 'toda'}


def _mentions(benefit: str, speech: str) -> bool:
    """A fala cita o benefício? (alguma palavra forte dele, pelo radical: "gruda" ~ "grudar")."""
    words = [w for w in re.findall(r'[a-zà-ú]{4,}', benefit.lower()) if w not in STOPWORDS]
    low = speech.lower()
    return not words or any(w[:5] in low for w in words)


SPEC_BENEFIT = re.compile(r'tamanh|medida|pe[çc]as|\bcores\b|modelos|variedade|organiza|praticidade', re.IGNORECASE)
SPEC_SPEECH = re.compile(r'tamanh|medida|\bcm\b|cent[íi]metro', re.IGNORECASE)


def problems(prompt: str, benefits: Optional[list] = None) -> list:
    """O que está errado no prompt: tamanho, narração faltando, sem CTA, cortada ou sem o benefício principal."""
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
        if len(SPEC_SPEECH.findall(quote)) > 1:
            found.append('a narração gasta tempo com tamanhos/medidas: fale do benefício de usar o produto')
        if not any(w in quote.lower()[-160:] for w in CTA_WORDS):
            found.append('a narração não termina com um CTA (ex.: "Toque no carrinho e garanta o seu!")')
        if benefits and SPEC_BENEFIT.search(benefits[0]):
            found.append(f'o benefício principal ("{benefits[0]}") é ficha técnica/genérico: troque pelo que o produto '
                         'FAZ por quem usa (ex.: frigideira antiaderente: sem óleo, nada gruda, lava fácil) e '
                         'reescreva a narração em cima dele')
        elif benefits and not _mentions(benefits[0], quote):
            found.append(f'a narração não fala do benefício principal ("{benefits[0]}"): fale dele no lugar de '
                         'medidas/ficha técnica')
    return found


def _sentences(text: str) -> list:
    """Frases das instruções; o ponto de "mov." / "ref." / "fem." não quebra a frase."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for part in parts:
        if out and ABBREVIATED.search(out[-1] + ' '):
            out[-1] += ' ' + part
        else:
            out.append(part)
    return out


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
    sentences = _sentences(instructions)

    def priority(sentence: str) -> int:
        low = sentence.lower()
        if 'imagem enviada' in low or 'não adicione' in low or 'escrita' in low or 'na tela' in low:
            return 0   # fidelidade ao produto e nada escrito na tela: nunca sai
        if low.startswith('mostre'):
            return 1   # a cena de uso: a última a sair
        if low.startswith(('crie', 'vídeo')):
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


LABEL = 'Narração fem. PT/BR: '

NARRATIONS_SCHEMA = {
    'type': 'object',
    'properties': {
        'beneficios': {'type': 'array', 'items': {'type': 'string'}},
        'avaliacoes': {'type': 'string'},
        'opcoes': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['beneficios', 'avaliacoes', 'opcoes'],
    'additionalProperties': False,
}

NARRATIONS_TASK = f"""TAREFA AGORA: só a NARRAÇÃO (a Juliane escolhe uma antes de montar o prompt do vídeo).
Escreva 4 opções de narração diferentes entre si, cada uma com até {NARRATION_MAX} caracteres, seguindo as regras e a
estrutura da narração acima (curiosidade → objeção → benefício → urgência verdadeira → CTA no final). Varie o
gancho: 1) pergunta; 2) dor/situação do dia a dia; 3) "Já pensou…"/curiosidade; 4) prova social (o que dizem as
avaliações, nota e vendidos). Todas falam do benefício principal. Só a fala, sem aspas e sem "Narração:".
CAMPOS: beneficios (2 ou 3, do mais forte ao menos forte); avaliacoes (1 frase com o que os compradores mais elogiam
nas avaliações/prints das avaliações, ou "" se não vieram avaliações); opcoes (as 4 falas)."""


def _clean_speech(text: str) -> str:
    text = re.sub(r'^\s*(narra[çc][ãa]o[^:]*:)\s*', '', text.strip(), flags=re.IGNORECASE)
    return text.strip().strip('“”"').strip()


def narration_problems(speech: str, benefits: Optional[list] = None) -> list:
    """Problemas de uma opção de narração (mesmas checagens do prompt completo)."""
    found = problems(f"Vídeo. {LABEL}“{speech}”", benefits)
    if len(speech) > NARRATION_MAX:
        found.append(f"tem {len(speech)} caracteres (máximo {NARRATION_MAX})")
    return [f for f in found if 'máximo ' + str(MAX_CHARS) not in f]


def _images(product: Dict, prints: Optional[list]) -> list:
    images = [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                           'data': _photo_b64(product['imageUrl'])}}]
    for path in (prints or [])[:6]:
        images.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                                   'data': _file_b64(path)}})
    return images


def _context(product: Dict, notes: str, images: list) -> str:
    text = f"{RULES}\n\n{_facts(product)}"
    if notes:
        text += f"\nOBSERVAÇÕES DA JULIANE: {notes}"
    if len(images) > 1:
        text += (f"\n\n(As {len(images) - 1} imagem(ns) depois da foto principal são PRINTS do anúncio e/ou das "
                 "avaliações.)")
    return text


def narrations(product: Dict, notes: str = '', prints: Optional[list] = None, request: str = '',
               previous: Optional[list] = None, reviews: Optional[list] = None) -> Dict:
    """4 opções de narração (com os benefícios e o resumo das avaliações) para a Juliane escolher."""
    images = _images(product, prints)
    text = _context(product, notes, images)
    if reviews:
        text += ("\n\nAVALIAÇÕES DOS COMPRADORES (texto real, use como os prints das avaliações):\n"
                 + '\n'.join(f"- {r}" for r in reviews))
    text += f"\n\n{NARRATIONS_TASK}"
    if previous:
        text += ("\n\nOPÇÕES ANTERIORES (não repita):\n" + '\n'.join(f"- {o}" for o in previous)
                 + f"\nAJUSTE PEDIDO: {request or 'outras 4 opções, com ganchos diferentes'}")
    data = ask_json([*images, {'type': 'text', 'text': text}], NARRATIONS_SCHEMA, name='narracoes')
    data['opcoes'] = [_clean_speech(o) for o in data['opcoes']][:4]
    issues = {i: narration_problems(o, data['beneficios']) for i, o in enumerate(data['opcoes'])}
    issues = {i: v for i, v in issues.items() if v}
    if issues:   # uma rodada de correção só das opções com problema
        fix = '\n'.join(f"Opção {i + 1}: {data['opcoes'][i]}\nProblemas: {'; '.join(v)}" for i, v in issues.items())
        again = ask_json([*images, {'type': 'text', 'text': text + "\n\nCorrija estas opções (devolva as 4 "
                                    f"opções, as boas iguais):\n{fix}\nTODAS: {data['opcoes']}"}],
                         NARRATIONS_SCHEMA, name='narracoes')
        data = {**again, 'opcoes': [_clean_speech(o) for o in again['opcoes']][:4]}
    return data


def render_narrations(product: Dict, data: Dict, url: str, reviews_read: Optional[int] = None,
                      source: Optional[str] = None) -> str:
    e = html.escape
    lines = [f"🎙 <b>Escolha a narração</b> — {e(product['productName'][:80])}", e(url), '']
    if source == 'arquivo':
        lines.append(f"📝 Usei {reviews_read} avaliação(ões) do arquivo")
    elif reviews_read:
        lines.append(f"📝 Usei {reviews_read} avaliação(ões) que a extensão mandou")
    elif source:
        lines.append("📝 Sem avaliações deste produto: abra-o no Chrome com a extensão (role até as avaliações) e "
                     "toque 🔄 Outras 4")
    if data.get('beneficios'):
        lines.append('💪 ' + e(' · '.join(data['beneficios'])))
    if data.get('avaliacoes'):
        lines.append(f"⭐ Avaliações: {e(data['avaliacoes'])}")
    lines.append('')
    for i, option in enumerate(data['opcoes'], 1):
        lines += [f"<b>{i})</b> {e(option)} <i>({len(option)} carac.)</i>", '']
    lines.append("<i>Toque no número para montar o prompt com ela, ou responda esta mensagem pedindo ajuste "
                 "(ex.: \"mais curtas\", \"fale que não precisa de óleo\"). Para usar uma narração sua, responda "
                 "começando com \"minha:\".</i>")
    return '\n'.join(lines)[:4000]


INSTRUCTIONS_SCHEMA = {
    'type': 'object',
    'properties': {
        'detalhes_fixos': {'type': 'array', 'items': {'type': 'string'}},
        'instrucoes': {'type': 'string'},
        'conferir': {'type': 'string'},
    },
    'required': ['detalhes_fixos', 'instrucoes', 'conferir'],
    'additionalProperties': False,
}


def build_with_narration(product: Dict, narration: str, notes: str = '', prints: Optional[list] = None,
                         benefits: Optional[list] = None) -> Dict:
    """Prompt completo com a narração que a Juliane escolheu (a fala fica exatamente como ela aprovou)."""
    narration = _clean_speech(narration)
    tail = f"{LABEL}“{narration}”"
    budget = MAX_CHARS - len(tail) - 1
    images = _images(product, prints)
    text = (f"{_context(product, notes, images)}\n\nTAREFA AGORA: a narração já foi escolhida e NÃO muda:\n{tail}\n"
            f"Escreva só as INSTRUÇÕES DO VÍDEO (tudo que vem antes da narração, no FORMATO acima), com no máximo "
            f"{budget} caracteres, e com a cena de uso mostrando o que a narração fala"
            + (f" (benefícios: {', '.join(benefits)})" if benefits else '') + ". Termine com a frase de nenhuma "
            "escrita na tela. Não inclua a narração.")
    data = ask_json([*images, {'type': 'text', 'text': text}], INSTRUCTIONS_SCHEMA, name='instrucoes_video')
    instructions = compact(_split(data['instrucoes'])[0].strip())
    if 'tela' not in instructions.lower():
        instructions += ' Sem textos/legendas/preços na tela.'
    prompt = _fit(f"{instructions} {tail}")
    return {'beneficios': benefits or [], 'detalhes_fixos': data['detalhes_fixos'], 'prompt': prompt,
            'conferir': data['conferir'], 'narracao': narration}


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
        issues = problems(data['prompt'].strip(), data.get('beneficios'))
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
    benefits = '\n'.join(f"• {e(b)}" for b in data.get('beneficios') or [])
    return (f"🎬 <b>{e(product['productName'][:90])}</b>\n{e(url)}\n"
            f"Prompt com {len(data['prompt'])}/{MAX_CHARS} caracteres na mensagem abaixo: toque e segure → Copiar.\n\n"
            + (f"💪 <b>Benefícios na narração</b>\n{benefits}\n\n" if benefits else '') +
            f"🔒 <b>Conferir no vídeo gerado</b>\n{fixed}\n🔎 {e(data['conferir'])}\n\n"
            f"<i>Use a foto principal do anúncio como base. Para ajustar, responda o prompt "
            f"(ex.: \"mais curto\", \"gancho com pergunta\").</i>")[:4000]


def prompt_only(data: Dict) -> str:
    """Só o prompt, sem nada junto: copiar a mensagem copia exatamente o prompt."""
    return html.escape(data['prompt'])
