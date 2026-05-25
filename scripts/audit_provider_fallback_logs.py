#!/usr/bin/env python3
"""Verify fallback logs when artifacts missing/stale; restore artifacts cleanly."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _body() -> int:
    sys.path.insert(0, str(ROOT))
    import facility_provider_indexes as fpi

    index_dir = Path(fpi.INDEX_DIR)
    if not index_dir.is_dir():
        print('FAIL: no index dir')
        return 1

    td = tempfile.mkdtemp(prefix='pbj_idx_audit_')
    moved = []
    for name in (
        'facility_quarterly_provider.sqlite',
        'meta.json',
        'state_percentile_hprd.pkl',
        'state_contract_median.pkl',
    ):
        src = index_dir / name
        if src.is_file():
            dst = Path(td) / name
            fpi.close_sqlite()
            fpi._META_CACHE = None
            os.replace(src, dst)
            moved.append((src, dst))

    buf = io.StringIO()
    with redirect_stdout(buf):
        import app as m

        m._PROVIDER_INDEXES_HYDRATED = False
        m._STATE_PERCENTILE_HPRD_INDEX_CACHE = None
        m._STATE_CONTRACT_MEDIAN_CACHE = None
        m._load_facility_quarterly_for_provider_cached.cache_clear()
        r = m.app.test_client().get('/provider/676230')
        h = m.app.test_client().get('/health')
    out = buf.getvalue()
    fb = out.count('"event":"provider_index_fallback"')
    print('MISSING_ARTIFACTS')
    print('status', r.status_code, 'health', h.status_code)
    print('fallback_events', fb)
    for ln in out.splitlines():
        if 'provider_index_fallback' in ln:
            print('LOG', ln[:280])
            break

    for src, dst in moved:
        fpi.close_sqlite()
        os.replace(dst, src)
    fpi._META_CACHE = None

    meta_path = index_dir / 'meta.json'
    ok_stale = True
    if meta_path.is_file():
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)
        real_mtime = meta.get('source_mtime')
        meta['source_mtime'] = 1
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        fpi._META_CACHE = None

        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            import app as m

            m._PROVIDER_INDEXES_HYDRATED = False
            m._load_facility_quarterly_for_provider_cached.cache_clear()
            r2 = m.app.test_client().get('/provider/335003')
        out2 = buf2.getvalue()
        fb2 = out2.count('"event":"provider_index_fallback"')
        print('STALE_META')
        print('status', r2.status_code)
        print('fallback_events', fb2)
        for ln in out2.splitlines():
            if 'provider_index_fallback' in ln:
                print('LOG', ln[:280])
                break
        meta['source_mtime'] = real_mtime
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        fpi._META_CACHE = None
        ok_stale = fb2 >= 1 and r2.status_code == 200

    leftover = list(index_dir.glob('*.bak*'))
    print('leftover_bak_files', leftover)
    ok = (
        fb >= 1
        and r.status_code == 200
        and h.status_code == 200
        and ok_stale
        and not leftover
    )
    print('RESULT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main() -> int:
    if os.environ.get('PBJ_FALLBACK_AUDIT_CHILD') == '1':
        return _body()
    env = os.environ.copy()
    env['PBJ_FALLBACK_AUDIT_CHILD'] = '1'
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'audit_provider_fallback_logs.py')],
        cwd=str(ROOT),
        env=env,
    )
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
