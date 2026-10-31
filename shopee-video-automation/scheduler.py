"""
Agenda em lotes: 30 vídeos por dia, 10 de manhã, 10 à tarde e 10 à noite, em lotes de 5 vídeos no mesmo horário
(a LiA publica um atrás do outro). Cada lote tem um horário quebrado (ex.: 9:13, nunca 9:00), o mesmo para os 5
vídeos dele; nunca o mesmo produto duas vezes no mesmo dia.
"""

import os
import random
from datetime import datetime, timedelta, time
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv('AGENDA_TIMEZONE', 'America/Sao_Paulo'))
# Horas dos lotes (2 de manhã, 2 à tarde, 2 à noite); o minuto é sorteado por dia, sempre quebrado
BATCH_HOURS = [int(h) for h in (os.getenv('AGENDA_LOTES') or '9,11,14,16,19,21').split(',') if h.strip()]
BATCH_SIZE = int(os.getenv('AGENDA_POR_LOTE', '5'))
POSTS_PER_DAY = int(os.getenv('AGENDA_POSTS_POR_DIA', str(len(BATCH_HOURS) * BATCH_SIZE)))
START_HOUR = min(BATCH_HOURS)
END_HOUR = max(BATCH_HOURS) + 1
PERIODS = {'manhã': range(0, 12), 'tarde': range(12, 18), 'noite': range(18, 24)}
MIN_LEAD = timedelta(minutes=5)
MAX_DAYS_AHEAD = 60


def now() -> datetime:
    return datetime.now(TZ)


def period(t: datetime) -> str:
    return next((name for name, hours in PERIODS.items() if t.astimezone(TZ).hour in hours), '')


def batches(day) -> List[datetime]:
    """Os horários dos lotes do dia: minuto quebrado (3 a 27, nunca múltiplo de 5), sorteado pela data."""
    rng = random.Random(day.toordinal())
    out = []
    for hour in BATCH_HOURS:
        minute = rng.choice([m for m in range(3, 28) if m % 5])
        out.append(datetime.combine(day, time(hour, minute), TZ))
    return out


def next_slot(product_key: str, scheduled: Iterable[dict], current: Optional[datetime] = None,
              rng: Optional[random.Random] = None, last_posted: Optional[datetime] = None,
              posted: Iterable[dict] = ()) -> datetime:
    """
    O próximo lote com vaga: ainda não passou, tem menos de BATCH_SIZE vídeos, o dia tem menos de POSTS_PER_DAY e
    ainda não tem esse produto. `scheduled`: posts agendados ('scheduled_at', 'product_key'); `posted`: já postados
    ('posted_at', 'product_key'), que contam no limite do dia e na regra do mesmo produto.
    (`rng` e `last_posted` ficam por compatibilidade: os horários dos lotes já vêm da data.)
    """
    current = current or now()
    items = [(datetime.fromisoformat(p['scheduled_at']).astimezone(TZ), p['product_key'], True)
             for p in scheduled if p.get('scheduled_at')]
    items += [(datetime.fromisoformat(p['posted_at']).astimezone(TZ), p['product_key'], False)
              for p in posted if p.get('posted_at')]
    for offset in range(MAX_DAYS_AHEAD):
        day = (current + timedelta(days=offset)).date()
        day_items = [(w, k, s) for w, k, s in items if w.date() == day]
        if len(day_items) >= POSTS_PER_DAY or any(k == product_key for _, k, _ in day_items):
            continue
        for slot in batches(day):
            if slot < current + MIN_LEAD:
                continue
            in_batch = sum(1 for w, _, s in day_items if s and w.replace(second=0, microsecond=0) == slot)
            if in_batch < BATCH_SIZE:
                return slot
    raise RuntimeError('Agenda cheia nos próximos 60 dias')
