#!/usr/bin/env python3
"""Pre-commit checks: provider HTML parity, entity HPRD paths, health, smoke timings."""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PBJ_SKIP_PROVIDER_PAGE_CACHE', '0')
os.environ.setdefault('PBJ_PROVIDER_PAGE_CACHE_TTL', '900')

CCNS = ('676230', '035297')


def _rss_mb() -> float | None:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def _extract_markers(html: str) -> dict[str, str]:
    text = html.decode('utf-8', errors='replace') if isinstance(html, bytes) else html
    out: dict[str, str] = {}

    m = re.search(r'<title[^>]*>([^<]+)</title>', text, re.I)
    out['title'] = (m.group(1).strip() if m else '')

    for pat, key in (
        (r'data-latest-quarter=["\']([^"\']+)', 'latest_quarter'),
        (r'data-provnum=["\']([^"\']+)', 'provnum'),
        (r'data-total-nurse-hprd=["\']([^"\']+)', 'total_nurse_hprd'),
        (r'data-state-percentile=["\']([^"\']+)', 'state_percentile'),
        (r'pbj-entity-summary[^>]*>([^<]{20,200})<', 'entity_summary'),
        (r'id="pbj-chart-data"[^>]*>(\{.*?\})</script>', 'chart_data_snip'),
    ):
        mm = re.search(pat, text, re.I | re.S)
        if mm:
            out[key] = mm.group(1).strip()[:240]

    m = re.search(r'pbj-details-entity[^>]*>[\s\S]{0,4000}?</div>', text, re.I)
    if m:
        block = re.sub(r'\s+', ' ', m.group(0))[:400]
        out['entity_block_snip'] = block

    m = re.search(r'Total Nurse HPRD[^<]{0,80}<[^>]+>([^<]+)', text, re.I)
    if m:
        out['display_total_hprd'] = m.group(1).strip()

    return out


def _load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _render_ccns(mod) -> dict[str, dict[str, str]]:
    mod.clear_provider_page_cache()
    client = mod.app.test_client()
    out = {}
    for ccn in CCNS:
        r = client.get(f'/provider/{ccn}')
        out[ccn] = {
            'status': r.status_code,
            'cache': r.headers.get('X-PBJ-Provider-Cache'),
            'markers': _extract_markers(r.get_data()),
        }
    return out


def _compare_entity_hprd_paths(mod) -> tuple[bool, str]:
    """Stream path vs national index for one entity roster."""
    pd = mod.get_pd()
    if pd is None:
        return False, 'pandas unavailable'
    latest_q = mod.get_canonical_latest_quarter() or ''
    path, _mtime, index, _names = mod._get_entity_facilities_index()
    if not path or not index:
        return False, 'entity index empty'
    eid = next(iter(index))
    facilities = list(index[eid].values())[:40]
    ccn_list = [f['ccn'] for f in facilities]

    stream_rows = mod._stream_facility_quarterly_latest_for_ccns(ccn_list, latest_q)
    stream_metrics = {}
    for fac in facilities:
        row = stream_rows.get(fac['ccn'])
        if row is None:
            continue
        d = {}
        mod._apply_facility_quarterly_metrics_row(d, row, latest_q)
        stream_metrics[fac['ccn']] = {
            'Total_Nurse_HPRD': d.get('Total_Nurse_HPRD'),
            'RN_HPRD': d.get('RN_HPRD'),
            'Contract_Percentage': d.get('Contract_Percentage'),
            'avg_daily_census': d.get('avg_daily_census'),
        }

    national = mod._facility_latest_hprd_by_ccn_for_quarter(latest_q)
    mismatches = []
    for ccn, sm in stream_metrics.items():
        nm = national.get(ccn) or {}
        for k in ('Total_Nurse_HPRD', 'RN_HPRD', 'Contract_Percentage', 'avg_daily_census'):
            sv, nv = sm.get(k), nm.get(k)
            if pd.isna(sv) if isinstance(sv, float) else False:
                sv = None
            if pd.isna(nv) if isinstance(nv, float) else False:
                nv = None
            if sv != nv and not (sv is None and nv is None):
                mismatches.append((ccn, k, sv, nv))
    if mismatches:
        return False, f'mismatches={mismatches[:5]}'
    return True, f'compared {len(stream_metrics)} ccns for entity {eid}'


