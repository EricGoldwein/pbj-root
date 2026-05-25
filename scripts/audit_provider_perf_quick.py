#!/usr/bin/env python3
"""Quick perf thresholds (PowerShell-safe script file)."""
from __future__ import annotations

import concurrent.futures
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ['PBJ_PROVIDER_COLD_BURST_LIMIT'] = '0'
os.environ['PBJ_PROVIDER_CRAWLER_COLD_LIMIT'] = '0'
os.environ.pop('RENDER', None)


def main() -> int:
    import app as m

    c = m.app.test_client()
    t0 = time.perf_counter()
    c.get('/health')
    health_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    c.get('/')
    home_ms = (time.perf_counter() - t0) * 1000
    m.clear_provider_page_cache()
    t0 = time.perf_counter()
    r = c.get('/provider/676230')
    cold_ms = (time.perf_counter() - t0) * 1000
    cold_cache = r.headers.get('X-PBJ-Provider-Cache')
    t0 = time.perf_counter()
    r2 = c.get('/provider/676230')
    hit_ms = (time.perf_counter() - t0) * 1000
    hit_cache = r2.headers.get('X-PBJ-Provider-Cache')

    os.environ['PBJ_PROVIDER_COLD_SLOTS'] = '1'
    os.environ['PBJ_PROVIDER_COLD_WAIT'] = '60'
    m._PROVIDER_COLD_RENDER_SEM = None

    def cold(ccn):
        m.clear_provider_page_cache()
        t0 = time.perf_counter()
        resp = m.app.test_client().get(f'/provider/{ccn}')
        return resp.status_code, round((time.perf_counter() - t0) * 1000, 1)

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        a, b = pool.map(cold, ('676230', '335003'))

    rows = [
        ('health', health_ms, 100, health_ms < 100),
        ('home', home_ms, 500, home_ms < 500),
        ('cold', cold_ms, 2000, cold_ms < 2000 and cold_cache == 'MISS'),
        ('hit', hit_ms, 50, hit_ms < 50 and hit_cache == 'HIT'),
        ('concurrent', 0, 0, a[0] != 503 and b[0] != 503),
    ]
    print('PERF')
    for name, ms, thr, ok in rows:
        print(f'{name} {ms:.1f}ms thr={thr} pass={ok}')
    print(f'concurrent {a} {b}')
    return 0 if all(r[3] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
