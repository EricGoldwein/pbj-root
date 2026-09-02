"""Audience SQLite backup and restore utilities."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from audience import db as audience_db
from audience.backup import (
    backup_database,
    cleanup_old_backups,
    restore_database,
    validate_backup_file,
)


@pytest.fixture()
def db_env(monkeypatch, tmp_path):
    db_file = tmp_path / 'subscribers.db'
    backup_root = tmp_path / 'backups'
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', str(db_file))
    monkeypatch.setenv('PBJ_AUDIENCE_BACKUP_DIR', str(backup_root))
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', raising=False)
    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()
    yield db_file, backup_root


def test_successful_backup(db_env):
    db_file, backup_root = db_env
    with audience_db.db_session() as conn:
        conn.execute(
            "INSERT INTO contacts (email) VALUES ('backup-test@example.com')"
        )
    result = backup_database()
    assert result['ok'] is True
    assert os.path.isfile(result['backupPath'])
    assert result['sizeBytes'] > 0
    assert str(backup_root) in result['backupPath']
    report = validate_backup_file(result['backupPath'])
    assert report['tableCounts']['contacts'] >= 1


def test_backup_while_database_still_writable(db_env):
    db_file, _backup_root = db_env
    with audience_db.db_session() as conn:
        conn.execute("INSERT INTO contacts (email) VALUES ('before@example.com')")
    result = backup_database()
    with audience_db.db_session() as conn:
        conn.execute("INSERT INTO contacts (email) VALUES ('after@example.com')")
        count = conn.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]
    assert count >= 2
    assert os.path.isfile(result['backupPath'])


def test_retention_cleanup(db_env, monkeypatch):
    db_file, backup_root = db_env
    backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('PBJ_AUDIENCE_BACKUP_RETENTION', '2')
    for idx in range(4):
        path = backup_root / f'audience-2026010{idx}-12000{idx}.db'
        src = sqlite3.connect(str(db_file))
        dst = sqlite3.connect(str(path))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    removed = cleanup_old_backups(str(backup_root), keep=2)
    assert removed == 2
    remaining = list(backup_root.glob('audience-*.db'))
    assert len(remaining) == 2


def test_missing_source_database(monkeypatch, tmp_path):
    missing = tmp_path / 'missing.db'
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', str(missing))
    with pytest.raises(FileNotFoundError, match='source_database_missing'):
        backup_database()


def test_unwritable_backup_directory(db_env, monkeypatch):
    _db_file, _backup_root = db_env
    if os.name == 'nt':
        pytest.skip('Read-only directory semantics differ on Windows')
    readonly = _backup_root / 'readonly'
    readonly.mkdir()
    os.chmod(readonly, 0o444)
    try:
        with pytest.raises(RuntimeError, match='backup_dir_not_writable'):
            backup_database(destination_dir=str(readonly))
    finally:
        os.chmod(readonly, 0o755)


def test_corrupt_backup_rejected(db_env, tmp_path):
    corrupt = tmp_path / 'corrupt.db'
    corrupt.write_bytes(b'not-a-sqlite-database')
    with pytest.raises(RuntimeError, match='backup_corrupt'):
        validate_backup_file(str(corrupt))


def test_successful_restore_into_temporary_database(db_env):
    db_file, backup_root = db_env
    with audience_db.db_session() as conn:
        conn.execute("INSERT INTO contacts (email) VALUES ('restore-me@example.com')")
    backup = backup_database()
    with audience_db.db_session() as conn:
        conn.execute('DELETE FROM contacts')
        assert conn.execute('SELECT COUNT(*) FROM contacts').fetchone()[0] == 0

    restore_target = db_file.parent / 'restored.db'
    result = restore_database(
        backup['backupPath'],
        target_path=str(restore_target),
        confirm_overwrite=True,
    )
    assert result['ok'] is True
    assert result['tableCounts']['contacts'] >= 1
    conn = sqlite3.connect(restore_target)
    try:
        row = conn.execute(
            "SELECT email FROM contacts WHERE email = 'restore-me@example.com'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_restore_integrity_failure_on_bad_backup(db_env, tmp_path):
    bad = tmp_path / 'bad-backup.db'
    conn = sqlite3.connect(bad)
    conn.execute('CREATE TABLE t (id INTEGER)')
    conn.commit()
    conn.close()
    # Truncate to corrupt pages while keeping sqlite header-ish content
    data = bad.read_bytes()
    bad.write_bytes(data[:100])
    with pytest.raises(RuntimeError, match='backup_corrupt'):
        restore_database(str(bad), target_path=str(tmp_path / 'out.db'), confirm_overwrite=True)


def test_restore_requires_explicit_confirmation(db_env):
    backup = backup_database()
    with pytest.raises(RuntimeError, match='restore_requires_confirm_overwrite'):
        restore_database(backup['backupPath'], confirm_overwrite=False)


def test_production_requires_backup_dir(db_env, monkeypatch):
    monkeypatch.setenv('RENDER', '1')
    monkeypatch.delenv('PBJ_AUDIENCE_BACKUP_DIR', raising=False)
    audience_db._production_checked = False
    with pytest.raises(RuntimeError, match='PBJ_AUDIENCE_BACKUP_DIR'):
        backup_database()
