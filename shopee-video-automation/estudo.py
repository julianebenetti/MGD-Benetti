"""
Levantamento periódico do Shopee Vídeo e o histórico da conta.

A cada ESTUDO_DIAS (14) o robô lê as vendas do canal vídeo (relatório de conversões da API, campo Canal = vídeo),
resume o que vendeu, quando a pessoa compra e quanto cancela, compara com o levantamento anterior e guarda o resumo
no histórico. O histórico também guarda os marcos da conta (punições, mudanças de estratégia), escritos com /nota.
"""

import html
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from conversions import brl

HISTORY_KEY = 'historico_sv'
MAX_HISTORY = 300

# O começo da história, até a criação do histórico (06/11/2026): vem do que foi vivido e decidido até aqui.
SEED = [
    ('2026-09-07', 'marco', 'Primeira venda pelo Shopee Vídeo.'),
    ('2026-10-10', 'marco', 'Pico de vendas: 19 pedidos no dia, quase todos da Escova Rotativa Elétrica 2 em 1 '
                            '(73% de toda a comissão do vídeo até 04/11).'),
    ('2026-10-12', 'punicao', '"Produto irrelevante" (vídeo da loja pedrita.bambam.store). Em seguida: estrela '
                              'ponteira (16/10), pisca-pisca (17/10), toalha de Natal (20/10), arara e sapateira '
                              '(22/10). Causas: até 5 links por vídeo e vídeo de IA diferente do anúncio.'),
    ('2026-10-23', 'decisao', '7 pontos de penalidade e banimento até 25/10. O robô passou a validar "idêntico ao '
                              'anúncio" (detalhe por detalhe) e a mandar só 1 link para a LiA.'),
    ('2026-10-28', 'punicao', '"Produto irrelevante": kit com 10 baldes de gelo e o vídeo mostrava 1. 8 pontos, '
                              'banida até 31/10. O robô passou a exigir a quantidade do kit no vídeo.'),
    ('2026-10-31', 'decisao', 'Agenda em lotes de 5, 30 vídeos por dia (manhã, tarde e noite). Postagens seguem '
                              'também na outra conta do Shopee Vídeo.'),
    ('2026-11-05', 'estudo', 'Relatório Canal = vídeo (07/09–04/11): 236 pedidos, 156 válidos, 80 cancelados (34%), '
                             'R$ 311,53 de comissão, R$ 2,00 por pedido. Beleza/cabelo = 93% dos pedidos (escova '
                             'rotativa); Natal começando; moda e pet quase não venderam pelo vídeo. Compras na hora '
                             'do vídeo, picos 13–15h, 18h e 20–21h. Vendas caíram a quase zero depois de 19/10.'),
    ('2026-11-06', 'decisao', 'Os cancelamentos da escova eram porque o produto vendido não era o mesmo do vídeo. '
                              'Ideias do dia passam a seguir o que vende no vídeo: 10 mais buscados, 12 beleza/'
                              'cabelo, 8 Natal, moda e pet como teste. Lotes às 9, 11, 13, 17, 19 e 20h. Estratégia: '
                              'fixar o vídeo que mais vende, fazer mais versões dos vencedores, testar oportunidades.'),
]


def history(db) -> List[Dict]:
    data = json.loads(db.get_meta(HISTORY_KEY, 'null') or 'null')
    if data is None:
        data = [{'dia': d, 'tipo': t, 'texto': x} for d, t, x in SEED]
        db.set_meta(HISTORY_KEY, json.dumps(data, ensure_ascii=False))
    return data


def add(db, kind: str, text: str, day: Optional[str] = None):
    data = history(db)
    data.append({'dia': day or datetime.now().date().isoformat(), 'tipo': kind, 'texto': text[:1500]})
    data.sort(key=lambda h: h['dia'])
    db.set_meta(HISTORY_KEY, json.dumps(data[-MAX_HISTORY:], ensure_ascii=False))


ICONS = {'marco': '⭐', 'punicao': '⛔', 'decisao': '🧭', 'estudo': '📈', 'nota': '📝'}


def history_text(db, last: int = 25) -> str:
    data = history(db)
    lines = ["📚 <b>Histórico do Shopee Vídeo</b> (os mais recentes por último)",
             "<i>Acrescente um marco: /nota texto (ex.: /nota levei punição no vídeo da toalha)</i>", ""]
    for h in data[-last:]:
        d = datetime.fromisoformat(h['dia'])
        lines.append(f"{ICONS.get(h['tipo'], '•')} <b>{d:%d/%m/%y}</b> {html.escape(h['texto'])}")
    if len(data) > last:
        lines.insert(3, f"<i>… {len(data) - last} registro(s) mais antigos</i>")
    return '\n'.join(lines)[:4000]


