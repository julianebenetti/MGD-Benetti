"""
Sub_id do link de afiliado: Data + SV (Shopee Video) + Produto, ex: 11Out26SVSapateiraBanco.
Mesmo padrão do Central Post; repetição ganha V2, V3...
"""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Optional

REGISTRY = Path(__file__).parent / 'sub_ids_usados.json'
MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
SIGLA = 'SV'
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


def novo_sub_id(nome_curto: str, hoje: Optional[date] = None) -> str:
    hoje = hoje or date.today()
    base = f"{hoje.day:02d}{MESES[hoje.month - 1]}{hoje.year % 100:02d}{SIGLA}{_limpar(nome_curto)}"
    usados = _usados()
    sub_id, versao = base, 2
    while sub_id in usados:
        sub_id = f"{base}V{versao}"
        versao += 1
    usados.add(sub_id)
    REGISTRY.write_text(json.dumps(sorted(usados), indent=0))
    return sub_id
