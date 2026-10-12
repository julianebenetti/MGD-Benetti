"""
Agenda em sequência: cada post entra de 1 a 2 horas depois do anterior, dentro da janela do dia,
em horários quebrados, no máximo N por dia e nunca o mesmo produto duas vezes no mesmo dia.
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


GAP_MIN = int(os.getenv('AGENDA_INTERVALO_MIN', '60'))    # minutos entre um post e o próximo
GAP_MAX = int(os.getenv('AGENDA_INTERVALO_MAX', '120'))


def _broken(t: datetime) -> datetime:
    """Foge de minutos redondos (ex: 17:34, não 17:30)."""
    t = t.replace(second=0, microsecond=0)
    while t.minute % 5 == 0:
        t += timedelta(minutes=1)
    return t


def _day_start(day, rng: random.Random) -> datetime:
    return _broken(datetime.combine(day, time(START_HOUR), TZ) + timedelta(minutes=rng.randint(2, 25)))


def next_slot(product_key: str, scheduled: Iterable[dict], current: Optional[datetime] = None,
              rng: Optional[random.Random] = None, last_posted: Optional[datetime] = None) -> datetime:
    """
    Sequência por dia: o post entra de GAP_MIN a GAP_MAX minutos depois do último daquele dia (ou do último
    postado, ou de agora), dentro da janela START_HOUR–END_HOUR. Dia cheio (POSTS_PER_DAY), sem espaço até
    END_HOUR ou que já tem o mesmo produto: vai para o dia seguinte, começando logo depois de START_HOUR.
    `scheduled`: posts já agendados, cada um com 'scheduled_at' (ISO) e 'product_key'.
    """
    current = current or now()
    rng = rng or random.Random()
    items = [(datetime.fromisoformat(p['scheduled_at']).astimezone(TZ), p['product_key']) for p in scheduled]
    for offset in range(MAX_DAYS_AHEAD):
        day = (current + timedelta(days=offset)).date()
        day_items = [(w, k) for w, k in items if w.date() == day]
        if len(day_items) >= POSTS_PER_DAY or any(k == product_key for _, k in day_items):
            continue
        refs = [w for w, _ in day_items]
        if offset == 0:
            refs += [current] + ([last_posted.astimezone(TZ)] if last_posted else [])
        if refs and max(refs) >= datetime.combine(day, time(START_HOUR), TZ):
            slot = _broken(max(refs) + timedelta(minutes=rng.randint(GAP_MIN, GAP_MAX)))
        else:
            slot = _day_start(day, rng)
        if slot.time() < time(START_HOUR):
            slot = _day_start(day, rng)
        if slot.date() == day and slot.time() <= time(END_HOUR):
            return slot
    raise RuntimeError('Agenda cheia nos próximos 60 dias')
