#!/usr/bin/env python3
"""Log proof + performance checks for provider index fast path."""
from __future__ import annotations

import concurrent.futures
import io
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['PBJ_PROVIDER_COLD_BURST_LIMIT'] = '0'
os.environ['PBJ_PROVIDER_CRAWLER_COLD_LIMIT'] = '0'
os.environ.pop('RENDER', None)
# Match Render: local app.py defaults PBJ_SKIP_PROVIDER_PAGE_CACHE=1 off-Render.
os.environ['PBJ_SKIP_PROVIDER_PAGE_CACHE'] = '0'
os.environ.setdefault('PBJ_PROVIDER_PAGE_CACHE_TTL', '900')


def main() -> int:
    import app as m

    print('=== LOG PROOF (artifacts present) ===')
    m.clear_provider_page_cache()
    m._PROVIDER_INDEXES_HYDRATED = False
    buf = io.StringIO()
    with redirect_stdout(buf):
        c = m.app.test_client()
        c.get('/provider/676230')
        c.get('/provider/676230')
    out = buf.getvalue()
    events = [
        'provider_indexes_hydrated',
        'facility_quarterly_lookup',
        'provider_index_fallback',
        'entity_metrics_stream',
        'state_percentile_csv_rebuild',
    ]
    for ev in events:
        n = sum(1 for ln in out.splitlines() if f'"event":"{ev}"' in ln)
        print(f'{ev}: {n}')
    for ln in out.splitlines():
        if '"event":"provider_indexes_hydrated"' in ln or '"event":"facility_quarterly_lookup"' in ln:
            print('EXAMPLE', ln[:320])

    print('\n=== PERFORMANCE ===')
    c = m.app.test_client()
    t0 = time.perf_counter()
    c.get('/health')
    health_ms = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter()
    c.get('/')
    home_ms = round((time.perf_counter() - t0) * 1000, 1)
    m.clear_provider_page_cache()
    t0 = time.perf_counter()
    r1 = c.get('/provider/676230')
    cold_ms = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter()
    r2 = c.get('/provider/676230')
    hit_ms = round((time.perf_counter() - t0) * 1000, 1)
    hit_cache = r2.headers.get('X-PBJ-Provider-Cache')

    os.environ['PBJ_PROVIDER_COLD_SLOTS'] = '1'
    os.environ['PBJ_PROVIDER_COLD_WAIT'] = '60'
    m._PROVIDER_COLD_RENDER_SEM = None

    def cold(ccn):
        m.clear_provider_page_cache()
        t0 = time.perf_counter()
        r = m.app.test_client().get(f'/provider/{ccn}')
        return ccn, r.status_code, round((time.perf_counter() - t0) * 1000, 1)

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        conc = list(pool.map(cold, ['676230', '335003']))

    print(f'health_ms={health_ms} (target <100)')
    print(f'home_ms={home_ms} (target <500)')
    print(f'cold_ms={cold_ms} cache={r1.headers.get("X-PBJ-Provider-Cache")} (target <2000)')
    print(f'hit_ms={hit_ms} cache={hit_cache} (target <50)')
    print(f'concurrent={conc} (no 503)')

    ok = (
        health_ms < 100
        and home_ms < 500
        and cold_ms < 2000
        and r1.status_code == 200
        and hit_ms < 50
        and hit_cache == 'HIT'
        and all(s != 503 for _, s, _ in conc)
    )
    print('PERF', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
