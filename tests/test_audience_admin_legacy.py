"""Legacy /admin/subscribers route security and unified admin access."""

from __future__ import annotations

import os

import pytest

from audience.admin_auth import SESSION_KEY, _session_token


@pytest.fixture()
def admin_key(monkeypatch):
    monkeypatch.setenv('ADMIN_VIEW_KEY', 'secret-admin-key')
    monkeypatch.delenv('PBJ_ADMIN_KEY', raising=False)


@pytest.fixture()
def client(admin_key):
    from app import app

    app.config['SECRET_KEY'] = 'test-secret-key'
    return app.test_client()


def test_legacy_subscribers_rejects_query_key(client):
    resp = client.get('/admin/subscribers?key=secret-admin-key')
    assert resp.status_code == 403
    assert resp.get_json()['error'] == 'Unauthorized'
    assert resp.headers.get('X-Robots-Tag') == 'noindex, nofollow'
    assert 'no-store' in (resp.headers.get('Cache-Control') or '')


def test_legacy_subscribers_unauthenticated_redirects_to_login(client):
    resp = client.get('/admin/subscribers')
    assert resp.status_code in (302, 303)
    location = resp.headers.get('Location') or ''
    assert '/admin/audience/login' in location
    assert 'key=' not in location.lower()
    assert 'secret' not in location.lower()


def test_legacy_subscribers_session_redirects_to_audience(client):
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = _session_token('secret-admin-key')
    resp = client.get('/admin/subscribers')
    assert resp.status_code in (302, 303)
    location = resp.headers.get('Location') or ''
    assert location.endswith('/admin/audience')
    assert 'key=' not in location.lower()


def test_legacy_subscribers_header_auth_redirects_to_audience(client):
    resp = client.get(
        '/admin/subscribers',
        headers={'Authorization': 'Bearer secret-admin-key'},
    )
    assert resp.status_code in (302, 303)
    assert (resp.headers.get('Location') or '').endswith('/admin/audience')


def test_audience_admin_unauthenticated_redirects(client):
    resp = client.get('/admin/audience')
    assert resp.status_code in (302, 303)
    location = resp.headers.get('Location') or ''
    assert '/admin/audience/login' in location
    assert 'key=' not in location.lower()


def test_audience_admin_session_succeeds(client):
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = _session_token('secret-admin-key')
    resp = client.get('/admin/audience')
    assert resp.status_code == 200
    assert b'PBJ320 audience' in resp.data
    assert b'noindex' in resp.data.lower() or resp.headers.get('X-Robots-Tag')


def test_audience_csv_export_requires_auth(client):
    resp = client.get('/admin/audience', headers={'Accept': 'text/csv'})
    assert resp.status_code in (302, 303, 403)


def test_audience_csv_export_header_auth_succeeds(client, monkeypatch, tmp_path):
    db_path = tmp_path / 'subscribers.db'
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', str(db_path))
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', raising=False)
    from audience import db as audience_db

    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()

    resp = client.get(
        '/admin/audience',
        headers={
            'Authorization': 'Bearer secret-admin-key',
            'Accept': 'text/csv',
        },
    )
    assert resp.status_code == 200
    assert 'text/csv' in (resp.headers.get('Content-Type') or '')
    assert resp.data.startswith(b'email,')
    body = resp.get_data(as_text=True)
    assert 'secret-admin-key' not in body


def test_audience_json_api_header_auth_succeeds(client, monkeypatch, tmp_path):
    db_path = tmp_path / 'subscribers.db'
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', str(db_path))
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', raising=False)
    from audience import db as audience_db

    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()

    resp = client.get(
        '/admin/audience',
        headers={
            'Authorization': 'Bearer secret-admin-key',
            'Accept': 'application/json',
        },
    )
    assert resp.status_code == 200
    assert resp.is_json


def test_conversion_queries_require_auth(client):
    resp = client.get('/api/audience/conversion-queries')
    assert resp.status_code == 403


def test_conversion_queries_header_auth(client):
    resp = client.get(
        '/api/audience/conversion-queries',
        headers={'Authorization': 'Bearer secret-admin-key'},
    )
    assert resp.status_code == 200
