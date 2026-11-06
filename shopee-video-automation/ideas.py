"""
Ideias de produtos para gravar (💡 Ideias e /sugestoes).

🔥 Buscas em alta: os termos mais buscados do dia na Shopee (lista "Buscas em alta" do rodapé, gravada às 07:15 pelo
buscas-alta.js da AfiliDash na tabela garimpo_buscas_alta do Postgres da VPS); para o orgânico, sem piso de comissão.
Nas outras seções o sinal de procura é o total de vendas do anúncio. Busca em nichos que vendem o ano todo (rodízio diário) e nas datas comemorativas dos próximos 90 dias, e aplica as
regras do Garimpo: comissão de pelo menos R$ 9 por venda, nota ≥ 4,7, nunca suplementos.
"""

import html
import logging
import math
import os
import re
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Set, Tuple

from shopee_affiliate import commission_value

logger = logging.getLogger(__name__)

MIN_COMMISSION = 9.0      # R$ por venda (piso do Garimpo)
MIN_RATING = 4.7
MIN_SALES = 100
TARGET = 15               # ideias da lista principal (comissão ≥ R$ 9)
MINIMUM = 15
# 💸 Preço acessível (o que mais vende no Shopee Vídeo): preço baixo, comissão menor, muitas vendas
CHEAP_PRICE = float(os.getenv('IDEIAS_PRECO_ACESSIVEL', '60'))
CHEAP_MIN_COMMISSION = float(os.getenv('IDEIAS_COMISSAO_ACESSIVEL', '3'))
CHEAP_MIN_SALES = 500
CHEAP_TARGET = 10
PER_KEYWORD = 50
SEASON_DAYS = 90

# Nunca: suplementos, vitaminas, colágeno, whey (regra do Garimpo)
BLOCKED = re.compile(r'suplement|vitamin|col[aá]geno|whey|creatina|prote[ií]na|termog[eê]nic|[oô]mega ?3|'
                     r'c[aá]psula|multivitam|bcaa|glutamina|pr[eé]-?treino|emagrec', re.IGNORECASE)

# Nichos que vendem o ano todo. A cada dia entra uma parte deles (rodízio) e uma palavra-chave diferente de
# cada nicho, para a lista não repetir os mesmos tipos de produto.
NICHOS = {
    'Cozinha': ['utensílios de cozinha', 'escorredor de louça', 'tábua de corte', 'mini processador',
                'porta tempero', 'garrafa térmica', 'forma de silicone', 'faqueiro'],
    'Organização': ['organizador gaveta', 'caixa organizadora', 'organizador guarda roupa', 'cabide veludo',
                    'organizador de geladeira', 'sapateira', 'organizador de maquiagem'],
    'Banheiro': ['organizador banheiro', 'tapete banheiro', 'kit banheiro', 'porta escova de dente',
                 'chuveiro filtro', 'cesto roupa suja'],
    'Limpeza': ['mop giratório', 'escova elétrica limpeza', 'rodo mágico', 'aspirador portátil',
                'lavadora de alta pressão', 'pano microfibra'],
    'Decoração': ['luminária de mesa', 'quadro decorativo', 'espelho decorativo', 'vaso decorativo',
                  'tapete sala', 'cortina', 'difusor de aromas'],
    'Quarto e cama': ['jogo de cama', 'travesseiro', 'manta sofá', 'protetor de colchão', 'luminária quarto'],
    'Pet': ['cama pet', 'arranhador gato', 'comedouro automático', 'brinquedo cachorro', 'tapete higiênico',
            'coleira peitoral', 'fonte bebedouro gato'],
    'Bebê e infantil': ['organizador bebê', 'babador silicone', 'brinquedo educativo', 'tapete de atividades',
                        'luminária infantil', 'mochila infantil'],
    'Beleza e cabelo': ['escova secadora', 'chapinha', 'organizador de maquiagem', 'pincel maquiagem',
                        'espelho com led', 'babyliss'],
    'Moda e acessórios': ['bolsa feminina', 'carteira feminina', 'óculos de sol', 'relógio feminino',
                          'kit brincos', 'cinto feminino', 'mochila notebook'],
    'Calçados e roupas': ['tênis feminino', 'chinelo nuvem', 'pijama feminino', 'conjunto feminino',
                          'vestido feminino', 'meia calça'],
    'Tecnologia': ['fone bluetooth', 'carregador turbo', 'suporte celular', 'smartwatch', 'caixa de som bluetooth',
                   'ring light', 'power bank'],
    'Casa inteligente': ['lâmpada inteligente', 'tomada inteligente', 'câmera wifi', 'fita led', 'sensor de presença'],
    'Escritório e estudos': ['organizador de mesa', 'suporte notebook', 'luminária de estudo', 'cadeira escritório',
                             'planner', 'estojo'],
    'Fitness': ['tapete yoga', 'elástico exercício', 'garrafa academia', 'corda de pular', 'halter',
                'faixa elástica'],
    'Carro': ['organizador carro', 'aspirador automotivo', 'suporte celular carro', 'capa banco carro',
              'kit limpeza automotiva'],
    'Jardim e varanda': ['vaso autoirrigável', 'luz solar jardim', 'regador', 'horta vertical',
                         'mangueira expansível'],
    'Ferramentas': ['parafusadeira', 'kit ferramentas', 'trena laser', 'furadeira', 'kit chaves'],
    'Viagem e camping': ['mala de viagem', 'necessaire', 'organizador de mala', 'lanterna recarregável',
                         'cadeira de praia'],
    'Festa e presentes': ['kit presente', 'cesta de presente', 'caneca personalizada', 'decoração festa'],
}
NICHOS_POR_DIA = 12
MAX_PER_THEME = 2          # no máximo 2 ideias do mesmo nicho/data por seção
REPEAT_DAYS = 30           # ideia sugerida (ou produto parecido) não volta antes disso


