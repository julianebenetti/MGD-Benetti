"""
Vendas reais (relatório de conversões da API de afiliados), separadas pelo sub_id de cada vídeo.

O sub_id do link volta no campo utmContent de cada conversão ("SV-14Out26-KitCapas--": os 5 sub_ids
do link separados por "-"; posts antigos: "12Out26SVKitCapas----"); a comissão de cada item vem em
itemTotalCommission.
"""

import html
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

FIELDS = ('purchaseTime utmContent orders { orderId orderStatus items { itemId itemName shopName qty '
          'actualAmount itemTotalCommission displayItemStatus } }')
PAGE = 500
MAX_PAGES = 20
_lock = threading.Lock()
_last_call = 0.0


def _money(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(order_status: str) -> str:
    s = (order_status or '').upper()
    return 'cancelado' if s == 'CANCELLED' else 'concluido' if s == 'COMPLETED' else 'pendente'


def sub_id_of(utm_content: str) -> str:
    return '-'.join(p for p in (utm_content or '').split('-') if p)


def fetch(client, start: datetime, end: datetime) -> List[Dict]:
    """
    Itens vendidos com compra entre `start` e `end`: um dict por item, com sub_id, pedido, status e comissão.
    A Shopee só aceita uma consulta nova (sem scrollId) 30 s depois da anterior; as páginas seguintes
    precisam vir em até 30 s, com o scrollId da anterior.
    """
    global _last_call
    with _lock:
        wait = 31 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        items, scroll = [], None
        for _ in range(MAX_PAGES):
            args = f"purchaseTimeStart:{int(start.timestamp())},purchaseTimeEnd:{int(end.timestamp())},limit:{PAGE}"
            if scroll:
                args += f",scrollId:{_gql(scroll)}"
            data = client._graphql(
                f"{{conversionReport({args}){{nodes{{{FIELDS}}} pageInfo{{hasNextPage scrollId}}}}}}")
            report = data['conversionReport']
            for node in report.get('nodes') or []:
                sub_id = sub_id_of(node.get('utmContent'))
                for order in node.get('orders') or []:
                    for item in order.get('items') or []:
                        items.append({
                            'time': node.get('purchaseTime'),
                            'sub_id': sub_id,
                            'order_id': order.get('orderId'),
                            'status': _status(order.get('orderStatus')),
                            'item': item.get('itemName') or '',
                            'shop': item.get('shopName') or '',
                            'qty': int(item.get('qty') or 1),
                            'commission': _money(item.get('itemTotalCommission')),
                        })
            info = report.get('pageInfo') or {}
            scroll = info.get('scrollId')
            if not info.get('hasNextPage') or not scroll:
                break
        _last_call = time.time()
    logger.info(f"Conversões {start:%d/%m %H:%M}–{end:%d/%m %H:%M}: {len(items)} item(ns)")
    return items


def _gql(value: str) -> str:
    from shopee_affiliate import _gql_str
    return _gql_str(value)


def brl(value: float) -> str:
    return f"R$ {value:.2f}".replace('.', ',')


def summary_line(items: List[Dict]) -> str:
    """Uma linha: pedidos e comissão (sem os cancelados), para o relatório do dia."""
    valid = [i for i in items if i['status'] != 'cancelado']
    orders = {i['order_id'] for i in valid}
    total = sum(i['commission'] for i in valid)
    pending = sum(i['commission'] for i in valid if i['status'] == 'pendente')
    cancelled = len({i['order_id'] for i in items if i['status'] == 'cancelado'})
    return (f"{len(orders)} pedido(s) · comissão <b>{brl(total)}</b> (⏳ pendente {brl(pending)})"
            + (f" · ❌ {cancelled} cancelado(s)" if cancelled else ''))


def report(items: List[Dict], posts_by_sub: Dict[str, str], title: str, top: int = 15) -> str:
    """Resumo das vendas por vídeo (sub_id do robô) e o que veio de outros links."""
    e = html.escape
    lines = [f"💵 <b>{title}</b>", "(pela data da compra; a Shopee pode levar algumas horas para mostrar)", "",
             f"Total: {summary_line(items)}"]
    valid = [i for i in items if i['status'] != 'cancelado']
    if not valid:
        lines.append("\nNenhuma venda nesse período.")
        return '\n'.join(lines)

    # vídeos feitos no app da LiA com os links das ideias (sub_id LIA-<data>-<produto>) também contam como do robô
    posts_by_sub = {**posts_by_sub, **{i['sub_id']: f"🤖 LiA app: {i['sub_id'].split('-')[-1]}" for i in valid
                                       if i['sub_id'].startswith('LIA-')}}
    groups = defaultdict(list)
    for i in valid:
        groups[i['sub_id'] if i['sub_id'] in posts_by_sub else ''].append(i)
    ours = [i for sub, g in groups.items() if sub for i in g]
    lines.append(f"🎬 Dos vídeos do robô: {len({i['order_id'] for i in ours})} pedido(s) · "
                 f"{brl(sum(i['commission'] for i in ours))}")

    ranked = sorted(((sub, g) for sub, g in groups.items() if sub),
                    key=lambda sg: sum(i['commission'] for i in sg[1]), reverse=True)
    if ranked:
        lines += ["", "<b>Por vídeo</b>"]
        for sub, g in ranked[:top]:
            lines.append(f"• {e(posts_by_sub[sub][:40])}: {len({i['order_id'] for i in g})} pedido(s) · "
                         f"<b>{brl(sum(i['commission'] for i in g))}</b> <code>{e(sub)}</code>")
        if len(ranked) > top:
            lines.append(f"… e mais {len(ranked) - top} vídeo(s)")
    if groups.get(''):
        other = groups['']
        lines.append(f"\n🔗 Outros links (fora do robô): {len({i['order_id'] for i in other})} pedido(s) · "
                     f"{brl(sum(i['commission'] for i in other))}")
    return '\n'.join(lines)