def _health_no_pandas(mod) -> tuple[bool, str]:
    before_pd = mod.pd
    mod.pd = None
    try:
        client = mod.app.test_client()
        t0 = time.perf_counter()
        r = client.get('/health')
        ms = round((time.perf_counter() - t0) * 1000, 2)
        ok = r.status_code == 200 and r.data == b'ok' and ms < 50
        return ok, f'status={r.status_code} ms={ms} data={r.data!r}'
    finally:
        mod.pd = before_pd


def _smoke(mod) -> list[str]:
    lines = []
    client = mod.app.test_client()
    t0 = time.perf_counter()
    r = client.get('/health')
    lines.append(f'/health status={r.status_code} ms={round((time.perf_counter()-t0)*1000,1)} rss={_rss_mb()}MB')
    for ccn in CCNS:
        mod.clear_provider_page_cache()
        t0 = time.perf_counter()
        r1 = client.get(f'/provider/{ccn}')
        cold_ms = round((time.perf_counter() - t0) * 1000, 1)
        t0 = time.perf_counter()
        r2 = client.get(f'/provider/{ccn}')
        hit_ms = round((time.perf_counter() - t0) * 1000, 1)
        lines.append(
            f'cold /provider/{ccn} status={r1.status_code} cache={r1.headers.get("X-PBJ-Provider-Cache")} '
            f'ms={cold_ms} len={len(r1.data)}'
        )
        lines.append(
            f'hit  /provider/{ccn} status={r2.status_code} cache={r2.headers.get("X-PBJ-Provider-Cache")} '
            f'ms={hit_ms}'
        )
    lines.append(f'final rss={_rss_mb()}MB')
    return lines


def main() -> int:
    head_py = ROOT / 'app_head_snapshot.py'
    with head_py.open('w', encoding='utf-8') as fh:
        subprocess.run(
            ['git', 'show', 'HEAD:app.py'],
            cwd=ROOT,
            check=True,
            stdout=fh,
        )

    # Fresh imports
    for name in list(sys.modules):
        if name == 'app' or name.startswith('app_'):
            del sys.modules[name]

    new_mod = _load_module_from_path(ROOT / 'app.py', 'app_new')
    old_mod = _load_module_from_path(head_py, 'app_old')

    ok_health, health_detail = _health_no_pandas(new_mod)
    print(f'health independent: {ok_health} ({health_detail})')

    ok_hprd, hprd_detail = _compare_entity_hprd_paths(new_mod)
    print(f'entity HPRD parity: {ok_hprd} ({hprd_detail})')

    before = _render_ccns(old_mod)
    for name in list(sys.modules):
        if name.startswith('app_'):
            del sys.modules[name]
    new_mod = _load_module_from_path(ROOT / 'app.py', 'app_new2')
    after = _render_ccns(new_mod)

    print('\nHTML marker comparison (HEAD vs working tree):')
    all_ok = True
    for ccn in CCNS:
        b, a = before[ccn]['markers'], after[ccn]['markers']
        keys = sorted(set(b) | set(a))
        print(f'  CCN {ccn}: status {before[ccn]["status"]}->{after[ccn]["status"]}')
        for k in keys:
            if b.get(k) != a.get(k):
                all_ok = False
                print(f'    DIFF {k}:')
                print(f'      before: {b.get(k)!r}')
                print(f'      after:  {a.get(k)!r}')
        if all(m == b.get(m) == a.get(m) for m in keys if m in b and m in a):
            print(f'    all {len(keys)} markers match')

    print('\nSmoke (new code):')
    smoke = _smoke(new_mod)
    for line in smoke:
        print(line)

    head_py.unlink(missing_ok=True)
    if not ok_health or not ok_hprd:
        return 1
    if not all_ok:
        print('\nWARNING: HTML marker diffs detected — inspect manually.')
        return 1
    print('\nAll automated checks passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
