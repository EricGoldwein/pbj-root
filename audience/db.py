"""SQLite persistence for PBJ320 audience contacts, subscriptions, and events."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

_log = logging.getLogger(__name__)
_path_logged = False
_production_checked = False


def is_production_environment() -> bool:
    return bool(
        os.environ.get('RENDER')
        or os.environ.get('PBJ_ENV', '').strip().lower() in ('production', 'prod')
        or os.environ.get('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', '').strip().lower() in ('1', 'true', 'yes')
    )


def db_path() -> str:
    explicit = os.environ.get('SUBSCRIBERS_DB_PATH', '').strip()
    if explicit:
        return explicit
    instance = os.path.join(os.getcwd(), 'instance', 'subscribers.db')
    if os.path.isdir(os.path.join(os.getcwd(), 'instance')):
        return instance
    return os.path.join(os.getcwd(), 'subscribers.db')


def ensure_production_db_config() -> None:
    """Warn in production when audience DB is not on a configured persistent path.

    Prefer SUBSCRIBERS_DB_PATH on a Render persistent disk. Missing config must not
    prevent process boot; signup routes degrade via connect errors instead.
    """
    global _production_checked
    if _production_checked:
        return
    _production_checked = True
    if not is_production_environment():
        return
    path = os.environ.get('SUBSCRIBERS_DB_PATH', '').strip()
    if not path:
        _log.warning(
            'SUBSCRIBERS_DB_PATH is unset in production; audience data may be lost on restart. '
            'Set SUBSCRIBERS_DB_PATH to a persistent disk path. See docs/audience-system-developer.md'
        )
        return
    parent = os.path.dirname(path) or '.'
    if not os.path.isdir(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            _log.error('SUBSCRIBERS_DB_PATH parent not writable: %s (%s)', parent, exc)
            return
    _log.info('Audience DB production path verified: %s', path)


def connect() -> sqlite3.Connection:
    ensure_production_db_config()
    path = db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    global _path_logged
    ensure_production_db_config()
    path = db_path()
    if not _path_logged:
        persistent = bool(os.environ.get('SUBSCRIBERS_DB_PATH', '').strip())
        _log.info(
            'Audience DB: %s%s',
            path,
            ' (persistent)' if persistent else ' (local dev)',
        )
        _path_logged = True

    with db_session() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL UNIQUE COLLATE NOCASE,
                name VARCHAR(200),
                organization VARCHAR(200),
                role VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                first_source_url TEXT,
                first_referrer TEXT,
                first_utm_source VARCHAR(128),
                first_utm_medium VARCHAR(128),
                first_utm_campaign VARCHAR(128),
                last_seen_at TIMESTAMP,
                anonymous_visitor_id VARCHAR(128)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                subscription_type VARCHAR(64) NOT NULL,
                resource_type VARCHAR(32),
                resource_id VARCHAR(64),
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                source_url TEXT,
                cta_variant VARCHAR(64),
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unsubscribed_at TIMESTAMP,
                UNIQUE(contact_id, subscription_type, resource_type, resource_id)
            );

            CREATE TABLE IF NOT EXISTS signup_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
                source_url TEXT,
                page_type VARCHAR(32),
                facility_ccn VARCHAR(16),
                facility_name VARCHAR(200),
                state_abbr VARCHAR(8),
                state_name VARCHAR(64),
                chain_identifier VARCHAR(64),
                search_filters TEXT,
                referrer TEXT,
                utm_source VARCHAR(128),
                utm_medium VARCHAR(128),
                utm_campaign VARCHAR(128),
                cta_variant VARCHAR(64),
                cta_id VARCHAR(64),
                device_category VARCHAR(16),
                visitor_status VARCHAR(16),
                facility_pages_viewed INTEGER,
                trigger_reason VARCHAR(64),
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS consent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                action VARCHAR(32) NOT NULL,
                subscription_type VARCHAR(64),
                consent_copy_version VARCHAR(32) NOT NULL,
                consent_language TEXT,
                source_url TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                rating VARCHAR(16),
                response TEXT NOT NULL,
                source_url TEXT,
                context TEXT,
                quote_permission VARCHAR(32),
                attribution_name VARCHAR(200),
                attribution_organization VARCHAR(200),
                review_status VARCHAR(32) DEFAULT 'pending_review',
                publication_status VARCHAR(32) DEFAULT 'pending_review',
                is_anonymous INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS engagement_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anonymous_or_contact_id VARCHAR(128) NOT NULL,
                event_name VARCHAR(64) NOT NULL,
                page_type VARCHAR(32),
                resource_id VARCHAR(64),
                metadata TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS prompt_dismissals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_key VARCHAR(128) NOT NULL,
                prompt_type VARCHAR(64) NOT NULL,
                dismissed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(visitor_key, prompt_type)
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL,
                subscription_type VARCHAR(64) NOT NULL,
                resource_type VARCHAR(32),
                resource_id VARCHAR(64),
                subject VARCHAR(300),
                body_preview TEXT,
                provider VARCHAR(32),
                provider_campaign_id VARCHAR(128),
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                recipient_count INTEGER DEFAULT 0,
                test_mode INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS campaign_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                subscription_id INTEGER REFERENCES subscriptions(id),
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                provider_message_id VARCHAR(128),
                idempotency_key VARCHAR(128),
                is_test INTEGER DEFAULT 0,
                sent_at TIMESTAMP,
                error_message TEXT,
                UNIQUE(campaign_id, contact_id)
            );

            CREATE TABLE IF NOT EXISTS campaign_audience (
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                subscription_id INTEGER REFERENCES subscriptions(id),
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (campaign_id, contact_id)
            );

            CREATE INDEX IF NOT EXISTS idx_subscriptions_type_status
                ON subscriptions(subscription_type, status);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_resource
                ON subscriptions(resource_type, resource_id, status);
            CREATE INDEX IF NOT EXISTS idx_engagement_visitor
                ON engagement_events(anonymous_or_contact_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_signup_context_contact
                ON signup_context(contact_id, created_at);
            '''
        )
        _migrate_legacy_subscribers(conn)
        _migrate_insights_subscription_type(conn)
        _migrate_campaign_audit_columns(conn)


def _migrate_legacy_subscribers(conn: sqlite3.Connection) -> None:
    tables = {
        r['name']
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='subscribers'"
        ).fetchall()
    }
    if 'subscribers' not in tables:
        return
    rows = conn.execute(
        'SELECT email, source, created_at FROM subscribers ORDER BY created_at'
    ).fetchall()
    for row in rows:
        email = (row['email'] or '').strip().lower()
        if not email:
            continue
        conn.execute(
            '''
            INSERT OR IGNORE INTO contacts (email, first_source_url, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ''',
            (email, row['source'] or 'legacy', row['created_at'], row['created_at']),
        )
        contact = conn.execute(
            'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (email,)
        ).fetchone()
        if not contact:
            continue
        conn.execute(
            '''
            INSERT OR IGNORE INTO subscriptions
                (contact_id, subscription_type, status, cta_variant, source_url, subscribed_at)
            VALUES (?, 'pbj320_insights', 'active', 'legacy_subscribe', ?, ?)
            ''',
            (contact['id'], row['source'] or 'legacy', row['created_at']),
        )


def _migrate_campaign_audit_columns(conn: sqlite3.Connection) -> None:
    cols = {
        r['name']
        for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()
    }
    additions = {
        'excluded_count': 'INTEGER DEFAULT 0',
        'successful_count': 'INTEGER DEFAULT 0',
        'failed_count': 'INTEGER DEFAULT 0',
        'frozen_at': 'TIMESTAMP',
        'send_started_at': 'TIMESTAMP',
        'idempotency_key': 'VARCHAR(64)',
    }
    for name, typedef in additions.items():
        if name not in cols:
            conn.execute(f'ALTER TABLE campaigns ADD COLUMN {name} {typedef}')
    send_cols = {
        r['name']
        for r in conn.execute("PRAGMA table_info(campaign_sends)").fetchall()
    }
    for name, typedef in (
        ('is_test', 'INTEGER DEFAULT 0'),
        ('idempotency_key', 'VARCHAR(128)'),
    ):
        if name not in send_cols:
            conn.execute(f'ALTER TABLE campaign_sends ADD COLUMN {name} {typedef}')


def _migrate_insights_subscription_type(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE subscriptions SET subscription_type = 'pbj320_insights' WHERE subscription_type = 'insights'"
    )
    conn.execute(
        "UPDATE subscriptions SET status = 'active' WHERE subscription_type = 'pbj320_insights' AND status = 'pending_external'"
    )
    conn.execute(
        "UPDATE consent_events SET subscription_type = 'pbj320_insights' WHERE subscription_type = 'insights'"
    )


def execute_with_retry(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
    *,
    retries: int = 2,
) -> sqlite3.Cursor:
    for attempt in range(retries):
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as exc:
            if 'locked' in str(exc).lower() and attempt < retries - 1:
                time.sleep(0.25)
                continue
            raise
    raise RuntimeError('unreachable')
