"""Precomputed aggregates for /state pages (build at deploy; read at runtime).

Verified from: app.py generate_state_page / generate_state_page_html consumers.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from typing import Any

BUNDLE_VERSION = 2
DEFAULT_REL_PATH = os.path.join('data', 'state_page_aggregates.json.gz')
_SIGNATURE_CHUNK = 65536


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


def _file_size(path: str | None) -> int:
    if not path or not os.path.isfile(path):
        return 0
    try:
        return int(os.path.getsize(path))
    except OSError:
        return 0


def resolve_source_path(app_root: str, path: str) -> str:
    p = (path or '').strip()
    if not p:
        return ''
    if os.path.isabs(p):
        return p
    return os.path.join(app_root, p.replace('/', os.sep))


def file_signature(path: str | None) -> dict[str, Any]:
    """Stable source fingerprint (size + sampled sha256) — avoids brittle mtime-only checks on Render."""
    if not path or not os.path.isfile(path):
        return {'path': '', 'size_bytes': 0, 'sha256': '', 'mtime': 0.0}
    abs_p = os.path.abspath(path)
    try:
        size = int(os.path.getsize(abs_p))
    except OSError:
        return {'path': '', 'size_bytes': 0, 'sha256': '', 'mtime': 0.0}
    h = hashlib.sha256()
    h.update(str(size).encode('ascii'))
    try:
        with open(abs_p, 'rb') as f:
            head = f.read(_SIGNATURE_CHUNK)
            h.update(head)
            if size > _SIGNATURE_CHUNK:
                f.seek(max(0, size - _SIGNATURE_CHUNK))
                h.update(f.read(_SIGNATURE_CHUNK))
    except OSError:
        return {'path': '', 'size_bytes': 0, 'sha256': '', 'mtime': 0.0}
    return {
        'path': abs_p,
        'size_bytes': size,
        'sha256': h.hexdigest(),
        'mtime': _file_mtime(abs_p),
    }


def source_meta(path: str | None, app_root: str) -> dict[str, Any]:
    if not path:
        return {'path': '', 'size_bytes': 0, 'sha256': '', 'mtime': 0.0}
    abs_p = os.path.abspath(path)
    root = os.path.abspath(app_root)
    sig = file_signature(abs_p)
    try:
        rel = os.path.relpath(abs_p, root)
        stored = rel if not rel.startswith('..') else abs_p
    except ValueError:
        stored = abs_p
    stored_path = stored.replace('\\', '/') if isinstance(stored, str) else stored
    return {
        'path': stored_path,
        'size_bytes': int(sig.get('size_bytes') or 0),
        'sha256': str(sig.get('sha256') or ''),
        'mtime': float(sig.get('mtime') or 0.0),
    }


def _source_actual(app_root: str, meta: dict[str, Any]) -> dict[str, Any]:
    rel = str(meta.get('path') or '').strip()
    abs_path = resolve_source_path(app_root, rel)
    sig = file_signature(abs_path) if rel else file_signature(None)
    return {
        'path': rel,
        'abs_path': abs_path,
        'exists': bool(rel and os.path.isfile(abs_path)),
        'size_bytes': int(sig.get('size_bytes') or 0),
        'sha256': str(sig.get('sha256') or ''),
        'mtime': float(sig.get('mtime') or 0.0),
    }


def _validate_v1_mtime(app_root: str, bundle: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    sources = bundle.get('sources') or {}
    details: dict[str, Any] = {'mode': 'mtime_v1', 'sources': {}}
    if not sources:
        return False, 'missing_sources', details
    for key, meta in sources.items():
        if not isinstance(meta, dict):
            return False, f'invalid_source_{key}', details
        recorded = meta.get('mtime')
        path = meta.get('path') or ''
        if recorded is None or not path:
            details['sources'][key] = {'ok': False, 'reason': 'missing_path_or_mtime', 'expected': meta}
            return False, f'source_{key}_incomplete', details
        abs_path = resolve_source_path(app_root, path)
        actual_mtime = _file_mtime(abs_path)
        ok = abs(float(recorded)) == actual_mtime and os.path.isfile(abs_path)
        details['sources'][key] = {
            'ok': ok,
            'expected_mtime': float(recorded),
            'actual_mtime': actual_mtime,
            'path': path,
            'exists': os.path.isfile(abs_path),
        }
        if not ok:
            return False, f'source_{key}_mtime_mismatch', details
    return True, 'ok', details


def _validate_v2_signature(app_root: str, bundle: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    sources = bundle.get('sources') or {}
    details: dict[str, Any] = {'mode': 'signature_v2', 'sources': {}}
    if not sources:
        return False, 'missing_sources', details
    for key, meta in sources.items():
        if not isinstance(meta, dict):
            return False, f'invalid_source_{key}', details
        path = str(meta.get('path') or '').strip()
        if not path:
            details['sources'][key] = {'ok': False, 'reason': 'missing_path', 'expected': meta}
            return False, f'source_{key}_missing_path', details
        expected_size = int(meta.get('size_bytes') or 0)
        expected_sha = str(meta.get('sha256') or '').strip()
        if not expected_size or not expected_sha:
            details['sources'][key] = {'ok': False, 'reason': 'missing_signature', 'expected': meta}
            return False, f'source_{key}_missing_signature', details
        actual = _source_actual(app_root, meta)
        ok = (
            actual['exists']
            and actual['size_bytes'] == expected_size
            and actual['sha256'] == expected_sha
        )
        details['sources'][key] = {
            'ok': ok,
            'expected': {
                'path': path,
                'size_bytes': expected_size,
                'sha256': expected_sha,
            },
            'actual': {
                'path': path,
                'size_bytes': actual['size_bytes'],
                'sha256': actual['sha256'],
                'mtime': actual['mtime'],
                'exists': actual['exists'],
            },
        }
        if not ok:
            reason = 'missing_file' if not actual['exists'] else 'signature_mismatch'
            return False, f'source_{key}_{reason}', details
    return True, 'ok', details


def validate_bundle_sources(app_root: str, bundle: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    version = bundle.get('version')
    if version == 1:
        return _validate_v1_mtime(app_root, bundle)
    if version == 2:
        return _validate_v2_signature(app_root, bundle)
    return False, f'unsupported_version_{version!r}', {'mode': 'unknown', 'version': version}


def bundle_sources_valid(app_root: str, bundle: dict[str, Any]) -> bool:
    ok, _reason, _details = validate_bundle_sources(app_root, bundle)
    return ok


def inspect_bundle_status(app_root: str) -> dict[str, Any]:
    """Diagnostics for /warmup and ops — never raises."""
    path = aggregates_path(app_root)
    out: dict[str, Any] = {
        'bundle_path': path.replace('\\', '/'),
        'bundle_exists': os.path.isfile(path),
        'bundle_bytes': os.path.getsize(path) if os.path.isfile(path) else 0,
        'bundle_version': None,
        'built_at': None,
        'canonical_quarter': None,
        'validation_ok': False,
        'validation_reason': 'bundle_missing',
        'validation_details': {},
        'live_fallback': True,
    }
    if not out['bundle_exists']:
        return out
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
    except Exception as e:
        out['validation_reason'] = 'bundle_load_error'
        out['validation_details'] = {'error': str(e)}
        return out
    if not isinstance(data, dict):
        out['validation_reason'] = 'bundle_not_object'
        return out
    out['bundle_version'] = data.get('version')
    out['built_at'] = data.get('built_at')
    out['canonical_quarter'] = data.get('canonical_quarter')
    ok, reason, details = validate_bundle_sources(app_root, data)
    out['validation_ok'] = ok
    out['validation_reason'] = reason
    out['validation_details'] = details
    out['live_fallback'] = not ok
    return out


def load_bundle(app_root: str) -> dict[str, Any] | None:
    status = inspect_bundle_status(app_root)
    if not status.get('bundle_exists'):
        print('[state_page_aggregates] bundle missing', flush=True)
        return None
    path = aggregates_path(app_root)
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
    if not isinstance(data, dict):
        return None
    if data.get('version') not in (1, 2):
        print(f'[state_page_aggregates] unsupported version {data.get("version")!r}', flush=True)
        return None
    ok, reason, details = validate_bundle_sources(app_root, data)
    if not ok:
        print(f'[state_page_aggregates] bundle rejected: {reason} {details}', flush=True)
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
