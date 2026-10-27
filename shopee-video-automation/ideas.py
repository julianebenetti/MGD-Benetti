"""
Ideias de produtos para gravar (💡 Ideias e /sugestoes).

A API de afiliados não informa "mais buscados do dia"; o sinal de procura é o total de vendas do anúncio.
Busca em nichos que vendem o ano todo (rodízio diário) e nas datas comemorativas dos próximos 90 dias, e aplica as
regras do Garimpo: comissão de pelo menos R$ 9 por venda, nota ≥ 4,7, nunca suplementos.
"""

import html
import logging
import math
import os
import re
from datetime import date, timedelta
from typing import Callable, Dict, List, Set, Tuple

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


def _brl(v: float) -> str:
    return f"R$ {v:.2f}".replace('.', ',')


def _milhar(n: int) -> str:
    return f"{n:,}".replace(',', '.')


def render(seasonal: List[Dict], evergreen: List[Dict], cheap: List[Dict], today: date) -> List[str]:
    """Mensagens (cada uma abaixo do limite do Telegram) com a lista numerada."""
    e = html.escape

    def line(i: int, p: Dict) -> str:
        url = f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"
        return (f"<b>{i}. {e(p['productName'][:90])}</b>\n"
                f"   {_brl(float(p.get('priceMin') or 0))} · comissão <b>{_brl(commission_value(p))}</b> · "
                f"{_milhar(int(p.get('sales') or 0))} vendas · nota {p.get('ratingStar')}" +
                f"\n   🏷️ {e(p['tema'])} · {e(p.get('shopName', '')[:30])}\n   🔗 {url}")

    main_total = len(seasonal) + len(evergreen)
    blocks = [f"💡 <b>{main_total + len(cheap)} ideias para gravar</b> · {today:%d/%m}\n"
              f"Nota ≥ {MIN_RATING}, ordenadas por comissão × vendas. Grave e mande em 📥 Envios com o link."]
    i = 1
    if seasonal:
        blocks.append(f"📅 <b>Datas que estão chegando</b> (comissão ≥ {_brl(MIN_COMMISSION)})")
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


def export_rows(seasonal: List[Dict], evergreen: List[Dict], cheap: List[Dict]) -> List[Dict]:
    """As ideias do dia na mesma numeração da lista, para o CSV (o link de afiliado entra depois)."""
    rows = []
    for section, items in (('Datas chegando', seasonal), ('Vende o ano todo', evergreen), ('Preço acessível', cheap)):
        for p in items:
            rows.append({'n': len(rows) + 1, 'secao': section, 'produto': p['productName'][:150],
                         'loja': p.get('shopName', ''), 'preco': f"{float(p.get('priceMin') or 0):.2f}".replace('.', ','),
                         'comissao': f"{commission_value(p):.2f}".replace('.', ','), 'vendas': int(p.get('sales') or 0),
                         'nota': p.get('ratingStar') or '', 'tema': p.get('tema', ''),
                         'link_produto': f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"})
    return rows


def export_csv(rows: List[Dict]) -> bytes:
    """CSV separado por ";" (abre direto no Excel em português), com o link de afiliado de cada ideia."""
    import csv
    import io
    cols = ['n', 'link', 'produto', 'secao', 'tema', 'loja', 'preco', 'comissao', 'vendas', 'nota', 'sub_id',
            'link_produto']
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, delimiter=';', extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode('utf-8-sig')


def export_text(rows: List[Dict], today: date) -> str:
    """Os links um após o outro, separados por ";" (para colar no app da LiA)."""
    links = ';'.join(r['link'] for r in rows)
    return (f"🔗 <b>Links das {len(rows)} ideias de {today:%d/%m}</b>, separados por ; (toque para copiar)\n\n"
            f"<code>{html.escape(links)}</code>")


STOP_NAME = {'de', 'da', 'do', 'das', 'dos', 'com', 'para', 'e', 'em', 'kit', 'a', 'o', 'para'}


def short_name(name: str) -> str:
    """2 palavras do nome do produto para o sub_id ("Frigideira Antiaderente…" -> "FrigideiraAntiaderente")."""
    words = [w for w in re.findall(r'[A-Za-zÀ-ú0-9]+', name) if w.lower() not in STOP_NAME]
    import unicodedata
    text = ''.join(w.capitalize() for w in words[:2])
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
