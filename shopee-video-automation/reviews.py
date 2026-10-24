"""
Avaliações dos compradores para a narração dos prompts (🎬 Prompts). O robô NUNCA acessa a Shopee (proteção da
conta): as avaliações chegam pela extensão "AfiliDash Avaliações" do Chrome da Juliane (ela só repassa o que a
página do produto já carregou, sem pedir nada à Shopee) ou pelo JSON/CSV da extensão "Shopee Reviews Grabber".
"""

import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List

logger = logging.getLogger(__name__)

PORT = int(os.getenv('AVALIACOES_PORTA', '8787'))
MAX_STORED = 60
MAX_AGE_DAYS = 60


def _line(review: Dict) -> str:
    text = ' '.join(str(review.get('comentario') or '').split())[:300]
    variation = ' '.join(str(review.get('variacao') or '').split())[:60]
    return f"★{review.get('estrelas', '')} {text}" + (f" ({variation})" if variation else '')


def save(db, item_id: str, new: List[Dict]) -> int:
    """Junta as avaliações novas às já guardadas do produto (sem repetir); devolve o total guardado."""
    key = f"avaliacoes:{item_id}"
    old = json.loads(db.get_meta(key, 'null') or 'null') or {'reviews': []}
    seen = {r['comentario'] for r in old['reviews']}
    merged = old['reviews'] + [r for r in new if r['comentario'] not in seen]
    db.set_meta(key, json.dumps({'quando': time.time(), 'reviews': merged[:MAX_STORED]}, ensure_ascii=False))
    return len(merged[:MAX_STORED])


def stored(db, item_id, limit: int = 30) -> List[str]:
    """Avaliações que a extensão mandou deste produto (como "★5 texto (variação)")."""
    data = json.loads(db.get_meta(f"avaliacoes:{item_id}", 'null') or 'null') if item_id else None
    if not data or time.time() - data.get('quando', 0) > MAX_AGE_DAYS * 86400:
        return []
    return [_line(r) for r in data['reviews'][:limit]]


def _clean(payload) -> tuple:
    item_id, shop_id = str(payload.get('itemId') or ''), str(payload.get('shopId') or '')
    if not item_id.isdigit():
        raise ValueError('itemId inválido')
    reviews = []
    for r in (payload.get('reviews') or [])[:200]:
        text = ' '.join(str((r or {}).get('comentario') or '').split())
        if text:
            reviews.append({'estrelas': str(r.get('estrelas') or '')[:3], 'comentario': text[:1000],
                            'variacao': str(r.get('variacao') or '')[:100]})
    return item_id, shop_id, reviews


def serve(db, key: str, port: int = PORT) -> ThreadingHTTPServer:
    """Recebe as avaliações da extensão: POST com o JSON {itemId, shopId, reviews} e o cabeçalho X-Chave."""
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: Dict):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self._reply(200, {'ok': True, 'servico': 'AfiliDash Avaliações'})

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('X-Chave', ''), key):
                self._reply(403, {'ok': False})
                return
            size = int(self.headers.get('Content-Length') or 0)
            if size <= 0 or size > 1_000_000:
                self._reply(413, {'ok': False})
                return
            try:
                item_id, shop_id, reviews = _clean(json.loads(self.rfile.read(size)))
            except (ValueError, json.JSONDecodeError, AttributeError) as e:
                self._reply(400, {'ok': False, 'erro': str(e)[:100]})
                return
            total = save(db, item_id, reviews) if reviews else len(stored(db, item_id, MAX_STORED))
            logger.info(f"Avaliações recebidas da extensão: produto {shop_id}/{item_id}, {len(reviews)} nova(s), "
                        f"{total} guardada(s)")
            self._reply(200, {'ok': True, 'total': total})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Recebendo avaliações da extensão na porta {port}")
    return server


def extension_zip(url: str, key: str) -> bytes:
    """A extensão pronta para instalar, já com o endereço do VPS e a chave."""
    import io
    import zipfile
    from pathlib import Path
    from urllib.parse import urlsplit
    folder = Path(__file__).parent / 'extensao_avaliacoes'
    parts = urlsplit(url)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.iterdir()):
            text = path.read_text(encoding='utf-8')
            text = (text.replace('__ORIGEM__', f"{parts.scheme}://{parts.netloc}")
                    .replace('__URL__', url).replace('__CHAVE__', key))
            z.writestr(f"afilidash-avaliacoes/{path.name}", text)
    return buf.getvalue()


COMMENT_KEYS = ('comentario', 'comentário', 'comment', 'texto', 'text', 'review', 'avaliacao', 'avaliação')
STAR_KEYS = ('estrelas', 'stars', 'star', 'rating_star', 'rating', 'nota')
VARIATION_KEYS = ('variacao', 'variação', 'variation', 'model', 'modelo')


def _pick(row: Dict, keys) -> str:
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        if low.get(key) not in (None, ''):
            return ' '.join(str(low[key]).split())
    return ''


def _rows(data) -> List[Dict]:
    """A lista de avaliações dentro do JSON (lista solta ou dentro de "reviews"/"avaliacoes"/"ratings"/…)."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for value in data.values():
            rows = _rows(value) if isinstance(value, (list, dict)) else []
            if rows and any(_pick(r, COMMENT_KEYS) for r in rows):
                return rows
    return []


def parse_file(path: str, limit: int = 30) -> List[str]:
    """
    Avaliações do arquivo que a extensão "Shopee Reviews Grabber" baixa (JSON ou CSV: autor, estrelas,
    comentário, data, variação…), no mesmo formato de `fetch`: "★5 texto (variação)". Só as que têm texto.
    """
    import csv
    import io
    import json
    raw = open(path, 'rb').read().decode('utf-8-sig', errors='replace')
    if path.lower().endswith('.json') or raw.lstrip().startswith(('[', '{')):
        rows = _rows(json.loads(raw))
    else:
        sample = raw[:2000]
        delimiter = ';' if sample.count(';') > sample.count(',') else ','
        rows = list(csv.DictReader(io.StringIO(raw), delimiter=delimiter))
    found = []
    for row in rows:
        text = _pick(row, COMMENT_KEYS)
        if not text:
            continue
        stars = _pick(row, STAR_KEYS)
        variation = _pick(row, VARIATION_KEYS)
        found.append(f"★{stars} {text[:300]}" + (f" ({variation[:60]})" if variation else ''))
        if len(found) >= limit:
            break
    return found
