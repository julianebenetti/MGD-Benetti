"""
Sub_id do link de afiliado: SV-<data da publicação>-<produto>, ex: SV-14Out26-SapateiraBanco.

Vai para a Shopee como 3 sub_ids separados (SV, 14Out26, SapateiraBanco): o relatório junta os sub_ids
com "-", então aparece exatamente "SV-14Out26-SapateiraBanco" (e nenhum sub_id leva "-", que a Shopee
usa como separador). Repetição ganha V2, V3... no nome do produto.
"""

import json
import re
import threading
import unicodedata
from datetime import date
from pathlib import Path
from typing import List, Optional

REGISTRY = Path(__file__).parent / 'sub_ids_usados.json'
MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
SIGLA = 'SV'
_lock = threading.Lock()  # dois vídeos preparados ao mesmo tempo não pegam o mesmo sub_id
MAX_PRODUTO = 20


def _limpar(nome: str) -> str:
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    return re.sub(r'[^A-Za-z0-9]', '', nome)[:MAX_PRODUTO] or 'Produto'


def _usados() -> set:
    try:
        return set(json.loads(REGISTRY.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def prefixo(dia: date) -> str:
    """Começo do sub_id de um dia: "SV-14Out26-"."""
    return f"{SIGLA}-{dia.day:02d}{MESES[dia.month - 1]}{dia.year % 100:02d}-"


def novo_sub_id(nome_curto: str, dia: Optional[date] = None, reservar: bool = True) -> str:
    """
    `dia`: data da publicação (agendamento). `reservar=False`: sub_id provisório (enquanto o post está em
    Editados), que não ocupa o nome: o definitivo é gerado ao agendar.
    """
    base = prefixo(dia or date.today()) + _limpar(nome_curto)
    if not reservar:
        return base
    with _lock:
        usados = _usados()
        sub_id, versao = base, 2
        while sub_id in usados:
            sub_id = f"{base}V{versao}"
            versao += 1
        usados.add(sub_id)
        REGISTRY.write_text(json.dumps(sorted(usados), indent=0))
    return sub_id


def partes(sub_id: str) -> List[str]:
    """Os sub_ids que vão no link (até 5): "SV-14Out26-Kit" -> ["SV", "14Out26", "Kit"]."""
    return [p for p in (sub_id or '').split('-') if p][:5]


def nome_do_sub_id(sub_id: str) -> str:
    """Nome do produto dentro de um sub_id novo (SV-data-Nome) ou antigo (14Out26SVNome)."""
    if sub_id.startswith(f"{SIGLA}-"):
        return re.sub(r'V\d+$', '', sub_id.split('-')[-1])
    m = re.match(rf'^\d{{2}}[A-Za-z]{{3}}\d{{2}}{SIGLA}(.+?)(V\d+)?$', sub_id)
    return m.group(1) if m else sub_id
