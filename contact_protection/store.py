"""Durable SQLite store for rate limits, used Turnstile tokens, quarantine, and reason counters."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from contact_protection.config import contact_protection_db_path, hash_pepper

_log = logging.getLogger('pbj.contact_protection')
_init_lock = threading.Lock()
_initialized_paths: set[str] = set()
_override_path: Optional[str] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bucket TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_rate_bucket_time ON rate_events(bucket, created_at);

CREATE TABLE IF NOT EXISTS used_tokens (
  token_hash TEXT PRIMARY KEY,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS message_fingerprints (
  fp TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_msg_fp_time ON message_fingerprints(fp, created_at);

CREATE TABLE IF NOT EXISTS quarantine (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at REAL NOT NULL,
  reason_codes TEXT NOT NULL,
  email_domain TEXT,
  name_len INTEGER,
  message_len INTEGER,
  message_fp TEXT
);

CREATE TABLE IF NOT EXISTS contact_reason_counts (
  day TEXT NOT NULL,
  reason TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, reason)
);
"""


def set_store_path_for_tests(path: str) -> None:
    global _override_path
    _override_path = path


def db_path() -> str:
    if _override_path:
        return _override_path
    return contact_protection_db_path()


def hash_identifier(value: str) -> str:
    pepper = hash_pepper().encode('utf-8')
    return hashlib.sha256(pepper + b'|' + (value or '').encode('utf-8')).hexdigest()[:32]


def hash_ip(ip: str) -> str:
    return hash_identifier(f'ip:{ip or "unknown"}')


def hash_email(email: str) -> str:
    return hash_identifier(f'email:{(email or "").strip().lower()}')


def message_fingerprint(message: str) -> str:
    import re

    norm = re.sub(r'\s+', ' ', (message or '').strip().lower())
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()[:32]


def _connect() -> sqlite3.Connection:
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_store() -> None:
    """Ensure schema exists (alias for ops / docs)."""
    ensure_schema()


def aggregate_reason_counts(day: Optional[str] = None) -> dict[str, int]:
    """Return reason → count for a UTC day (default: today)."""
    if day is None:
        return reason_counts_today()
    with session() as conn:
        rows = conn.execute(
            'SELECT reason, count FROM contact_reason_counts WHERE day = ?',
            (day,),
        ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def ensure_schema() -> None:
    path = db_path()
    if path in _initialized_paths:
        return
    with _init_lock:
        if path in _initialized_paths:
            return
        with _connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        _initialized_paths.add(path)


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    ensure_schema()
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_store_for_tests() -> None:
    path = db_path()
    _initialized_paths.discard(path)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    for suffix in ('-wal', '-shm'):
        side = path + suffix
        if os.path.isfile(side):
            try:
                os.remove(side)
            except OSError:
                pass
    ensure_schema()


def record_reason(reason: str) -> None:
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
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
        _log.warning('reason_log_failed reason=%s err=%s', reason, type(exc).__name__)


def count_rate_events(bucket: str, window_seconds: int) -> int:
    cutoff = time.time() - window_seconds
    with session() as conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM rate_events WHERE bucket = ? AND created_at >= ?',
            (bucket, cutoff),
        ).fetchone()
    return int(row[0] if row else 0)


def add_rate_event(bucket: str) -> None:
    with session() as conn:
        conn.execute(
            'INSERT INTO rate_events(bucket, created_at) VALUES (?, ?)',
            (bucket, time.time()),
        )


def token_already_used(token_hash: str) -> bool:
    with session() as conn:
        row = conn.execute(
            'SELECT 1 FROM used_tokens WHERE token_hash = ?',
            (token_hash,),
        ).fetchone()
    return bool(row)


def mark_token_used(token_hash: str) -> None:
    with session() as conn:
        conn.execute(
            'INSERT OR IGNORE INTO used_tokens(token_hash, created_at) VALUES (?, ?)',
            (token_hash, time.time()),
        )
        conn.execute(
            'DELETE FROM used_tokens WHERE created_at < ?',
            (time.time() - 86400,),
        )


def recent_duplicate_message(message: str, window_seconds: int = 86400) -> bool:
    fp = message_fingerprint(message)
    cutoff = time.time() - window_seconds
    with session() as conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM message_fingerprints WHERE fp = ? AND created_at >= ?',
            (fp, cutoff),
        ).fetchone()
    return int(row[0] if row else 0) >= 1


def record_message(message: str) -> None:
    fp = message_fingerprint(message)
    with session() as conn:
        conn.execute(
            'INSERT INTO message_fingerprints(fp, created_at) VALUES (?, ?)',
            (fp, time.time()),
        )


def quarantine_submission(
    *,
    reason_codes: list[str],
    email_domain: str,
    name_len: int,
    message_len: int,
    message_fp: str,
) -> None:
    with session() as conn:
        conn.execute(
            """
            INSERT INTO quarantine(created_at, reason_codes, email_domain, name_len, message_len, message_fp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                ','.join(reason_codes),
                (email_domain or '')[:120],
                name_len,
                message_len,
                message_fp,
            ),
        )


def reason_counts_today() -> dict[str, int]:
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    with session() as conn:
        rows = conn.execute(
            'SELECT reason, count FROM contact_reason_counts WHERE day = ?',
            (day,),
        ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}
