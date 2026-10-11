"""
Agenda: N posts por dia dentro de uma janela, em horários quebrados,
nunca o mesmo produto duas vezes no mesmo dia.
"""

import os
import random
from datetime import datetime, timedelta, time
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv('AGENDA_TIMEZONE', 'America/Sao_Paulo'))
POSTS_PER_DAY = int(os.getenv('AGENDA_POSTS_POR_DIA', '10'))
START_HOUR = int(os.getenv('AGENDA_INICIO', '9'))
END_HOUR = int(os.getenv('AGENDA_FIM', '22'))
MIN_LEAD = timedelta(minutes=5)
MAX_DAYS_AHEAD = 60


def now() -> datetime:
    return datetime.now(TZ)


def _segment(day, index: int) -> tuple:
    start = datetime.combine(day, time(START_HOUR), TZ)
    length = (END_HOUR - START_HOUR) * 60 / POSTS_PER_DAY
    return start + timedelta(minutes=index * length), length


def _broken_time(seg_start: datetime, seg_minutes: float, rng: random.Random) -> datetime:
    """Horário dentro do segmento, fugindo de minutos redondos (ex: 17:34, não 17:30)."""
    while True:
        t = seg_start + timedelta(minutes=rng.randint(3, max(4, int(seg_minutes) - 3)))
        if t.minute % 5:
            return t.replace(second=0, microsecond=0)


def next_slot(product_key: str, scheduled: Iterable[dict], current: Optional[datetime] = None,
              rng: Optional[random.Random] = None) -> datetime:
    """
    `scheduled`: posts já agendados, cada um com 'scheduled_at' (ISO) e 'product_key'.
    Devolve o primeiro horário livre respeitando as regras.
    """
    current = current or now()
    rng = rng or random.Random()
    by_day = {}
    for post in scheduled:
        when = datetime.fromisoformat(post['scheduled_at']).astimezone(TZ)
        by_day.setdefault(when.date(), []).append((when, post['product_key']))

    for offset in range(MAX_DAYS_AHEAD):
        day = (current + timedelta(days=offset)).date()
        items = by_day.get(day, [])
        if any(key == product_key for _, key in items) or len(items) >= POSTS_PER_DAY:
            continue
        taken = set()
        for when, _ in items:
            for i in range(POSTS_PER_DAY):
                seg_start, length = _segment(day, i)
                if seg_start <= when < seg_start + timedelta(minutes=length):
                    taken.add(i)
        for i in range(POSTS_PER_DAY):
            if i in taken:
                continue
            seg_start, length = _segment(day, i)
            slot = _broken_time(seg_start, length, rng)
            if slot >= current + MIN_LEAD:
                return slot
    raise RuntimeError('Agenda cheia nos próximos 60 dias')
