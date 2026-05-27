"""Precomputed aggregates for /state pages (build at deploy; read at runtime).

Verified from: app.py generate_state_page / generate_state_page_html consumers.
"""
from __future__ import annotations

import gzip
import json
import os
import time
from typing import Any

BUNDLE_VERSION = 1
DEFAULT_REL_PATH = os.path.join('data', 'state_page_aggregates.json.gz')


def aggregates_path(app_root: str) -> str:
    override = (os.environ.get('PBJ_STATE_AGGREGATES_PATH') or '').strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(app_root, override.replace('/', os.sep))
    return os.path.join(app_root, DEFAULT_REL_PATH.replace('/', os.sep))


def _file_mtime(path: str | None) -> float:
    if not path or not os.path.isfile(path):
        return 0.0
    try:
        return float(os.path.getmtime(path))
    except OSError:
        return 0.0


def resolve_source_path(app_root: str, path: str) -> str:
    p = (path or '').strip()
    if not p:
        return ''
    if os.path.isabs(p):
        return p
    return os.path.join(app_root, p.replace('/', os.sep))


def bundle_sources_valid(app_root: str, bundle: dict[str, Any]) -> bool:
    """True when on-disk CSV mtimes match what the bundle was built from."""
    sources = bundle.get('sources') or {}
    if not sources:
        return False
    for _key, meta in sources.items():
        if not isinstance(meta, dict):
            return False
        recorded = meta.get('mtime')
        path = meta.get('path') or ''
        if recorded is None or not path:
            return False
        abs_path = resolve_source_path(app_root, path)
        if abs(float(recorded)) != _file_mtime(abs_path):
            return False
    return True


def load_bundle(app_root: str) -> dict[str, Any] | None:
    path = aggregates_path(app_root)
    if not os.path.isfile(path):
        return None
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
    except Exception as e:
        print(f'[state_page_aggregates] load failed {path}: {e}', flush=True)
        return None
    if not isinstance(data, dict) or data.get('version') != BUNDLE_VERSION:
        return None
    if not bundle_sources_valid(app_root, data):
        print('[state_page_aggregates] bundle stale (source CSV mtime changed)', flush=True)
        return None
    return data


def write_bundle(app_root: str, bundle: dict[str, Any]) -> str:
    path = aggregates_path(app_root)
    os.makedirs(os.path.dirname(path) or app_root, exist_ok=True)
    payload = json.dumps(bundle, separators=(',', ':'), ensure_ascii=False)
    if path.endswith('.gz'):
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            f.write(payload)
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(payload)
    return path


def source_meta(path: str | None, app_root: str) -> dict[str, Any]:
    if not path:
        return {'path': '', 'mtime': 0.0}
    abs_p = os.path.abspath(path)
    root = os.path.abspath(app_root)
    try:
        rel = os.path.relpath(abs_p, root)
        stored = rel if not rel.startswith('..') else abs_p
    except ValueError:
        stored = abs_p
    stored_path = stored.replace('\\', '/') if isinstance(stored, str) else stored
    return {'path': stored_path, 'mtime': _file_mtime(abs_p)}
