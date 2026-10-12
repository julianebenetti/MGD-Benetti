"""
Estado do robô em SQLite: posts, headlines já usadas e posição da leitura do Telegram.
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).parent / 'estado.db'
JSON_FIELDS = ('products', 'links', 'metadata', 'editados_msgs', 'agenda_msgs', 'melhores')

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,              -- editado | agendando | agendado | enviando | avisado | postado | descartado
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
    sticker_path TEXT,
    cover_approved INTEGER DEFAULT 0,
    caption_approved INTEGER DEFAULT 0,
    final_video_path TEXT,             -- vídeo com a capa na abertura (gerado ao aprovar)
    variacoes TEXT DEFAULT 'pendente', -- pendente (aguarda o print) | ok | sem
    melhores TEXT,                     -- JSON: lojas com comissão maior que a do link enviado
    troca TEXT DEFAULT 'sem',          -- pendente (pergunta se troca pela melhor) | trocado | mantido | sem
    posted_at TEXT,                    -- quando foi para Postados
    posted_via TEXT,                   -- lia | manual
    discarded_at TEXT,
    editados_msgs TEXT DEFAULT '[]',
    agenda_msgs TEXT DEFAULT '[]',
    scheduled_at TEXT
);
CREATE TABLE IF NOT EXISTS headlines (product_key TEXT, headline TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS video_jobs (    -- vídeos na fila: sobrevivem a reinícios do robô
    msg_id INTEGER PRIMARY KEY, file_id TEXT, link TEXT, text TEXT, trust INTEGER, at REAL
);
CREATE TABLE IF NOT EXISTS failures (      -- vídeos que falharam, para refazer com um link novo
    msg_id INTEGER PRIMARY KEY, err_msg_id INTEGER, file_id TEXT, text TEXT, at REAL, link TEXT
);
"""


class Storage:
    def __init__(self, path: Path = DB_PATH):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self._add_missing_columns()

    def _add_missing_columns(self):
        """Bancos criados por versões antigas ganham as colunas novas (CREATE IF NOT EXISTS não altera)."""
        existing = {r[1] for r in self.conn.execute("PRAGMA table_info(posts)")}
        for name, decl in (('sticker_path', 'TEXT'), ('cover_approved', 'INTEGER DEFAULT 0'),
                           ('caption_approved', 'INTEGER DEFAULT 0'),
                           ('final_video_path', 'TEXT'), ('variacoes', "TEXT DEFAULT 'pendente'"),
                           ('melhores', 'TEXT'), ('troca', "TEXT DEFAULT 'sem'"), ('posted_at', 'TEXT'),
                           ('posted_via', 'TEXT'), ('discarded_at', 'TEXT')):
            if name not in existing:
                self.conn.execute(f"ALTER TABLE posts ADD COLUMN {name} {decl}")
        if 'link' not in {r[1] for r in self.conn.execute("PRAGMA table_info(failures)")}:
            self.conn.execute("ALTER TABLE failures ADD COLUMN link TEXT")
        self.conn.commit()

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
                "SELECT * FROM posts WHERE status IN ('agendado', 'avisado', 'enviando') ORDER BY scheduled_at").fetchall()
        return [self._row(r) for r in rows]

    def with_status(self, *statuses: str) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                f"SELECT * FROM posts WHERE status IN ({', '.join('?' * len(statuses))}) ORDER BY created_at",
                statuses).fetchall()
        return [self._row(r) for r in rows]

    def recent_failures(self, max_age: float) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM failures WHERE at > ? ORDER BY at",
                                     (time.time() - max_age,)).fetchall()
        return [dict(r) for r in rows]

    def add_headline(self, product_key: str, headline: str):
        with self.lock:
            self.conn.execute("INSERT INTO headlines VALUES (?, ?)", (product_key, headline))
            self.conn.commit()

    def headlines_for(self, product_key: str) -> List[str]:
        with self.lock:
            rows = self.conn.execute("SELECT headline FROM headlines WHERE product_key = ?", (product_key,))
            return [r[0] for r in rows.fetchall()]

    def add_failure(self, msg_id: int, err_msg_id: int, file_id: str, text: str, link: str = ''):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO failures (msg_id, err_msg_id, file_id, text, at, link) "
                              "VALUES (?, ?, ?, ?, ?, ?)", (msg_id, err_msg_id, file_id, text, time.time(), link))
            self.conn.commit()

    def find_failure(self, replied_id: Optional[int], max_age: float) -> Optional[Dict]:
        """A falha respondida (pelo vídeo ou pela mensagem de erro); senão, a mais recente dentro do prazo."""
        with self.lock:
            row = None
            if replied_id:
                row = self.conn.execute("SELECT * FROM failures WHERE msg_id = ? OR err_msg_id = ?",
                                        (replied_id, replied_id)).fetchone()
            if row is None:
                row = self.conn.execute("SELECT * FROM failures WHERE at > ? ORDER BY at DESC LIMIT 1",
                                        (time.time() - max_age,)).fetchone()
        return dict(row) if row else None

    def remove_failure(self, msg_id: int):
        with self.lock:
            self.conn.execute("DELETE FROM failures WHERE msg_id = ?", (msg_id,))
            self.conn.commit()

    def add_video_job(self, msg_id: int, file_id: str, link: str, text: str, trust: bool):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO video_jobs VALUES (?, ?, ?, ?, ?, ?)",
                              (msg_id, file_id, link, text, int(trust), time.time()))
            self.conn.commit()

    def remove_video_job(self, msg_id: int):
        with self.lock:
            self.conn.execute("DELETE FROM video_jobs WHERE msg_id = ?", (msg_id,))
            self.conn.commit()

    def video_jobs(self) -> List[Dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM video_jobs ORDER BY at").fetchall()]

    def get_meta(self, key: str, default: str = '') -> str:
        with self.lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
            self.conn.commit()
