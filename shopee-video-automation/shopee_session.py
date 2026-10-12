"""
Sessão logada da Shopee para o navegador do robô (sem login a Shopee mostra "Login Necessário").
Os cookies vêm exportados do navegador da Juliane (extensão Cookie-Editor, formato JSON,
ou arquivo cookies.txt) e ficam em shopee_cookies.json.
"""

import atexit
import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / 'shopee_cookies.json'
# Desligado por padrão: a Shopee bloqueia o navegador do VPS como robô ("verify/traffic") e as
# tentativas ficam associadas à conta logada. Com 'nao', o robô nunca abre páginas da Shopee.
PAGES_ENABLED = os.getenv('SHOPEE_ACESSAR_PAGINAS', 'nao').lower() in ('sim', 'true', '1')
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


# ---------- navegador ----------
# A Shopee detecta o Chromium "headless" e o marca de automação ("verify/traffic").
# Por padrão o robô abre um Chromium normal numa tela virtual (Xvfb) e esconde o navigator.webdriver.
BROWSER_ARGS = ['--disable-blink-features=AutomationControlled']
HIDE_AUTOMATION_JS = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
_xvfb = None


def _ensure_display() -> bool:
    global _xvfb
    if os.environ.get('DISPLAY'):
        return True
    if not shutil.which('Xvfb'):
        return False
    if _xvfb is None:
        _xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1920x1080x24', '-nolisten', 'tcp'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(_xvfb.terminate)
        time.sleep(1)  # se outra instância já usa :99, a tela dela serve igual
    os.environ['DISPLAY'] = ':99'
    return True


def launch(playwright, profile_dir, **kwargs):
    """Navegador persistente, logado na Shopee e com menos cara de automação."""
    mode = os.getenv('SHOPEE_BROWSER_MODE', 'auto').lower()  # auto | headless | visivel
    headless = mode == 'headless' or (mode == 'auto' and not _ensure_display())
    # o processo do Playwright já existia antes da tela virtual: a tela vai explícita para o navegador
    env = {**os.environ} if headless else {**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':99')}
    context = playwright.chromium.launch_persistent_context(
        str(profile_dir), headless=headless, locale='pt-BR', args=BROWSER_ARGS, env=env,
        ignore_default_args=['--enable-automation'], **kwargs)
    context.add_init_script(HIDE_AUTOMATION_JS)
    apply_session(context)
    return context
