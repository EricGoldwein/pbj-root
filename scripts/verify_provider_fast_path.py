#!/usr/bin/env python3
"""Verify provider fast-path indexes: complete page, no full CSV scans on render."""
from __future__ import annotations

import concurrent.futures
import io
import os
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PBJ_PROVIDER_PAGE_CACHE_TTL', '900')
os.environ.setdefault('PBJ_PROVIDER_PERF_LOG', '1')

CCNS = ('676230', '035297')


def main() -> int:
    buf = io.StringIO()
    with redirect_stdout(buf):
        import app as m
        m.clear_provider_page_cache()
        client = m.app.test_client()
        log = []

        def run(label: str, path: str, *, clear: bool = False):
            if clear:
                m.clear_provider_page_cache()
            t0 = time.perf_counter()
            r = client.get(path, headers={'User-Agent': 'Mozilla/5.0'})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            log.append((label, r.status_code, ms, r.headers.get('X-PBJ-Provider-Cache', '-')))
            print(f'{label}: {r.status_code} {ms}ms cache={r.headers.get("X-PBJ-Provider-Cache")}')
            return r

        run('health', '/health')
        run('home', '/')
        r_cold = run('provider cold', f'/provider/{CCNS[0]}', clear=True)
        html = r_cold.get_data(as_text=True)
        run('provider hit', f'/provider/{CCNS[0]}')

        def cold_other(ccn: str):
            m.clear_provider_page_cache()
            t0 = time.perf_counter()
            r = client.get(f'/provider/{ccn}', headers={'User-Agent': 'Mozilla/5.0'})
            return ccn, r.status_code, r.headers.get('X-PBJ-Provider-Cache'), round((time.perf_counter() - t0) * 1000, 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(cold_other, c) for c in CCNS]
            concurrent_results = [f.result() for f in concurrent.futures.as_completed(futs)]
        print('concurrent:', concurrent_results)

    out = buf.getvalue()
    errors = []

    if 'entity_metrics_stream' in out:
        errors.append('entity_metrics_stream still logged during provider render')
    if out.count('facility_quarterly_stream_start') > 0:
        errors.append('facility_quarterly_stream_start still logged (expected sqlite lookup)')
    if (
        'provider_indexes_hydrated' not in out
        and 'facility_quarterly_lookup source=sqlite' not in out
        and out.count('facility_quarterly_stream_start') > 0
    ):
        errors.append('no artifact hydrate and CSV stream still used')

    checks = {
        'charts': 'pbj-chart-container' in html or 'pbj-chart-wrapper' in html,
        'state_percentile': 'percentile' in html.lower() or 'pbj-percentile' in html,
        'entity_summary': 'pbj-entity-summary' in html or 'pbj-details-entity' in html,
        'total_hprd': 'Total Nurse HPRD' in html or 'HPRD' in html,
        'reported_hprd_numeric': bool(
            re.search(r'reported\s+<strong>\d+\.\d+\s+HPRD</strong>', html, re.I)
        ),
        'no_na_narrative': 'reported <strong>N/A HPRD</strong>' not in html
            and 'reported <strong>N/A</strong>' not in html,
    }
    for name, ok in checks.items():
        print(f'content_{name}:', ok)
        if not ok:
            errors.append(f'missing critical marker: {name}')

    if errors:
        print('FAIL:', *errors, sep='\n  ')
        return 1
    print('OK: fast path verification passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
