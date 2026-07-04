#!/usr/bin/env python3
"""Audit 4 only: missing/stale artifacts in isolated subprocess."""
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _run_missing():
    import facility_provider_indexes as fpi

    sqlite = fpi.SQLITE_PATH
    meta = fpi.META_PATH
    for p in (sqlite, meta, fpi.PERCENTILE_PKL, fpi.CONTRACT_PKL):
        if os.path.isfile(p):
            os.rename(p, p + '.bak_sub')
    fpi._META_CACHE = None
    fpi._SQLITE_CONN = None
    buf = io.StringIO()
    with redirect_stdout(buf):
        import app as m

        m._PROVIDER_INDEXES_HYDRATED = False
        m._load_facility_quarterly_for_provider_cached.cache_clear()
        c = m.app.test_client()
        r = c.get('/provider/676230')
        h = c.get('/health')
    out = buf.getvalue()
    print('MISSING_ARTIFACTS')
    print('provider_status', r.status_code)
    print('health_status', h.status_code)
    print('stream_starts', out.count('facility_quarterly_stream_start'))
    print('hydrate_events', out.count('provider_indexes_hydrated'))
    for p in (sqlite, meta, fpi.PERCENTILE_PKL, fpi.CONTRACT_PKL):
        bak = p + '.bak_sub'
        if os.path.isfile(bak):
            os.rename(bak, p)


def _run_stale():
    import facility_provider_indexes as fpi

    meta = fpi.META_PATH
    if not os.path.isfile(meta):
        print('STALE_SKIP no meta')
        return
    with open(meta, encoding='utf-8') as f:
        obj = json.load(f)
    real_mtime = obj.get('source_mtime')
    obj['source_mtime'] = 1
    with open(meta, 'w', encoding='utf-8') as f:
        json.dump(obj, f)
    fpi._META_CACHE = None
    buf = io.StringIO()
    with redirect_stdout(buf):
        import app as m

        m._PROVIDER_INDEXES_HYDRATED = False
        m._load_facility_quarterly_for_provider_cached.cache_clear()
        r = m.app.test_client().get('/provider/335003')
    out = buf.getvalue()
    print('STALE_META')
    print('provider_status', r.status_code)
    print('stream_starts', out.count('facility_quarterly_stream_start'))
    print('sqlite_lookup', out.count('facility_quarterly_lookup source=sqlite'))
    if real_mtime is not None:
        obj['source_mtime'] = real_mtime
        with open(meta, 'w', encoding='utf-8') as f:
            json.dump(obj, f)


if __name__ == '__main__':
    _run_missing()
    _run_stale()
