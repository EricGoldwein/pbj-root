"""Durable SQLite store for contact-form rate limits, tokens, quarantine, fingerprints."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional, Sequence

from contact_protection import config

_log = logging.getLogger('pbj.contact_protection')
_init_lock = threading.Lock()
_initialized_paths: set[str] = set()
_override_path: Optional[str] = None


def set_store_path_for_tests(path: str) -> None:
    global _override_path
    _override_path = path
    _initialized_paths.discard(path)


def resolved_db_path() -> str:
    if _override_path:
        return _override_path
    return config.db_path()


def _hash_identifier(kind: str, value: str) -> str:
    pepper = config.rate_limit_pepper().encode('utf-8')
    msg = f'{kind}:{value}'.encode('utf-8')
    return hmac.new(pepper, msg, hashlib.sha256).hexdigest()


def hash_ip(ip: str) -> str:
    return _hash_identifier('ip', (ip or '').strip())


def hash_email(email: str) -> str:
    return _hash_identifier('email', (email or '').strip().lower())


def hash_token(token: str) -> str:
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def hash_message(message: str) -> str:
    normalized = ' '.join((message or '').lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    db = path or resolved_db_path()
    parent = os.path.dirname(db)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db, timeout=10.0)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn, db)
    return conn


def _ensure_schema(conn: sqlite3.Connection, path: str) -> None:
    if path in _initialized_paths:
        return
    with _init_lock:
        if path in _initialized_paths:
            return
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rate_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bucket TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rate_bucket_time
                ON rate_events(bucket, created_at);

            CREATE TABLE IF NOT EXISTS used_tokens (
                token_hash TEXT PRIMARY KEY,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS message_fingerprints (
                msg_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_msg_fp_time
                ON message_fingerprints(msg_hash, created_at);

            CREATE TABLE IF NOT EXISTS quarantine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                reason_codes TEXT NOT NULL,
                email_domain TEXT,
                name_len INTEGER,
                message_len INTEGER,
                message_hash TEXT,
                press INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS contact_reason_counts (
                day TEXT NOT NULL,
                reason TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, reason)
            );
            """
        )
        conn.commit()
        _initialized_paths.add(path)


def init_store() -> None:
    with session():
        pass


@contextmanager
def session(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_outcome(reason: str) -> None:
    day = time.strftime('%Y-%m-%d', time.gmtime())
    try:
        with session() as conn:
            conn.execute(
                """
                INSERT INTO contact_reason_counts(day, reason, count) VALUES (?, ?, 1)
                ON CONFLICT(day, reason) DO UPDATE SET count = count + 1
                """,
                (day, reason),
            )
    except Exception as exc:
        _log.warning('outcome_count_failed reason=%s err=%s', reason, type(exc).__name__)


def aggregate_reason_counts(day: Optional[str] = None) -> dict[str, int]:
    day = day or time.strftime('%Y-%m-%d', time.gmtime())
    with session() as conn:
        rows = conn.execute(
            'SELECT reason, count FROM contact_reason_counts WHERE day = ?', (day,)
        ).fetchall()
    return {str(r['reason']): int(r['count']) for r in rows}


def outcome_counts_for_day(day: Optional[str] = None) -> dict[str, int]:
    return aggregate_reason_counts(day)


def count_rate_events(bucket: str, window_seconds: float) -> int:
    cutoff = time.time() - window_seconds
    with session() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM rate_events WHERE bucket = ? AND created_at >= ?',
            (bucket, cutoff),
        ).fetchone()
        return int(row['c'] if row else 0)


def add_rate_event(bucket: str) -> None:
    with session() as conn:
        conn.execute(
            'INSERT INTO rate_events(bucket, created_at) VALUES (?, ?)',
            (bucket, time.time()),
        )
        conn.execute(
            'DELETE FROM rate_events WHERE created_at < ?',
            (time.time() - 172800,),
        )


def token_already_used(token: str) -> bool:
    th = hash_token(token)
    with session() as conn:
        row = conn.execute(
            'SELECT 1 FROM used_tokens WHERE token_hash = ?', (th,)
        ).fetchone()
        return row is not None


def mark_token_used(token: str) -> None:
    th = hash_token(token)
    with session() as conn:
        conn.execute(
            'INSERT OR IGNORE INTO used_tokens(token_hash, created_at) VALUES (?, ?)',
            (th, time.time()),
        )
        conn.execute(
            'DELETE FROM used_tokens WHERE created_at < ?',
            (time.time() - 86400,),
        )


def recent_duplicate_message(message: str, window_seconds: float = 86400.0) -> bool:
    mh = hash_message(message)
    cutoff = time.time() - window_seconds
    with session() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM message_fingerprints WHERE msg_hash = ? AND created_at >= ?',
            (mh, cutoff),
        ).fetchone()
        return int(row['c'] if row else 0) >= 1


def record_message_fingerprint(message: str) -> None:
    with session() as conn:
        conn.execute(
            'INSERT INTO message_fingerprints(msg_hash, created_at) VALUES (?, ?)',
            (hash_message(message), time.time()),
        )
        conn.execute(
            'DELETE FROM message_fingerprints WHERE created_at < ?',
            (time.time() - 172800,),
        )


def quarantine_submission(
    *,
    reason_codes: Sequence[str],
    email: str,
    name: str,
    message: str,
    is_press: bool,
) -> None:
    domain = ''
    if '@' in (email or ''):
        domain = email.rsplit('@', 1)[-1].lower()[:120]
    with session() as conn:
        conn.execute(
            """
            INSERT INTO quarantine(
                created_at, reason_codes, email_domain, name_len, message_len, message_hash, press
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                ','.join(reason_codes),
                domain,
                len(name or ''),
                len(message or ''),
                hash_message(message),
                1 if is_press else 0,
            ),
        )


def reset_store_for_tests(path: Optional[str] = None) -> None:
    db = path or resolved_db_path()
    _initialized_paths.discard(db)
    if os.path.isfile(db):
        os.remove(db)
    for suffix in ('-wal', '-shm'):
        p = db + suffix
        if os.path.isfile(p):
            os.remove(p)
