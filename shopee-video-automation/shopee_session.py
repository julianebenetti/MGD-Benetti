"""
Sessão logada da Shopee para o navegador do robô (sem login a Shopee mostra "Login Necessário").
Os cookies vêm exportados do navegador da Juliane (extensão Cookie-Editor, formato JSON,
ou arquivo cookies.txt) e ficam em shopee_cookies.json.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / 'shopee_cookies.json'
LOGIN_COOKIES = ('SPC_EC', 'SPC_ST', 'SPC_U')
SAME_SITE = {'no_restriction': 'None', 'none': 'None', 'lax': 'Lax', 'strict': 'Strict'}


class CookieError(ValueError):
    pass


def _from_json(raw: str) -> List[Dict]:
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get('cookies', [])
    cookies = []
    for c in data:
        cookie = {'name': c['name'], 'value': c['value'], 'domain': c['domain'],
                  'path': c.get('path') or '/', 'secure': bool(c.get('secure')),
                  'httpOnly': bool(c.get('httpOnly'))}
        expires = c.get('expirationDate') or c.get('expires')
        if expires and float(expires) > 0:
            cookie['expires'] = float(expires)
        same_site = SAME_SITE.get(str(c.get('sameSite', '')).lower())
        if same_site and (same_site != 'None' or cookie['secure']):
            cookie['sameSite'] = same_site
        cookies.append(cookie)
    return cookies


def _from_netscape(raw: str) -> List[Dict]:
    cookies = []
    for line in raw.splitlines():
        if line.startswith('#HttpOnly_'):
            line, http_only = line[len('#HttpOnly_'):], True
        else:
            http_only = False
        parts = line.split('\t')
        if line.startswith('#') or len(parts) != 7:
            continue
        domain, _, path, secure, expires, name, value = parts
        cookie = {'name': name, 'value': value, 'domain': domain, 'path': path,
                  'secure': secure.upper() == 'TRUE', 'httpOnly': http_only}
        if expires.isdigit() and int(expires) > 0:
            cookie['expires'] = float(expires)
        cookies.append(cookie)
    return cookies


def parse_cookies(raw: str) -> List[Dict]:
    raw = raw.strip()
    try:
        cookies = _from_json(raw) if raw.startswith(('[', '{')) else _from_netscape(raw)
    except (ValueError, KeyError, TypeError) as e:
        raise CookieError(f"Arquivo de cookies em formato desconhecido ({e}).")
    cookies = [c for c in cookies if 'shopee' in c['domain']]
    if not any(c['name'].startswith('SPC_') for c in cookies):
        raise CookieError("Não achei os cookies de login da Shopee (SPC_...). Exporte estando logada em shopee.com.br.")
    return cookies


def save_cookies(raw: str) -> Tuple[int, str]:
    """Valida e salva. Devolve (quantidade, data de validade do login)."""
    cookies = parse_cookies(raw)
    COOKIES_FILE.write_text(json.dumps(cookies))
    COOKIES_FILE.chmod(0o600)
    # validade do login = cookie de sessão principal (os outros SPC_ são curtos e se renovam sozinhos)
    main = [c.get('expires') for c in cookies if c['name'] in LOGIN_COOKIES and c.get('expires')]
    others = [c.get('expires') for c in cookies if c['name'].startswith('SPC_') and c.get('expires')]
    when = min(main) if main else (max(others) if others else None)
    validade = datetime.fromtimestamp(when).strftime('%d/%m/%Y') if when else 'sem data'
    return len(cookies), validade


def apply_session(context):
    """Coloca a sessão logada no navegador do Playwright (se houver cookies salvos)."""
    if COOKIES_FILE.exists():
        try:
            context.add_cookies(json.loads(COOKIES_FILE.read_text()))
        except Exception as e:
            logger.warning(f"Cookies da Shopee inválidos: {e}")


def is_blocked(url: str) -> bool:
    return '/verify/' in url or '/buyer/login' in url
