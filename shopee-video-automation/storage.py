"""
Estado do robô em SQLite: posts, headlines já usadas e posição da leitura do Telegram.
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).parent / 'estado.db'
JSON_FIELDS = ('products', 'links', 'metadata', 'editados_msgs', 'agenda_msgs')

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,              -- editado | agendado | avisado | postado | descartado
    created_at TEXT NOT NULL,
    source_msg_id INTEGER,
    product_key TEXT,                  -- shopId:itemId do produto principal
    product_name TEXT,
    products TEXT,                     -- JSON: produtos (principal + extras)
    links TEXT,                        -- JSON: links de afiliado, na mesma ordem
    sub_id TEXT,
    metadata TEXT,                     -- JSON: headline, descrição, hashtags, SEO
    video_path TEXT,
    cover_path TEXT,
    editados_msgs TEXT DEFAULT '[]',
    agenda_msgs TEXT DEFAULT '[]',
    scheduled_at TEXT
);
CREATE TABLE IF NOT EXISTS headlines (product_key TEXT, headline TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class Storage:
    def __init__(self, path: Path = DB_PATH):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def _row(self, row) -> Optional[Dict]:
        if row is None:
            return None
        post = dict(row)
        for f in JSON_FIELDS:
            post[f] = json.loads(post[f]) if post[f] else ([] if f.endswith('msgs') else None)
        return post

    def create_post(self, **fields) -> int:
        fields.setdefault('status', 'editado')
        fields['created_at'] = datetime.now().isoformat(timespec='seconds')
        for f in JSON_FIELDS:
            if f in fields:
                fields[f] = json.dumps(fields[f], ensure_ascii=False)
        cols = ', '.join(fields)
        with self.lock:
            cur = self.conn.execute(
                f"INSERT INTO posts ({cols}) VALUES ({', '.join('?' * len(fields))})", list(fields.values()))
            self.conn.commit()
            return cur.lastrowid

    def update_post(self, post_id: int, **fields):
        for f in JSON_FIELDS:
            if f in fields:
                fields[f] = json.dumps(fields[f], ensure_ascii=False)
        sets = ', '.join(f"{k} = ?" for k in fields)
        with self.lock:
            self.conn.execute(f"UPDATE posts SET {sets} WHERE id = ?", [*fields.values(), post_id])
            self.conn.commit()

    def get_post(self, post_id: int) -> Optional[Dict]:
        with self.lock:
            return self._row(self.conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone())

    def post_by_editados_msg(self, message_id: int) -> Optional[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM posts WHERE status = 'editado'").fetchall()
        for row in rows:
            post = self._row(row)
            if message_id in post['editados_msgs']:
                return post
        return None

    def scheduled(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM posts WHERE status IN ('agendado', 'avisado') ORDER BY scheduled_at").fetchall()
        return [self._row(r) for r in rows]

    def add_headline(self, product_key: str, headline: str):
        with self.lock:
            self.conn.execute("INSERT INTO headlines VALUES (?, ?)", (product_key, headline))
            self.conn.commit()

    def headlines_for(self, product_key: str) -> List[str]:
        with self.lock:
            rows = self.conn.execute("SELECT headline FROM headlines WHERE product_key = ?", (product_key,))
            return [r[0] for r in rows.fetchall()]

    def get_meta(self, key: str, default: str = '') -> str:
        with self.lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
            self.conn.commit()
