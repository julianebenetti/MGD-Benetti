"""
Ideias de produtos para gravar (💡 Ideias e /sugestoes).

A API de afiliados não informa "mais buscados do dia"; o sinal de procura é o total de vendas do anúncio.
Busca em categorias que vendem o ano todo e nas datas comemorativas dos próximos 90 dias, e aplica as
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

EVERGREEN = [
    'organizador cozinha', 'pote hermético', 'escorredor de louça', 'utensílios de cozinha',
    'organizador banheiro', 'organizador guarda roupa', 'cabideiro', 'sapateira',
    'jogo de panelas', 'air fryer acessórios', 'mop limpeza', 'aspirador de pó',
    'luminária led', 'tapete sala', 'jogo de cama', 'cortina blackout',
    'kit manta e almofadas', 'decoração sala', 'mesa dobrável', 'lixeira automática',
]


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
        (date(year, 10, 31), 'Halloween', ['decoração halloween', 'fantasia halloween']),
        (_last_weekday(year, 11, 4), 'Black Friday', ['eletroportáteis', 'air fryer', 'fone bluetooth']),
        (date(year, 12, 25), 'Natal', ['árvore de natal', 'decoração de natal', 'kit almofadas natal',
                                       'enfeite árvore de natal', 'toalha de mesa natal', 'presente de natal']),
        (date(year, 12, 31), 'Ano Novo', ['decoração ano novo', 'taça de champanhe']),
    ]


def upcoming(today: date) -> List[Tuple[date, str, List[str]]]:
    """Datas comemorativas dos próximos SEASON_DAYS dias, da mais próxima para a mais distante."""
    found = [d for y in (today.year, today.year + 1) for d in _dates(y)
             if today <= d[0] <= today + timedelta(days=SEASON_DAYS)]
    return sorted(found)


def _score(p: Dict) -> float:
    return commission_value(p) * math.log10(10 + int(p.get('sales') or 0))


def _similar_key(name: str) -> str:
    return ' '.join(re.sub(r'[^a-z0-9 ]', '', name.lower()).split()[:4])


def collect(client, today: date, skip: Callable[[str], bool]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    (ideias de datas, ideias do ano todo, ideias de preço acessível). `skip(product_key)`: produtos já
    postados ou sugeridos há pouco. Cada ideia tem 'tema' (data ou categoria).
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
    seen_names: Set[str] = set()

    def good(p: Dict, cheap: bool = False) -> bool:
        key = f"{p['shopId']}:{p['itemId']}"
        name = _similar_key(p.get('productName', ''))
        price = float(p.get('priceMin') or 0)
        rules = (price <= CHEAP_PRICE and commission_value(p) >= CHEAP_MIN_COMMISSION
                 and int(p.get('sales') or 0) >= CHEAP_MIN_SALES) if cheap else \
            (commission_value(p) >= MIN_COMMISSION and int(p.get('sales') or 0) >= MIN_SALES)
        ok = (rules and float(p.get('ratingStar') or 0) >= MIN_RATING and not BLOCKED.search(p.get('productName', ''))
              and key not in seen_items and name not in seen_names and not skip(key))
        if ok:
            seen_items.add(key)
            seen_names.add(name)
        return ok

    def pick(keywords: List[str], tema: str, per_keyword: int, cheap: bool = False) -> List[Dict]:
        chosen = []
        for keyword in keywords:
            found = sorted(search(keyword), key=_score, reverse=True)
            chosen += [{**p, 'tema': tema} for p in [p for p in found if good(p, cheap)][:per_keyword]]
        return chosen

    seasonal = []
    for when, name, keywords in upcoming(today):
        seasonal += pick(keywords, f"{name} ({when:%d/%m})", 2)
    evergreen = pick(EVERGREEN, 'o ano todo', 1)
    if len(seasonal) + len(evergreen) < MINIMUM:   # pouca coisa passou nos filtros: mais uma por categoria
        evergreen += pick(EVERGREEN, 'o ano todo', 2)
    seasonal.sort(key=_score, reverse=True)
    evergreen.sort(key=_score, reverse=True)
    seasonal, evergreen = seasonal[:10], evergreen[:TARGET - len(seasonal[:10])]

    cheap = []   # mesmas buscas (sem chamadas novas à API), regras de preço acessível
    for when, name, keywords in upcoming(today):
        cheap += pick(keywords, f"{name} ({when:%d/%m})", 1, cheap=True)
    cheap += pick(EVERGREEN, 'o ano todo', 1, cheap=True)
    cheap.sort(key=_score, reverse=True)
    return seasonal, evergreen, cheap[:CHEAP_TARGET]


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
