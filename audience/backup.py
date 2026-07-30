"""SQLite backup and restore for PBJ320 audience database."""

from __future__ import annotations

import glob
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any

from audience.db import db_path, is_production_environment

_log = logging.getLogger(__name__)

CORE_TABLES = (
    'contacts',
    'subscriptions',
    'signup_context',
    'consent_events',
    'feedback',
    'engagement_events',
    'prompt_dismissals',
    'campaigns',
    'campaign_sends',
    'campaign_audience',
)


def backup_dir() -> str:
    explicit = os.environ.get('PBJ_AUDIENCE_BACKUP_DIR', '').strip()
    if explicit:
        return explicit
    parent = os.path.dirname(os.path.abspath(db_path())) or '.'
    return os.path.join(parent, 'audience-backups')


def retention_count() -> int:
    raw = os.environ.get('PBJ_AUDIENCE_BACKUP_RETENTION', '14').strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 14


def _timestamp_label() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def _ensure_backup_dir_writable(directory: str) -> None:
    if not directory:
        raise RuntimeError('backup_dir_not_configured')
    if is_production_environment() and not os.environ.get('PBJ_AUDIENCE_BACKUP_DIR', '').strip():
        raise RuntimeError(
            'PBJ_AUDIENCE_BACKUP_DIR must be set to a persistent disk path in production'
        )
    os.makedirs(directory, exist_ok=True)
    probe = os.path.join(directory, '.pbj_backup_write_test')
    try:
        with open(probe, 'w', encoding='utf-8') as fh:
            fh.write('ok')
        os.remove(probe)
    except OSError as exc:
        raise RuntimeError(f'backup_dir_not_writable: {directory}') from exc


def _integrity_ok(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute('PRAGMA integrity_check').fetchone()
        return bool(row and row[0] == 'ok')
    except sqlite3.DatabaseError:
        return False


def table_counts(conn: sqlite3.Connection) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for table in CORE_TABLES:
        try:
            counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
        except sqlite3.OperationalError:
            counts[table] = None
    return counts


def cleanup_old_backups(directory: str | None = None, *, keep: int | None = None) -> int:
    dest_dir = directory or backup_dir()
    keep_n = keep if keep is not None else retention_count()
    files = sorted(
        glob.glob(os.path.join(dest_dir, 'audience-*.db')),
        key=os.path.getmtime,
        reverse=True,
    )
    removed = 0
    for old in files[keep_n:]:
        try:
            os.remove(old)
            removed += 1
        except OSError:
            _log.warning('Failed to remove old audience backup: %s', old)
    return removed


def backup_database(
    *,
    source_path: str | None = None,
    destination_dir: str | None = None,
) -> dict[str, Any]:
    """
    Create a timestamped backup using SQLite's online backup API (safe with WAL + concurrent readers/writers).
    """
    src_path = os.path.abspath(source_path or db_path())
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f'source_database_missing: {src_path}')

    dest_dir = os.path.abspath(destination_dir or backup_dir())
    _ensure_backup_dir_writable(dest_dir)

    dest_file = os.path.join(dest_dir, f'audience-{_timestamp_label()}.db')
    src = sqlite3.connect(f'file:{src_path}?mode=ro', uri=True, timeout=30.0)
    dst = sqlite3.connect(dest_file, timeout=30.0)
    try:
        with dst:
            src.backup(dst)
        if not _integrity_ok(dst):
            raise RuntimeError('backup_integrity_failed')
    except Exception:
        if os.path.isfile(dest_file):
            try:
                os.remove(dest_file)
            except OSError:
                pass
        raise
    finally:
        src.close()
        dst.close()

    size = os.path.getsize(dest_file)
    removed = cleanup_old_backups(dest_dir)
    _log.info(
        'Audience DB backup ok path=%s size_bytes=%d removed_old=%d',
        dest_file,
        size,
        removed,
    )
    return {
        'ok': True,
        'backupPath': dest_file,
        'sizeBytes': size,
        'removedOld': removed,
        'sourcePath': src_path,
    }


def validate_backup_file(path: str) -> dict[str, Any]:
    backup_path = os.path.abspath(path)
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f'backup_missing: {backup_path}')

    try:
        conn = sqlite3.connect(f'file:{backup_path}?mode=ro', uri=True, timeout=30.0)
    except sqlite3.DatabaseError as exc:
        raise RuntimeError('backup_corrupt') from exc
    try:
        if not _integrity_ok(conn):
            raise RuntimeError('backup_corrupt')
        return {
            'ok': True,
            'integrity': 'ok',
            'tableCounts': table_counts(conn),
            'sizeBytes': os.path.getsize(backup_path),
            'backupPath': backup_path,
        }
    finally:
        conn.close()


def restore_database(
    backup_path: str,
    *,
    target_path: str | None = None,
    confirm_overwrite: bool = False,
) -> dict[str, Any]:
    if not confirm_overwrite:
        raise RuntimeError('restore_requires_confirm_overwrite')

    report = validate_backup_file(backup_path)
    target = os.path.abspath(target_path or db_path())
    safety_copy: str | None = None
    if os.path.isfile(target):
        safety_copy = f'{target}.pre-restore-{_timestamp_label()}.bak'
        shutil.copy2(target, safety_copy)
    else:
        os.makedirs(os.path.dirname(target) or '.', exist_ok=True)

    tmp = f'{target}.restore-tmp-{_timestamp_label()}'
    src = sqlite3.connect(f'file:{os.path.abspath(backup_path)}?mode=ro', uri=True, timeout=30.0)
    dst = sqlite3.connect(tmp, timeout=30.0)
    try:
        with dst:
            src.backup(dst)
        if not _integrity_ok(dst):
            raise RuntimeError('restore_integrity_failed')
    except Exception:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    finally:
        src.close()
        dst.close()

    os.replace(tmp, target)
    restored = validate_backup_file(target)
    _log.info(
        'Audience DB restore ok target=%s from=%s safety=%s',
        target,
        backup_path,
        safety_copy or 'none',
    )
    return {
        'ok': True,
        'targetPath': target,
        'backupPath': os.path.abspath(backup_path),
        'safetyCopyPath': safety_copy,
        'tableCounts': restored['tableCounts'],
        'priorBackupTableCounts': report['tableCounts'],
    }