def niches_of_the_day(today: date) -> List[Tuple[str, str]]:
    """(nicho, palavra-chave) de hoje: rodízio dos nichos e, dentro de cada um, das palavras-chave."""
    names = list(NICHOS)
    n = today.toordinal()
    start = (n * NICHOS_POR_DIA) % len(names)
    chosen = [names[(start + i) % len(names)] for i in range(min(NICHOS_POR_DIA, len(names)))]
    return [(name, NICHOS[name][(n // len(names) + n) % len(NICHOS[name])]) for name in chosen]


def similar_key(name: str) -> str:
    """Tipo de produto (primeiras palavras do nome, sem acento/número): o mesmo produto em outras lojas."""
    import unicodedata
    plain = unicodedata.normalize('NFKD', name.lower())
    plain = ''.join(c for c in plain if not unicodedata.combining(c))
    words = [w for w in re.sub(r'[^a-z ]', ' ', plain).split() if len(w) > 2 and w not in STOP]
    return ' '.join(w.rstrip('s')[:5] for w in words[:3])   # capas/capa, natal/natalina: mesmo tipo


STOP = {'kit', 'com', 'para', 'pcs', 'pecas', 'unidades', 'unid', 'novo', 'nova', 'premium', 'luxo', 'original'}


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _dates(year: int) -> List[Tuple[date, str, List[str]]]:
    easter = _easter(year)
    return [
        (date(year, 1, 20), 'Volta às aulas', ['material escolar', 'mochila escolar', 'lancheira']),
        (easter - timedelta(days=47), 'Carnaval', ['fantasia carnaval', 'bolsa de praia', 'leque carnaval']),
        (easter, 'Páscoa', ['forma de ovo de páscoa', 'cesta de páscoa']),
        (_nth_weekday(year, 5, 6, 2), 'Dia das Mães', ['presente dia das mães', 'kit skincare presente', 'bolsa feminina']),
        (date(year, 6, 12), 'Dia dos Namorados', ['presente namorado', 'presente namorada']),
        (date(year, 6, 24), 'Festa Junina', ['decoração festa junina', 'chapéu de palha']),
        (_nth_weekday(year, 8, 6, 2), 'Dia dos Pais', ['presente dia dos pais', 'kit churrasco', 'carteira masculina']),
        (date(year, 9, 15), 'Dia do Cliente', ['kit presente', 'organizador']),
        (date(year, 10, 12), 'Dia das Crianças', ['brinquedo educativo', 'brinquedo infantil']),
        (date(year, 10, 31), 'Halloween', ['decoração halloween', 'fantasia halloween', 'abóbora halloween']),
        (_last_weekday(year, 11, 4), 'Black Friday', ['eletroportáteis', 'air fryer', 'robô aspirador',
                                                      'cafeteira', 'liquidificador portátil', 'smart tv box']),
        (date(year, 12, 25), 'Natal', ['árvore de natal', 'enfeite árvore de natal', 'pisca pisca cascata',
                                       'presépio', 'guirlanda de natal', 'toalha de mesa natal', 'papai noel decoração',
                                       'caneca natal', 'pijama natal família', 'amigo secreto presente',
                                       'mesa posta natal', 'tapete natal']),
        (date(year, 12, 31), 'Ano Novo', ['decoração ano novo', 'taça de champanhe', 'roupa branca réveillon',
                                          'balde de gelo']),
    ]


def upcoming(today: date) -> List[Tuple[date, str, List[str]]]:
    """Datas comemorativas dos próximos SEASON_DAYS dias, da mais próxima para a mais distante."""
    found = [d for y in (today.year, today.year + 1) for d in _dates(y)
             if today <= d[0] <= today + timedelta(days=SEASON_DAYS)]
    return sorted(found)


def _score(p: Dict) -> float:
    return commission_value(p) * math.log10(10 + int(p.get('sales') or 0))


def collect(client, today: date, skip: Callable[[Dict], bool]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    (ideias de datas, ideias do ano todo, ideias de preço acessível). `skip(produto)`: já postado ou sugerido
    há pouco (o mesmo anúncio ou um parecido de outra loja). Cada ideia tem 'tema' (data ou nicho).
    """
    cache: Dict[str, List[Dict]] = {}

    def search(keyword: str) -> List[Dict]:
        if keyword not in cache:
            cache[keyword] = _search(keyword)
        return cache[keyword]

    def _search(keyword: str) -> List[Dict]:
        try:
            return client.search(keyword, limit=PER_KEYWORD, sort_type=2)   # mais vendidos
        except Exception as e:
            logger.warning(f"Ideias: busca '{keyword}' falhou ({e}); tentando sem ordenação")
            try:
                return client.search(keyword, limit=PER_KEYWORD)
            except Exception as e2:
                logger.warning(f"Ideias: busca '{keyword}' falhou de novo ({e2})")
                return []

    seen_items: Set[str] = set()
    seen_types: Set[str] = set()

    def good(p: Dict, cheap: bool = False) -> bool:
        key = f"{p['shopId']}:{p['itemId']}"
        kind = similar_key(p.get('productName', ''))
        price = float(p.get('priceMin') or 0)
        rules = (price <= CHEAP_PRICE and commission_value(p) >= CHEAP_MIN_COMMISSION
                 and int(p.get('sales') or 0) >= CHEAP_MIN_SALES) if cheap else \
            (commission_value(p) >= MIN_COMMISSION and int(p.get('sales') or 0) >= MIN_SALES)
        return (rules and float(p.get('ratingStar') or 0) >= MIN_RATING
                and not BLOCKED.search(p.get('productName', ''))
                and key not in seen_items and kind not in seen_types and not skip(p))

    def pick(searches: List[Tuple[str, str]], per_keyword: int, cheap: bool = False) -> List[Dict]:
        """Candidatos (até per_keyword por busca, sem tipos repetidos entre eles); nada é reservado ainda."""
        chosen, kinds = [], set()
        for tema, keyword in searches:
            taken = 0
            for p in sorted(search(keyword), key=_score, reverse=True):
                kind = similar_key(p.get('productName', ''))
                if taken < per_keyword and kind not in kinds and good(p, cheap):
                    chosen.append({**p, 'tema': tema})
                    kinds.add(kind)
                    taken += 1
        return chosen

    def diverse(items: List[Dict], limit: int) -> List[Dict]:
        """Os melhores, no máximo MAX_PER_THEME por nicho/data; só os escolhidos ficam reservados."""
        out, per_theme = [], {}
        for p in sorted(items, key=_score, reverse=True):
            kind, key = similar_key(p.get('productName', '')), f"{p['shopId']}:{p['itemId']}"
            if per_theme.get(p['tema'], 0) < MAX_PER_THEME and kind not in seen_types and key not in seen_items:
                out.append(p)
                per_theme[p['tema']] = per_theme.get(p['tema'], 0) + 1
                seen_types.add(kind)
                seen_items.add(key)
            if len(out) >= limit:
                break
        return out

    n = today.toordinal()
    season = []   # 3 palavras-chave por data, em rodízio
    for when, name, keywords in upcoming(today):
        season += [(f"{name} ({when:%d/%m})", keywords[(n * 3 + i) % len(keywords)]) for i in range(min(3, len(keywords)))]
    niches = niches_of_the_day(today)

    seasonal = diverse(pick(season, 2), 8)
    evergreen = diverse(pick(niches, 2), TARGET - len(seasonal))
    # pouca coisa passou: outras palavras-chave dos nichos de hoje e, depois, dos outros nichos
    extra = [(name, kw) for name, _ in niches for kw in NICHOS[name]] + \
            [(name, kw) for name in NICHOS if name not in dict(niches) for kw in NICHOS[name]]
    extra = [e for e in extra if e not in niches]
    while len(seasonal) + len(evergreen) < MINIMUM and extra:
        batch, extra = extra[:6], extra[6:]
        evergreen += diverse(pick(batch, 2), MINIMUM - len(seasonal) - len(evergreen))
    cheap = diverse(pick(season, 1, cheap=True) + pick(niches, 1, cheap=True), CHEAP_TARGET)
    return seasonal, evergreen, cheap


# 🔥 Buscas em alta (orgânico: sem piso de R$ por venda)
TRENDING_URL = os.getenv('BUSCAS_ALTA_URL', 'http://localhost:3000/garimpo_buscas_alta')
TRENDING_MAX = int(os.getenv('IDEIAS_BUSCADOS', '15'))
TRENDING_MIN_SALES = 100
# venda proibida (o termo "Pod Recarregável" apareceu em 26/10)
FORBIDDEN = re.compile(r'\bpods?\b|vape|vaper|cigarr?o eletr|e-?cig|narguil|ess[eê]ncia (de |para )?narg|'
                       r'\bjuul\b|\bignite\b|tabaco|fumo', re.IGNORECASE)
TERM_STOP = {'de', 'da', 'do', 'das', 'dos', 'para', 'pra', 'com', 'e', 'em', 'a', 'o', 'p'}


def trending_terms(today: date) -> Tuple[List[Dict], date]:
    """
    Termos da lista "Buscas em alta" de hoje (ou da data mais recente, se o robô das 07:15 falhou), pelo PostgREST
    local. ([], None) se estiver fora do ar: a seção some e o resto das Ideias sai normal.
    """
    import requests
    session = requests.Session()
    session.trust_env = False          # localhost: sem proxy
    try:
        rows = session.get(TRENDING_URL, params={'data': f'eq.{today.isoformat()}', 'order': 'posicao.asc'},
                           timeout=10).json()
        if not rows:
            latest = session.get(TRENDING_URL, params={'select': 'data', 'order': 'data.desc', 'limit': 1},
                                 timeout=10).json()
            if not latest:
                return [], None
            rows = session.get(TRENDING_URL, params={'data': f"eq.{latest[0]['data']}", 'order': 'posicao.asc'},
                               timeout=10).json()
    except Exception as e:
        logger.warning(f"Buscas em alta indisponíveis ({e}); Ideias sem essa seção")
        return [], None
    if not isinstance(rows, list) or not rows:
        return [], None
    return rows, date.fromisoformat(str(rows[0]['data'])[:10])


def _plain(text: str) -> List[str]:
    import unicodedata
    text = unicodedata.normalize('NFKD', (text or '').lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.findall(r'[a-z0-9]+', text)


def _stem(word: str) -> str:
    """Para comparar com plural opcional: "arvores"/"arvore", "flores"/"flor", "botoes"/"botao" ficam iguais."""
    if len(word) <= 3:
        return word
    for suffix, repl in (('oes', 'ao'), ('aes', 'ao'), ('ais', 'al'), ('eis', 'el')):
        if word.endswith(suffix):
            return word[:-3] + repl
    if word.endswith('s'):
        word = word[:-1]
    return word[:-1] if word.endswith('e') and len(word) > 3 else word


FILLER = {'kit', 'jogo', 'conjunto', 'par', 'combo', 'pcs', 'pecas', 'unidades', 'un', 'und', 'novo', 'nova',
          'lancamento', 'promocao', 'original', 'atacado'}


def name_has_term(name: str, term: str) -> bool:
    """
    O produto É o que a pessoa buscou: o nome começa pelo termo (depois de "Kit 2", "Jogo"…, no máximo uma palavra
    antes, ex.: "Sandália Rasteirinha") e tem todas as palavras dele na ordem, sem acento e com plural opcional.
    "Teclado" não pega "Tablet com Teclado" (o termo vem depois de "com": é acessório de outro produto).
    """
    words = [_stem(w) for w in _plain(term) if w not in TERM_STOP]
    if not words:
        return False
    raw = _plain(name)
    while raw and (raw[0] in FILLER or raw[0].isdigit() or raw[0] in TERM_STOP):
        raw = raw[1:]
    name_words = [_stem(w) for w in raw]
    joined = ''.join(w for w in _plain(term) if w not in TERM_STOP)          # "Mouse Pad" = "Mousepad"
    starts = [k for k, w in enumerate(name_words[:2]) if w == words[0] or raw[k].startswith(joined)]
    if not starts:
        return False
    k = starts[0]
    if any(w in ('com', 'mais', 'e') for w in raw[:k]):
        return False
    if raw[k].startswith(joined):
        return True
    i = 0
    for w in name_words[k:]:
        if i < len(words) and (w == words[i] or (len(words[i]) > 3 and w.startswith(words[i]))):
            i += 1
    return i == len(words)


def singular(term: str) -> str:
    """O termo no singular, para buscar também ("Arvores Natal" -> "arvore natal")."""
    out = []
    for w in _plain(term):
        if len(w) > 3 and w not in TERM_STOP:
            w = w[:-3] + 'ao' if w.endswith(('oes', 'aes')) else \
                w[:-1] if w.endswith('s') and not w.endswith(('is', 'us')) else w
        out.append(w)
    return ' '.join(out)


def trending(client, terms: List[Dict], skip: Callable[[Dict], bool]) -> Tuple[List[Dict], int]:
    """
    1 produto por termo (o de mais vendas), na ordem da lista da Shopee, até TRENDING_MAX: nome com o termo,
    nota ≥ MIN_RATING, ≥ TRENDING_MIN_SALES vendas, com comissão (sem piso). (ideias, termos sem produto bom)
    """
    chosen, missing, kinds, keys = [], 0, set(), set()
    for row in terms:
        if len(chosen) >= TRENDING_MAX:
            break
        term = (row.get('termo') or '').strip()
        if not term or row.get('adulto') or BLOCKED.search(term) or FORBIDDEN.search(term):
            continue
        found = {}
        queries = [term] + ([singular(term)] if singular(term) != ' '.join(_plain(term)) else [])
        for query in queries:
            try:
                for p in client.search(query, limit=PER_KEYWORD, sort_type=2):
                    found[f"{p['shopId']}:{p['itemId']}"] = p
            except Exception as e:
                logger.warning(f"Buscas em alta: busca '{query}' falhou ({e})")
        ok = [p for k, p in found.items()
              if name_has_term(p.get('productName', ''), term)
              and float(p.get('ratingStar') or 0) >= MIN_RATING and int(p.get('sales') or 0) >= TRENDING_MIN_SALES
              and commission_value(p) > 0 and not BLOCKED.search(p.get('productName', ''))
              and not FORBIDDEN.search(p.get('productName', '')) and k not in keys
              and similar_key(p.get('productName', '')) not in kinds and not skip(p)]
        if not ok:
            missing += 1
            continue
        best = max(ok, key=lambda p: int(p.get('sales') or 0))
        keys.add(f"{best['shopId']}:{best['itemId']}")
        kinds.add(similar_key(best.get('productName', '')))
        chosen.append({**best, 'tema': f'busca nº {row.get("posicao")}: "{term}"', 'busca': term})
    return chosen, missing


# Lista do dia pelo que VENDE NO SHOPEE VÍDEO (estudo de 05/11 com o relatório "Canal = vídeo": 93% dos pedidos
# foram de beleza/cabelo e o Natal começou a vender; moda e pet quase não venderam pelo vídeo e ficam como teste):
# 10 mais buscados + 12 beleza/cabelo + 8 Natal (só na temporada; fora dela, vão para beleza) + 5 moda + 3 tapete
# higiênico + 2 pet = 40, o limite diário do app da LiA. Cada nicho: (chave, título, quantos, palavras-chave em rodízio,
# palavra que o nome precisa ter, por tipo de produto?). "por tipo": no máximo 1 de cada tipo; tapete: vários
# anúncios do mesmo tipo, de lojas diferentes.
FOCUS = [
    ('casa', '🏠 Casa e decoração (teste)', int(os.getenv('IDEIAS_CASA', '10')),
     ['organizador', 'quadro decorativo', 'luminária', 'tapete sala', 'cortina', 'vaso decorativo', 'espelho decorativo',
      'almofada decorativa', 'porta retrato', 'prateleira', 'utensílios de cozinha', 'escorredor de louça',
      'kit banheiro', 'cabide', 'difusor de aromas', 'jogo de cama', 'manta sofá', 'cesto organizador'], '', True),
    ('beleza', '💇 Beleza e cabelo', int(os.getenv('IDEIAS_BELEZA', '5')),
     ['escova rotativa', 'escova secadora', 'secador de cabelo', 'prancha alisadora', 'chapinha', 'babyliss',
      'modelador de cachos', 'escova alisadora', 'escova giratória', 'secador profissional', 'difusor de cabelo',
      'kit escovas de cabelo', 'escova modeladora', 'prancha de cabelo'], '', True),
    ('natal', '🎄 Natal', int(os.getenv('IDEIAS_NATAL', '10')),
     ['papai noel decorativo', 'enfeite de natal', 'árvore de natal', 'guirlanda de natal', 'pisca pisca',
      'presépio', 'naninha natal', 'toalha de mesa natal', 'bola de natal', 'decoração natalina',
      'almofada natal', 'luzes de natal', 'boneco de neve decorativo', 'mesa posta natal'], '', True),
    ('moda', '👗 Moda feminina', int(os.getenv('IDEIAS_MODA', '10')),
     ['vestido feminino', 'conjunto feminino', 'blusa feminina', 'calça feminina', 'saia feminina',
      'macaquinho feminino', 'cropped feminino', 'body feminino', 'short feminino', 'pijama feminino',
      'jaqueta feminina', 'legging feminina', 'camisa feminina', 'macacão feminino', 'moda praia feminina',
      'kimono feminino', 'bermuda feminina', 'camisola feminina'], 'feminin', True),
    ('tapete', '🐾 Pet: tapete higiênico', int(os.getenv('IDEIAS_TAPETE', '0')),
     ['tapete higiênico', 'tapete higiênico cachorro', 'tapete higiênico lavável', 'tapete higiênico pet 60x60',
      'tapete higiênico 30 unidades'], 'tapete higien', False),
    ('pet', '🐾 Pet', int(os.getenv('IDEIAS_PET', '5')),
     ['tapete higiênico', 'cama pet', 'arranhador gato', 'comedouro automático', 'brinquedo cachorro', 'coleira peitoral',
      'fonte bebedouro gato', 'roupa pet', 'caixa de areia gato', 'escova pet', 'tapete lambedor',
      'bolsa transporte pet', 'comedouro lento', 'casinha cachorro', 'guia retrátil'], '', True),
]
FOCUS_KEYS = [f[0] for f in FOCUS]


def natal_season(today: date) -> bool:
    """Natal vende de meados de outubro até a véspera (depois disso a seção some e as vagas vão para casa)."""
    return (today.month, today.day) >= (10, 15) and (today.month, today.day) <= (12, 24)


FOCUS_KEYWORDS_PER_DAY = 7
# pet: nada de remédio/antipulgas/vermífugo (não é produto para vídeo de achadinho e tem regra própria de venda)
PET_BLOCKED = re.compile(r'rem[eé]dio|medicament|verm[ií]fug|antipulg|carrapat|antibi[oó]tic|vacina', re.IGNORECASE)


def _keywords_today(keywords: List[str], today: date, n: int) -> List[str]:
    start = (today.toordinal() * n) % len(keywords)
    return [keywords[(start + i) % len(keywords)] for i in range(min(n, len(keywords)))]


def focus(client, today: date, skip: Callable[[Dict], bool], skip_type: Callable[[Dict], bool],
          only: Optional[str] = None) -> List[Tuple[str, str, List[Dict]]]:
    """
    Os nichos fixos da lista do dia: [(chave, título, ideias)]. Nota ≥ MIN_RATING, ≥ MIN_SALES vendas, com
    comissão (sem piso: vídeo orgânico), por comissão × vendas, nunca suplementos. `skip`: o mesmo anúncio já
    postado/sugerido; `skip_type`: o mesmo tipo de produto (não vale para o tapete, que é sempre o mesmo tipo).
    """
    global _seller_field
    out, seen = [], set()
    counts = {f[0]: f[2] for f in FOCUS}
    if not natal_season(today):   # fora da temporada: as vagas do Natal vão para casa e decoração
        counts['casa'] += counts.pop('natal')
    for key, title, _, keywords, must, by_type in FOCUS:
        count = counts.get(key, 0) or (5 if only == key else 0)   # pedido avulso de uma seção desligada: 5
        if (only and key != only) or not count:
            continue
        found: Dict[str, Dict] = {}

        def search(batch: List[str]):
            global _seller_field
            for keyword in batch:
                try:   # com a comissão da loja (quando a API tiver), para dar preferência à comissão extra
                    extra_kw = {'extra_fields': 'sellerCommissionRate'} if _seller_field else {}
                    results = client.search(keyword, limit=PER_KEYWORD, sort_type=2, **extra_kw)
                except Exception as e:
                    if not _seller_field:
                        logger.warning(f"Ideias ({key}): busca '{keyword}' falhou ({e})")
                        continue
                    _seller_field = False
                    try:
                        results = client.search(keyword, limit=PER_KEYWORD, sort_type=2)
                    except Exception as e2:
                        logger.warning(f"Ideias ({key}): busca '{keyword}' falhou ({e2})")
                        continue
                for p in results:
                    extra = ' · comissão extra da loja' if _seller_rate(p) > 0 else ''
                    found.setdefault(f"{p['shopId']}:{p['itemId']}",
                                     {**p, 'tema': f"{title.split(' ', 1)[1]} · {keyword}{extra}"})

        words = _plain(must) if must else []
        chosen, kinds, shops = [], set(), set()

        def pick(check_history: bool):
            ok = []
            for k, p in found.items():
                name = ' '.join(_plain(p.get('productName', '')))
                if (float(p.get('ratingStar') or 0) >= MIN_RATING and int(p.get('sales') or 0) >= MIN_SALES
                        and commission_value(p) > 0 and not BLOCKED.search(p.get('productName', ''))
                        and not FORBIDDEN.search(p.get('productName', ''))
                        and not PET_BLOCKED.search(p.get('productName', ''))
                        and all(w in name for w in words) and k not in seen and not skip(p)
                        and not (by_type and check_history and skip_type(p))):
                    ok.append(p)
            for p in sorted(ok, key=lambda p: _score(p) * (1.5 if _seller_rate(p) > 0 else 1), reverse=True):
                if len(chosen) >= count:
                    return
                kind = similar_key(p.get('productName', ''))
                if (by_type and kind in kinds) or (not by_type and p.get('shopId') in shops):
                    continue
                chosen.append(p)
                kinds.add(kind)
                shops.add(p.get('shopId'))
                seen.add(f"{p['shopId']}:{p['itemId']}")

        today_kw = _keywords_today(keywords, today, FOCUS_KEYWORDS_PER_DAY)
        search(today_kw)
        pick(True)
        if len(chosen) < count:      # faltou: as outras palavras-chave do nicho
            search([k for k in keywords if k not in today_kw])
            pick(True)
        if len(chosen) < count:      # ainda faltou: aceita um tipo já sugerido semanas atrás (nunca o mesmo anúncio)
            pick(False)
        out.append((key, title, chosen))
    return out


# 🌱 Oportunidades (TESTE): a API não diz quantos afiliados divulgam cada produto; estes são sinais de pouca
# concorrência: nota boa, poucas vendas ainda (OPP_MIN_SALES a OPP_MAX_SALES) e, quando a API informa, comissão
# extra da loja (o vendedor está pagando a mais para atrair afiliados).
OPP_COUNT = int(os.getenv('IDEIAS_OPORTUNIDADES', '5'))
OPP_MIN_SALES = 100
OPP_MAX_SALES = 3000
OPP_KEYWORDS = [k for _, _, _, kws, _, _ in FOCUS for k in kws] + [
    'organizador', 'utensílios de cozinha', 'decoração quarto', 'luminária', 'kit banheiro', 'tapete sala']
_seller_field = True   # a busca aceita sellerCommissionRate? (desliga sozinho se a API recusar)


def _seller_rate(p: Dict) -> float:
    try:
        rate = float(p.get('sellerCommissionRate') or 0)
    except (TypeError, ValueError):
        return 0.0
    return rate / 100 if rate > 1 else rate


def opportunities(client, today: date, skip: Callable[[Dict], bool], skip_type: Callable[[Dict], bool],
                  count: int = OPP_COUNT) -> List[Dict]:
    """Até `count` produtos com sinais de pouca concorrência, 1 por tipo, da maior comissão para a menor."""
    global _seller_field
    found: Dict[str, Dict] = {}
    for keyword in _keywords_today(OPP_KEYWORDS, today, 8):
        results = []
        try:
            extra_kw = {'extra_fields': 'sellerCommissionRate'} if _seller_field else {}
            results = client.search(keyword, limit=PER_KEYWORD, sort_type=5, **extra_kw)
        except Exception as e:
            if _seller_field:
                _seller_field = False   # a API não tem o campo: segue sem ele
                logger.info(f"Oportunidades: sem comissão da loja na API ({e})")
                try:
                    results = client.search(keyword, limit=PER_KEYWORD, sort_type=5)
                except Exception as e2:
                    logger.warning(f"Oportunidades: busca '{keyword}' falhou ({e2})")
            else:
                logger.warning(f"Oportunidades: busca '{keyword}' falhou ({e})")
        for p in results:
            found.setdefault(f"{p['shopId']}:{p['itemId']}", {**p, 'kw': keyword})
    ok = []
    for p in found.values():
        name = p.get('productName', '')
        sales = int(p.get('sales') or 0)
        if (float(p.get('ratingStar') or 0) >= MIN_RATING and OPP_MIN_SALES <= sales <= OPP_MAX_SALES
                and commission_value(p) > 0 and not BLOCKED.search(name) and not FORBIDDEN.search(name)
                and not PET_BLOCKED.search(name) and not skip(p) and not skip_type(p)):
            if _seller_field and 'sellerCommissionRate' in p and _seller_rate(p) <= 0:
                continue   # a API informa e a loja não paga extra: fica de fora
            extra = _seller_rate(p)
            why = f"comissão extra da loja {extra * 100:.0f}%" if extra > 0 else "poucas vendas ainda"
            ok.append({**p, 'tema': f"Oportunidade (teste) · {why} · {p['kw']}"})
    chosen, kinds = [], set()
    for p in sorted(ok, key=lambda p: commission_value(p), reverse=True):
        kind = similar_key(p.get('productName', ''))
        if kind in kinds:
            continue
        chosen.append(p)
        kinds.add(kind)
        if len(chosen) >= count:
            break
    return chosen


def render_sections(sections: List[Tuple[str, str, List[Dict]]], today: date, hot_missing: int = 0,
                    hot_day: Optional[date] = None, hot_wanted: int = 0) -> List[str]:
    """A lista do dia por seção (mesma numeração do CSV/links), em mensagens abaixo do limite do Telegram."""
    e = html.escape

    def line(i: int, p: Dict) -> str:
        url = f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"
        return (f"<b>{i}. {e(p['productName'][:90])}</b>\n"
                f"   {_brl(float(p.get('priceMin') or 0))} · comissão <b>{_brl(commission_value(p))}</b> · "
                f"{_milhar(int(p.get('sales') or 0))} vendas · nota {p.get('ratingStar')}" +
                f"\n   {'🔎' if p.get('busca') else '🏷️'} {e(p['tema'])} · {e(p.get('shopName', '')[:30])}\n   🔗 {url}")

    total = sum(len(items) for _, _, items in sections)
    blocks = [f"💡 <b>{total} ideias para gravar</b> · {today:%d/%m}\n"
              f"Nota ≥ {MIN_RATING}, {MIN_SALES}+ vendas, nunca suplementos. Grave (ou crie no app da LiA) e mande em "
              f"📥 Envios com o link."]
    i = 1
    for key, title, items in sections:
        if key == 'alta':
            when = 'hoje' if hot_day in (None, today) else f"(lista de {hot_day:%d/%m})"
            title = f"🔥 Mais buscados na Shopee {when}"
        blocks.append(f"<b>{title}</b> ({len(items)})")
        if not items:
            blocks.append("<i>Nenhum produto passou nas regras hoje.</i>")
        for p in items:
            blocks.append(line(i, p))
            i += 1
        if key == 'alta' and hot_wanted and len(items) < hot_wanted:
            blocks.append(f"<i>Só {len(items)} dos termos em alta tinham produto bom"
                          + (f" ({hot_missing} sem produto)" if hot_missing else '') + ".</i>")
    blocks.append("<i>Pedir de novo: /sugestoes (tudo) · /sugestoes alta · /sugestoes casa · /sugestoes beleza · /sugestoes natal · "
                  "/sugestoes moda · /sugestoes pet · /sugestoes tapete · /sugestoes oportunidades</i>")
    messages, current = [], ''
    for block in blocks:
        if len(current) + len(block) + 2 > 3800:
            messages.append(current)
            current = ''
        current += ('\n\n' if current else '') + block
    if current:
        messages.append(current)
    return messages


def section_rows(sections: List[Tuple[str, str, List[Dict]]]) -> List[Dict]:
    """As ideias na numeração da lista, para o CSV/links da LiA."""
    rows = []
    for key, title, items in sections:
        label = title.split(' ', 1)[1] if ' ' in title else title
        for p in items:
            rows.append({**row_for(p, label, len(rows) + 1), 'grupo': key})
    return rows


def _brl(v: float) -> str:
    return f"R$ {v:.2f}".replace('.', ',')


def _milhar(n: int) -> str:
    return f"{n:,}".replace(',', '.')


def render(seasonal: List[Dict], evergreen: List[Dict], cheap: List[Dict], today: date,
           hot: Optional[List[Dict]] = None, hot_missing: int = 0, hot_day: Optional[date] = None) -> List[str]:
    """Mensagens (cada uma abaixo do limite do Telegram) com a lista numerada (🔥 Buscas em alta primeiro)."""
    hot = hot or []
    e = html.escape

    def line(i: int, p: Dict) -> str:
        url = f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"
        return (f"<b>{i}. {e(p['productName'][:90])}</b>\n"
                f"   {_brl(float(p.get('priceMin') or 0))} · comissão <b>{_brl(commission_value(p))}</b> · "
                f"{_milhar(int(p.get('sales') or 0))} vendas · nota {p.get('ratingStar')}" +
                f"\n   {'🔎' if p.get('busca') else '🏷️'} {e(p['tema'])} · {e(p.get('shopName', '')[:30])}\n   🔗 {url}")

    main_total = len(seasonal) + len(evergreen)
    blocks = [f"💡 <b>{main_total + len(cheap) + len(hot)} ideias para gravar</b> · {today:%d/%m}\n"
              f"Nota ≥ {MIN_RATING}. Grave e mande em 📥 Envios com o link."]
    i = 1
    if hot:
        when = 'hoje na Shopee' if hot_day in (None, today) else f"na Shopee (lista de {hot_day:%d/%m})"
        blocks.append(f"🔥 <b>Buscas em alta {when}</b> (orgânico: sem piso de comissão)")
        for p in hot:
            blocks.append(line(i, p))
            i += 1
        if hot_missing:
            blocks.append(f"<i>{hot_missing} termo(s) em alta sem produto bom hoje.</i>")
    if seasonal:
        blocks.append(f"📅 <b>Datas que estão chegando</b> (comissão ≥ {_brl(MIN_COMMISSION)}, por comissão × vendas)")
        for p in seasonal:
            blocks.append(line(i, p))
            i += 1
    if evergreen:
        blocks.append(f"🏠 <b>Vendem o ano todo</b> (comissão ≥ {_brl(MIN_COMMISSION)})")
        for p in evergreen:
            blocks.append(line(i, p))
            i += 1
    if cheap:
        blocks.append(f"💸 <b>Preço acessível</b> (até {_brl(CHEAP_PRICE)}, comissão ≥ {_brl(CHEAP_MIN_COMMISSION)}, "
                      f"{CHEAP_MIN_SALES}+ vendas: o que mais gira no Shopee Vídeo)")
        for p in cheap:
            blocks.append(line(i, p))
            i += 1
    if main_total < MINIMUM:
        blocks.append(f"⚠️ Só {main_total} produto(s) com comissão ≥ {_brl(MIN_COMMISSION)} passaram nas regras hoje.")

    messages, current = [], ''
    for block in blocks:
        if len(current) + len(block) + 2 > 3800:
            messages.append(current)
            current = ''
        current += ('\n\n' if current else '') + block
    if current:
        messages.append(current)
    return messages


def export_rows(seasonal: List[Dict], evergreen: List[Dict], cheap: List[Dict],
                hot: Optional[List[Dict]] = None) -> List[Dict]:
    """As ideias do dia na mesma numeração da lista, para o CSV (o link de afiliado entra depois)."""
    rows = []
    for section, items in (('Buscas em alta', hot or []), ('Datas chegando', seasonal),
                           ('Vende o ano todo', evergreen), ('Preço acessível', cheap)):
        for p in items:
            rows.append(row_for(p, section, len(rows) + 1))
    return rows


def row_for(p: Dict, section: str, n: int) -> Dict:
    return {'n': n, 'secao': section, 'produto': p['productName'][:150],
            'loja': p.get('shopName', ''), 'preco': f"{float(p.get('priceMin') or 0):.2f}".replace('.', ','),
            'comissao': f"{commission_value(p):.2f}".replace('.', ','), 'vendas': int(p.get('sales') or 0),
            'nota': p.get('ratingStar') or '', 'tema': p.get('tema', ''),
            'link_produto': f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"}


def still_good(p: Dict) -> bool:
    """Ideia de outro dia ainda vale: anúncio ativo, não é suplemento e a comissão não caiu abaixo do piso."""
    return bool(p) and not BLOCKED.search(p.get('productName', '')) and commission_value(p) >= CHEAP_MIN_COMMISSION


LIA_BATCH = 20   # o app da LiA aceita até 20 produtos por lote


def export_csv(rows: List[Dict]) -> bytes:
    """CSV para a "Planilha CSV" do app da LiA: uma coluna "link", um link por linha, na ordem da lista."""
    return ('link\n' + '\n'.join(r['link'] for r in rows) + '\n').encode('utf-8')


# Lotes da LiA (até 20 cada) juntando seções inteiras: 15 mais buscados + 5 beleza · 10 casa + 10 Natal · o restante
# (moda + pet + oportunidades). Seções que não estão aqui vão para lotes no fim. LIA_LOTES no .env muda isso.
LIA_GROUPS = [g.split('+') for g in
              (os.getenv('LIA_LOTES') or 'alta+beleza,casa+natal,moda+pet+tapete+oportunidades').split(',') if g]


def batches(rows: List[Dict]) -> List[List[Dict]]:
    """Os lotes para o app da LiA: pelas seções de LIA_GROUPS (sem cortar seção), cada um com no máximo 20."""
    if not any(r.get('grupo') for r in rows):   # links avulsos (/linksideias 40): de 20 em 20, na ordem
        return [rows[i:i + LIA_BATCH] for i in range(0, len(rows), LIA_BATCH)]
    out, used = [], set()
    for group in LIA_GROUPS:
        part = [r for r in rows if r.get('grupo') in group]
        used |= {id(r) for r in part}
        out += [part[i:i + LIA_BATCH] for i in range(0, len(part), LIA_BATCH)]
    rest = [r for r in rows if id(r) not in used]
    out += [rest[i:i + LIA_BATCH] for i in range(0, len(rest), LIA_BATCH)]
    return [b for b in out if b]


def batch_title(batch: List[Dict]) -> str:
    names = list(dict.fromkeys(r['secao'].split(' (')[0] for r in batch))
    return ' + '.join(names)


def _ranges(numbers: List[int]) -> str:
    """[1..15, 26..30] -> "1–15 e 26–30" (a numeração da lista do dia)."""
    parts, start, prev = [], None, None
    for n in numbers + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            parts.append(f"{start}–{prev}" if prev != start else str(start))
            start = prev = n
    return ', '.join(parts[:-1]) + (' e ' if len(parts) > 1 else '') + parts[-1] if parts else ''


def export_texts(rows: List[Dict], today: date) -> List[str]:
    """Os links um por linha (como o app da LiA pede), um lote por mensagem para copiar."""
    lots = batches(rows)
    texts = []
    for k, batch in enumerate(lots, 1):
        part = f"Lote {k}/{len(lots)} · " if len(lots) > 1 else ''
        texts.append(f"🔗 <b>{part}{html.escape(batch_title(batch))}</b> ({len(batch)} links: ideias "
                     f"{_ranges([r['n'] for r in batch])} de {today:%d/%m}), um por linha "
                     f"(toque para copiar e cole em \"Colar links de produtos\" no app da LiA)\n\n"
                     f"<code>{html.escape(chr(10).join(r['link'] for r in batch))}</code>")
    return texts


STOP_NAME = {'de', 'da', 'do', 'das', 'dos', 'com', 'para', 'e', 'em', 'kit', 'a', 'o', 'para'}


def short_name(name: str) -> str:
    """2 palavras do nome do produto para o sub_id ("Frigideira Antiaderente…" -> "FrigideiraAntiaderente")."""
    words = [w for w in re.findall(r'[A-Za-zÀ-ú0-9]+', name) if w.lower() not in STOP_NAME]
    import unicodedata
    text = ''.join(w.capitalize() for w in words[:2])
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