def summary(items: List[Dict]) -> Dict:
    """Números do período a partir das conversões do canal vídeo (cancelados à parte)."""
    valid = [i for i in items if i['status'] != 'cancelado']
    orders = {i['order_id'] for i in valid}
    cancelled = {i['order_id'] for i in items if i['status'] == 'cancelado'} - orders
    commission = sum(i['commission'] for i in valid)
    by_product = defaultdict(lambda: [set(), 0.0])
    for i in valid:
        by_product[i['item']][0].add(i['order_id'])
        by_product[i['item']][1] += i['commission']
    top = sorted(((n, len(o), c) for n, (o, c) in by_product.items()), key=lambda t: t[2], reverse=True)
    hours = Counter(datetime.fromtimestamp(int(i['time'])).hour for i in valid if i.get('time'))
    weekdays = Counter(datetime.fromtimestamp(int(i['time'])).weekday() for i in valid if i.get('time'))
    total = len(orders) + len(cancelled)
    return {
        'orders': len(orders), 'cancelled': len(cancelled), 'commission': round(commission, 2),
        'per_order': round(commission / len(orders), 2) if orders else 0.0,
        'cancel_rate': round(100 * len(cancelled) / total) if total else 0,
        'top': top[:8], 'top_share': round(100 * top[0][2] / commission) if top and commission else 0,
        'hours': dict(hours), 'weekdays': dict(weekdays),
    }


DIAS = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']


def _bands(hours: Dict[int, int]) -> str:
    bands = {'manhã': range(6, 12), 'tarde': range(12, 18), 'noite': range(18, 24), 'madrugada': range(0, 6)}
    total = sum(hours.values()) or 1
    return ' · '.join(f"{name} {round(100 * sum(hours.get(h, 0) for h in r) / total)}%" for name, r in bands.items())


def report_text(s: Dict, days: int, previous: Optional[Dict]) -> str:
    e = html.escape
    lines = [f"📈 <b>Levantamento do Shopee Vídeo</b> · últimos {days} dias",
             "(só vendas do canal vídeo, pela data da compra)", "",
             f"🛒 {s['orders']} pedido(s) válidos · comissão <b>{brl(s['commission'])}</b> · {brl(s['per_order'])} por "
             f"pedido · ❌ {s['cancelled']} cancelado(s) ({s['cancel_rate']}%)"]
    if previous:
        def delta(now, before):
            if not before:
                return ''
            pct = round(100 * (now - before) / before)
            return f" ({'+' if pct >= 0 else ''}{pct}% vs. levantamento anterior)"
        lines.append(f"📊 Pedidos{delta(s['orders'], previous.get('orders'))} · comissão"
                     f"{delta(s['commission'], previous.get('commission'))}")
    if s['top']:
        lines += ["", "<b>O que vendeu</b>"]
        for name, orders, commission in s['top'][:6]:
            lines.append(f"• {e(name[:55])}: {orders} pedido(s) · {brl(commission)}")
    if s['hours']:
        best = [h for h, _ in sorted(s['hours'].items(), key=lambda kv: kv[1], reverse=True)[:3]]
        lines += ["", f"⏰ Compras por período: {_bands(s['hours'])}",
                  f"   Horários mais fortes: {', '.join(f'{h}h' for h in sorted(best))}"]
    if s['weekdays']:
        day = max(s['weekdays'].items(), key=lambda kv: kv[1])[0]
        lines.append(f"📅 Melhor dia: {DIAS[day]}")
    tips = []
    if s['orders'] == 0:
        tips.append("Nenhuma venda pelo vídeo: revise se os vídeos estão sendo publicados e se há punição ativa.")
    if s['cancel_rate'] >= 20:
        tips.append(f"Cancelamento alto ({s['cancel_rate']}%): confira se o produto do link é exatamente o do vídeo.")
    if s['top_share'] >= 60:
        tips.append(f"Um produto fez {s['top_share']}% da comissão: faça mais versões dele (/vencedores) e procure "
                    "parecidos.")
    if tips:
        lines += ["", "<b>Atenção</b>"] + [f"• {t}" for t in tips]
    lines += ["", "<i>Para completar o levantamento, mande aqui os prints da análise do app do Shopee Vídeo "
                  "(visualizações por horário, público/seguidores, vídeos mais vistos). O histórico: /historico</i>"]
    return '\n'.join(lines)[:4000]


def history_line(s: Dict, days: int) -> str:
    top = s['top'][0][0][:40] if s['top'] else '—'
    return (f"Levantamento de {days} dias: {s['orders']} pedidos, {brl(s['commission'])} de comissão, "
            f"{s['cancel_rate']}% cancelados; mais vendido: {top} ({s['top_share']}% da comissão).")
