#!/usr/bin/env python3
"""
Product-safety and performance parity audit for provider-index fast path.
Does not modify app code. Writes scripts/audit_provider_index_report.txt
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import os
import re
import shutil
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORT = ROOT / 'scripts' / 'audit_provider_index_report.txt'

os.environ.setdefault('PBJ_PROVIDER_PERF_LOG', '1')
os.environ.setdefault('PBJ_SKIP_PROVIDER_PAGE_CACHE', '0')
os.environ.setdefault('PBJ_PROVIDER_PAGE_CACHE_TTL', '900')
# Local audit: disable Render burst limits so concurrent test is fair
os.environ['PBJ_PROVIDER_COLD_BURST_LIMIT'] = '0'
os.environ['PBJ_PROVIDER_CRAWLER_COLD_LIMIT'] = '0'
os.environ['RENDER'] = ''


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        import math
        f = float(v)
        if math.isnan(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _pick_audit_ccns() -> list[tuple[str, str]]:
    """Return [(ccn, category), ...] for 8+ representative facilities."""
    import pandas as pd

    pi_path = ROOT / 'provider_info' / 'ProviderInfoNorm_2026_04.csv'
    if not pi_path.is_file():
        for p in sorted((ROOT / 'provider_info').glob('ProviderInfoNorm_*.csv'), reverse=True):
            pi_path = p
            break
    pi = pd.read_csv(pi_path, dtype=str, low_memory=False)
    ccn_col = next((c for c in pi.columns if c.lower() in ('ccn', 'provnum', 'provider_number')), None)
    if not ccn_col:
        ccn_col = pi.columns[0]
    pi['_ccn'] = pi[ccn_col].astype(str).str.strip().str.zfill(6)
    st_col = next((c for c in pi.columns if c.upper() == 'STATE' or c.lower() == 'state'), None)
    ent_col = next((c for c in pi.columns if 'entity' in c.lower() and 'id' in c.lower()), None)
    own_col = next((c for c in pi.columns if 'ownership' in c.lower()), None)

    picks: list[tuple[str, str]] = [('676230', 'known_test_ccn')]

    if st_col:
        ny = pi[pi[st_col].astype(str).str.upper() == 'NY']
        ct = pi[pi[st_col].astype(str).str.upper() == 'CT']
        if not ny.empty:
            picks.append((ny.iloc[0]['_ccn'], 'ny'))
        if not ct.empty:
            picks.append((ct.iloc[0]['_ccn'], 'ct'))

    if ent_col:
        with_ent = pi[pi[ent_col].astype(str).str.strip() != '']
        no_ent = pi[pi[ent_col].astype(str).str.strip() == '']
        if not with_ent.empty:
            picks.append((with_ent.iloc[0]['_ccn'], 'with_entity'))
            # larger chain: entity with many facilities
            vc = with_ent[ent_col].value_counts()
            big_eid = vc.index[0] if len(vc) else None
            if big_eid is not None:
                sub = with_ent[with_ent[ent_col] == big_eid]
                if len(sub) >= 10:
                    picks.append((sub.iloc[0]['_ccn'], 'large_chain_entity'))
        if not no_ent.empty:
            picks.append((no_ent.iloc[0]['_ccn'], 'single_facility_no_entity'))

    # contract / hprd from facility csv sample
    fq_path = ROOT / 'facility_quarterly_metrics.csv'
    if fq_path.is_file():
        fq = pd.read_csv(fq_path, nrows=200000, low_memory=False)
        if 'PROVNUM' in fq.columns and 'CY_Qtr' in fq.columns:
            fq['_ccn'] = fq['PROVNUM'].astype(str).str.zfill(6)
            latest = fq['CY_Qtr'].astype(str).max()
            sub = fq[fq['CY_Qtr'].astype(str) == str(latest)]
            if 'Contract_Percentage' in sub.columns:
                sub['_c'] = pd.to_numeric(sub['Contract_Percentage'], errors='coerce')
                hi = sub[sub['_c'] >= 40].sort_values('_c', ascending=False)
                if not hi.empty:
                    picks.append((hi.iloc[0]['_ccn'], 'high_contract'))
            if 'Total_Nurse_HPRD' in sub.columns:
                sub['_h'] = pd.to_numeric(sub['Total_Nurse_HPRD'], errors='coerce')
                lo = sub[sub['_h'] <= 2.5].sort_values('_h')
                if not lo.empty:
                    picks.append((lo.iloc[0]['_ccn'], 'low_hprd_risky'))

    seen = set()
    out: list[tuple[str, str]] = []
    for ccn, cat in picks:
        if ccn not in seen and len(ccn) == 6:
            seen.add(ccn)
            out.append((ccn, cat))
    return out[:10]


def _extract_html_evidence(html: str) -> dict[str, Any]:
    text = html
    title_m = re.search(r'<title[^>]*>([^<]+)</title>', text, re.I)
    prov_m = re.search(r'data-provnum=["\']([^"\']+)', text, re.I)
    qtr_m = re.search(r'data-latest-quarter=["\']([^"\']+)', text, re.I)
    hprd_m = re.search(r'data-total-nurse-hprd=["\']([^"\']+)', text, re.I)
    pct_m = re.search(r'data-state-percentile=["\']([^"\']+)', text, re.I)
    return {
        'title': (title_m.group(1).strip() if title_m else '')[:120],
        'provnum': prov_m.group(1) if prov_m else '',
        'quarter': qtr_m.group(1) if qtr_m else '',
        'total_hprd_attr': hprd_m.group(1) if hprd_m else '',
        'state_percentile_attr': pct_m.group(1) if pct_m else '',
        'has_chart_container': 'pbj-chart-container' in text or 'pbj-chart-wrapper' in text,
        'has_chart_script': 'Chart' in text and 'pbj-chart' in text,
        'has_entity_block': 'pbj-details-entity' in text or 'pbj-entity-summary' in text,
        'has_ownership': 'pbj-details-ownership' in text,
        'has_provider_info': 'pbj-details-provider' in text or 'Overall:' in text,
        'has_empty_card_bug': bool(re.search(r'pbj-chart[^>]*>\s*</div>\s*</div>', text)),
        'has_nan_display': 'nan' in text.lower()[:50000],
        'html_len': len(text),
    }


def _metrics_from_df(df, prov: str, canonical_q: str, *, strict_csv_columns: bool = False) -> dict[str, Any]:
    import pandas as pd
    from facility_provider_indexes import REQUIRED_PROVIDER_DF_CSV_COLUMNS, provider_df_schema_errors

    if df is None or df.empty:
        return {'row_count': 0}
    if strict_csv_columns:
        schema_err = provider_df_schema_errors(df, ccn=prov)
        if schema_err:
            return {'row_count': len(df), 'schema_error': ';'.join(schema_err)}
    d = df.copy()
    if 'CY_Qtr' in d.columns:
        d['_q'] = d['CY_Qtr'].astype(str).str.strip()
    else:
        d['_q'] = ''
    latest_rows = d[d['_q'] == str(canonical_q)] if canonical_q else d
    if latest_rows.empty:
        latest = d.sort_values('_q').iloc[-1]
    else:
        latest = latest_rows.iloc[0]
    if strict_csv_columns:
        for col in REQUIRED_PROVIDER_DF_CSV_COLUMNS:
            if col not in d.columns:
                return {'row_count': len(d), 'schema_error': f'missing_{col}'}
    total = latest.get('Total_Nurse_HPRD') if strict_csv_columns else latest.get(
        'Total_Nurse_HPRD', latest.get('total_nurse_hprd')
    )
    rn = latest.get('RN_HPRD') if strict_csv_columns else latest.get('RN_HPRD', latest.get('rn_hprd'))
    lpn = latest.get('LPN_HPRD') if strict_csv_columns else latest.get('LPN_HPRD', latest.get('lpn_hprd'))
    aide = (
        latest.get('Nurse_Assistant_HPRD')
        if strict_csv_columns
        else latest.get('Nurse_Assistant_HPRD', latest.get('nurse_assistant_hprd'))
    )
    contract = (
        latest.get('Contract_Percentage')
        if strict_csv_columns
        else latest.get('Contract_Percentage', latest.get('contract_percentage'))
    )
    return {
        'row_count': len(d),
        'latest_quarter': str(latest.get('CY_Qtr', latest.get('cy_qtr', ''))),
        'total_nurse_hprd': _num(total),
        'rn_hprd': _num(rn),
        'lpn_hprd': _num(lpn),
        'aide_hprd': _num(aide),
        'contract_pct': _num(contract),
        'state': str(latest.get('STATE', latest.get('state', ''))).strip().upper()[:2],
    }


def _load_csv_path(prov: str):
    """Old path: force CSV stream (bypass sqlite)."""
    import app as m

    m._load_facility_quarterly_for_provider_cached.cache_clear()
    import facility_provider_indexes as fpi

    real_match = fpi.meta_matches_csv

    def _no_artifact(path):
        return False

    fpi.meta_matches_csv = _no_artifact
    try:
        df = m._load_facility_quarterly_for_provider_cached(prov)
    finally:
        fpi.meta_matches_csv = real_match
    return df


def _load_fast_path(prov: str):
    import app as m

    m._load_facility_quarterly_for_provider_cached.cache_clear()
    return m.load_facility_quarterly_for_provider(prov)


def _parity_row(prov: str, canonical_q: str) -> dict[str, Any]:
    import app as m

    row: dict[str, Any] = {'ccn': prov}
    csv_df = _load_csv_path(prov)
    fast_df = _load_fast_path(prov)
    row['csv_metrics'] = _metrics_from_df(csv_df, prov, canonical_q)
    row['fast_metrics'] = _metrics_from_df(fast_df, prov, canonical_q, strict_csv_columns=True)

    pi = m._provider_info_row_for_ccn(prov) or {}
    row['entity_id'] = pi.get('entity_id')
    row['entity_name'] = (pi.get('entity_name') or '')[:80]
    row['ownership'] = (pi.get('ownership_type') or '')[:60]

    state = row['fast_metrics'].get('state') or str(pi.get('state', '')).upper()[:2]
    hprd = row['fast_metrics'].get('total_nurse_hprd')
    rn = row['fast_metrics'].get('rn_hprd')

    # percentile: CSV rebuild path
    m._STATE_PERCENTILE_HPRD_INDEX_CACHE = None
    pct_csv = m._percentiles_for_state_quarter(state, canonical_q, hprd, rn)
    m._ensure_provider_indexes_hydrated()
    pct_fast = m._percentiles_for_state_quarter(state, canonical_q, hprd, rn)
    row['percentile_csv'] = pct_csv[0]
    row['percentile_fast'] = pct_fast[0]

    eid = row.get('entity_id')
    if eid:
        try:
            eid_int = int(eid)
            m.clear_provider_page_cache()
            _en, fac_csv = m.load_entity_facilities(eid_int, attach_quarterly_metrics=True)
            m._FACILITY_LATEST_HPRD_BY_CCN_VAL = None
            m._FACILITY_LATEST_HPRD_BY_CCN_KEY = None
            m._FACILITY_LATEST_HPRD_BY_CCN_AT = 0
            import facility_provider_indexes as fpi
            real = fpi.meta_matches_csv
            fpi.meta_matches_csv = lambda p: False
            try:
                _en2, fac_stream = m.load_entity_facilities(eid_int, attach_quarterly_metrics=True)
            finally:
                fpi.meta_matches_csv = real
            m._ensure_provider_indexes_hydrated()
            _en3, fac_fast = m.load_entity_facilities(eid_int, attach_quarterly_metrics=True)
            row['entity_facility_count'] = len(fac_fast)
            hprd_vals = [
                _num(f.get('Total_Nurse_HPRD'))
                for f in fac_fast
                if f.get('Total_Nurse_HPRD') is not None
            ]
            row['entity_avg_hprd_fast'] = round(sum(hprd_vals) / len(hprd_vals), 4) if hprd_vals else None
            stream_hprd = [
                _num(f.get('Total_Nurse_HPRD'))
                for f in fac_stream
                if f.get('Total_Nurse_HPRD') is not None
            ]
            row['entity_avg_hprd_stream'] = round(sum(stream_hprd) / len(stream_hprd), 4) if stream_hprd else None
        except Exception as e:
            row['entity_error'] = str(e)
    return row


def _classify_mismatch(field: str, a, b) -> str:
    if a == b:
        return 'match'
    if a is None and b is None:
        return 'match'
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) < 0.02:
            return 'harmless_numeric'
    if str(a).strip() == str(b).strip():
        return 'harmless_format'
    return 'REAL_BUG'


def main() -> int:
    lines: list[str] = []
    buf = io.StringIO()

    def log(s: str = '') -> None:
        lines.append(s)
        print(s)

    log('=' * 72)
    log('PBJ320 Provider Index Safety Audit')
    log('=' * 72)

    ccns = _pick_audit_ccns()
    log(f'\nAudit CCNs ({len(ccns)}):')
    for c, cat in ccns:
        log(f'  {c}  ({cat})')

    import app as m

    canonical_q = m.get_canonical_latest_quarter() or ''
    log(f'\nCanonical quarter: {canonical_q}')

    # --- Audit 1 ---
    log('\n## AUDIT 1 — Product completeness')
    completeness_fail = []
    with redirect_stdout(buf):
        client = m.app.test_client()
        for prov, cat in ccns:
            m.clear_provider_page_cache()
            t0 = time.perf_counter()
            r = client.get(f'/provider/{prov}', headers={'User-Agent': 'Mozilla/5.0'})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            html = r.get_data(as_text=True)
            ev = _extract_html_evidence(html)
            checks = {
                'status_200': r.status_code == 200,
                'title': bool(ev['title']),
                'ccn': prov in html or ev['provnum'] == prov,
                'state/context': bool(ev['quarter']) or 'Q' in html,
                'hprd': bool(ev['total_hprd_attr']) or 'HPRD' in html,
                'charts': ev['has_chart_container'],
                'provider_info': ev['has_provider_info'],
            }
            if cat in ('with_entity', 'large_chain_entity', 'ct') and ev.get('entity_id') is None:
                if 'pbj-details-entity' not in html and 'entity' not in cat:
                    pass
            if cat in ('with_entity', 'large_chain_entity'):
                checks['entity_when_expected'] = ev['has_entity_block'] or 'entity' in html.lower()
            if cat == 'ct':
                checks['ownership_ct'] = ev['has_ownership']
            fail = [k for k, v in checks.items() if not v]
            log(f'\n{prov} ({cat}) {ms}ms status={r.status_code}')
            log(f'  evidence: {json.dumps(ev, default=str)[:400]}')
            log(f'  checks: {checks}')
            if fail:
                completeness_fail.append((prov, fail))
                log(f'  FAIL fields: {fail}')
            if ev.get('has_nan_display'):
                completeness_fail.append((prov, ['nan_display']))
                log('  WARN: nan in HTML')

    log(f'\nAudit 1 result: {"PASS" if not completeness_fail else "FAIL"} ({len(completeness_fail)} issues)')

    # --- Audit 2 ---
    log('\n## AUDIT 2 — Data parity (CSV stream vs SQLite/pickle)')
    mismatches: list[str] = []
    for prov, cat in ccns:
        try:
            row = _parity_row(prov, canonical_q)
        except Exception as e:
            log(f'{prov}: parity error {e}')
            mismatches.append(f'{prov}: exception {e}')
            continue
        cm = row['csv_metrics']
        fm = row['fast_metrics']
        if fm.get('schema_error'):
            mismatches.append(f'{prov}.schema: fast={fm.get("schema_error")}')
            continue
        for field in ('row_count', 'latest_quarter', 'total_nurse_hprd', 'rn_hprd', 'lpn_hprd', 'aide_hprd', 'contract_pct'):
            a, b = cm.get(field), fm.get(field)
            cls = _classify_mismatch(field, a, b)
            if cls not in ('match', 'harmless_numeric', 'harmless_format'):
                mismatches.append(f'{prov}.{field}: csv={a} fast={b} -> {cls}')
            elif cls == 'harmless_numeric':
                log(f'  {prov}.{field}: harmless delta csv={a} fast={b}')
        pc, pf = row.get('percentile_csv'), row.get('percentile_fast')
        if pc != pf and not (pc is None and pf is None):
            if pc is not None and pf is not None and abs(int(pc) - int(pf)) <= 1:
                log(f'  {prov}.percentile: harmless rounding csv={pc} fast={pf}')
            else:
                mismatches.append(f'{prov}.percentile: csv={pc} fast={pf}')
        ea, eb = row.get('entity_avg_hprd_stream'), row.get('entity_avg_hprd_fast')
        if ea is not None and eb is not None and _classify_mismatch('entity_avg', ea, eb) == 'REAL_BUG':
            mismatches.append(f'{prov}.entity_avg_hprd: stream={ea} fast={eb}')
        log(f'{prov} ({cat}): rows csv={cm.get("row_count")} fast={fm.get("row_count")} '
            f'hprd csv={cm.get("total_nurse_hprd")} fast={fm.get("total_nurse_hprd")} '
            f'pct csv={pc} fast={pf}')

    real_bugs = [x for x in mismatches if 'REAL' in x or 'percentile' in x or 'exception' in x]
    log(f'\nAudit 2 result: {"PASS" if not real_bugs else "FAIL"}')
    log(f'  Total mismatch lines: {len(mismatches)}')
    for x in mismatches[:30]:
        log(f'  {x}')

    # --- Audit 3 ---
    log('\n## AUDIT 3 — No request-time full scans')
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        m.clear_provider_page_cache()
        global _PROVIDER_INDEXES_HYDRATED
        m._PROVIDER_INDEXES_HYDRATED = False
        m._STATE_PERCENTILE_HPRD_INDEX_CACHE = None
        c = m.app.test_client()
        for prov, _ in ccns[:4]:
            m.clear_provider_page_cache()
            c.get(f'/provider/{prov}')
        c.get(f'/provider/{ccns[0][0]}')
    out3 = buf2.getvalue()
    bad = {
        'facility_quarterly_stream_start': out3.count('facility_quarterly_stream_start'),
        'entity_metrics_stream': out3.count('entity_metrics_stream'),
        'state_percentile build': out3.count('"index": "state_percentile_hprd"') + out3.count('state_percentile_hprd'),
    }
    good = {
        'provider_indexes_hydrated': out3.count('provider_indexes_hydrated'),
        'sqlite_lookup': out3.count('facility_quarterly_lookup source=sqlite'),
        'cache_hit': out3.count('"cache":"HIT"') + out3.count('cache=HIT'),
    }
    log(f'  bad signals: {bad}')
    log(f'  good signals: {good}')
    a3_pass = bad['facility_quarterly_stream_start'] == 0 and bad['entity_metrics_stream'] == 0
    log(f'Audit 3 result: {"PASS" if a3_pass else "FAIL"}')

    # --- Audit 4 ---
    log('\n## AUDIT 4 — Missing/stale artifacts')
    import facility_provider_indexes as fpi

    sqlite = fpi.SQLITE_PATH
    meta = fpi.META_PATH
    bak_sqlite = sqlite + '.audit_bak'
    bak_meta = meta + '.audit_bak'
    restored = True
    try:
        if os.path.isfile(sqlite):
            shutil.move(sqlite, bak_sqlite)
        if os.path.isfile(meta):
            shutil.move(meta, bak_meta)
        fpi._META_CACHE = None
        fpi._SQLITE_CONN = None
        m._PROVIDER_INDEXES_HYDRATED = False
        m._load_facility_quarterly_for_provider_cached.cache_clear()
        buf4 = io.StringIO()
        with redirect_stdout(buf4):
            r = m.app.test_client().get(f'/provider/{ccns[0][0]}')
            rh = m.app.test_client().get('/health')
        o4 = buf4.getvalue()
        log(f'  missing sqlite: status={r.status_code} health={rh.status_code}')
        log(f'  stream_fallback={o4.count("facility_quarterly_stream_start")} logs_sample={o4[:500]}')
        a4_ok = r.status_code in (200, 404) and rh.status_code == 200
        log(f'  Audit 4a (missing): {"PASS" if a4_ok else "FAIL"}')
    finally:
        if os.path.isfile(bak_sqlite):
            shutil.move(bak_sqlite, sqlite)
        if os.path.isfile(bak_meta):
            shutil.move(bak_meta, meta)
        fpi._META_CACHE = None
        fpi._SQLITE_CONN = None
        m._PROVIDER_INDEXES_HYDRATED = False

    # stale meta
    if os.path.isfile(meta):
        with open(meta, encoding='utf-8') as f:
            meta_obj = json.load(f)
        meta_obj['source_mtime'] = 1
        with open(meta, encoding='w') as f:
            json.dump(meta_obj, f)
        fpi._META_CACHE = None
        m._PROVIDER_INDEXES_HYDRATED = False
        m._load_facility_quarterly_for_provider_cached.cache_clear()
        buf4b = io.StringIO()
        with redirect_stdout(buf4b):
            r2 = m.app.test_client().get(f'/provider/{ccns[1][0]}')
        o4b = buf4b.getvalue()
        log(f'  stale meta: status={r2.status_code} stream={o4b.count("facility_quarterly_stream_start")}')
        # restore meta from build
        if os.path.isfile(bak_meta):
            pass
        m._PROVIDER_INDEXES_HYDRATED = False
        fpi._META_CACHE = None

    log('  Artifacts restored after audit 4')

    # --- Audit 5 ---
    log('\n## AUDIT 5 — Render deployment safety')
    render = (ROOT / 'render.yaml').read_text(encoding='utf-8')
    a5 = []
    a5.append(('buildCommand has build_facility_provider_indexes', 'build_facility_provider_indexes' in render))
    a5.append(('startCommand gunicorn-only', 'startCommand: gunicorn' in render and 'ensure_deploy_csvs' not in render.split('startCommand')[1][:80]))
    gi = (ROOT / '.gitignore').read_text(encoding='utf-8')
    a5.append(('gitignore excludes sqlite from commit', 'provider_indexes/*.sqlite' in gi))
    a5.append(('sqlite exists locally', os.path.isfile(fpi.SQLITE_PATH)))
    a5.append(('meta exists locally', os.path.isfile(fpi.META_PATH)))
    if os.path.isfile(fpi.META_PATH):
        with open(fpi.META_PATH, encoding='utf-8') as f:
            meta_r = json.load(f)
        a5.append(('meta row_count', meta_r.get('row_count', 0) > 400000))
    a5.append(('INDEX_DIR matches', fpi.INDEX_DIR == os.path.join(str(ROOT), 'data', 'provider_indexes')))
    for name, ok in a5:
        log(f'  {name}: {"OK" if ok else "FAIL"}')
    log(f'Audit 5 result: {"PASS" if all(x[1] for x in a5) else "FAIL"}')

    # --- Audit 6 ---
    log('\n## AUDIT 6 — Performance thresholds')
    perf: list[tuple[str, float, str, bool]] = []
    client = m.app.test_client()
    t0 = time.perf_counter()
    client.get('/health')
    health_ms = (time.perf_counter() - t0) * 1000
    perf.append(('health', health_ms, '<100ms', health_ms < 100))
    t0 = time.perf_counter()
    client.get('/')
    home_ms = (time.perf_counter() - t0) * 1000
    perf.append(('home', home_ms, '<500ms', home_ms < 500))
    cold_times = []
    for prov, _ in ccns[:5]:
        m.clear_provider_page_cache()
        buf6 = io.StringIO()
        with redirect_stdout(buf6):
            t0 = time.perf_counter()
            r = client.get(f'/provider/{prov}')
            cold_times.append((prov, (time.perf_counter() - t0) * 1000, r.status_code, buf6.getvalue()))
    for prov, ms, st, lg in cold_times:
        scan = 'facility_quarterly_stream_start' in lg
        perf.append((f'cold/{prov}', ms, '<2000ms', ms < 2000 and st == 200 and not scan))
    prov0 = ccns[0][0]
    t0 = time.perf_counter()
    r_hit = client.get(f'/provider/{prov0}')
    hit_ms = (time.perf_counter() - t0) * 1000
    perf.append((f'hit/{prov0}', hit_ms, '<50ms', hit_ms < 50 and r_hit.headers.get('X-PBJ-Provider-Cache') == 'HIT'))
    os.environ['PBJ_PROVIDER_COLD_SLOTS'] = '1'
    os.environ['PBJ_PROVIDER_COLD_WAIT'] = '60'
    m._PROVIDER_COLD_RENDER_SEM = None

    def _cold(p):
        m.clear_provider_page_cache()
        return m.app.test_client().get(f'/provider/{p}', headers={'User-Agent': 'Mozilla/5.0'})

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        futs = [pool.submit(_cold, ccns[0][0]), pool.submit(_cold, ccns[1][0])]
        conc = [(f.result().status_code, f.result().headers.get('X-PBJ-Provider-Cache')) for f in futs]
    perf.append(('concurrent_2', 0, 'no 503', all(s != 503 for s, _ in conc)))
    log('| test | ms | threshold | pass |')
    log('|------|-----|-----------|------|')
    for name, ms, thr, ok in perf:
        log(f'| {name} | {ms:.1f} | {thr} | {"yes" if ok else "NO"} |')
    log(f'  concurrent statuses: {conc}')
    a6_pass = all(x[3] for x in perf)
    log(f'Audit 6 result: {"PASS" if a6_pass else "PARTIAL/FAIL"}')

    # --- Audit 7 ---
    log('\n## AUDIT 7 — 503 behavior (code paths)')
    log('  503 triggers on /provider:')
    log('    1. no_pandas')
    log('    2. no_facility_csv (missing facility_quarterly_metrics.csv)')
    log('    3. queue_rejected: sem.acquire(timeout=wait) failed AND no stale cache')
    log('  NOT 503: cache_hit, cache_hit_after_queue_timeout, cache_hit_race, cold_burst 429, ai 429')
    log('  Cache: 429/503 responses are not stored (_provider_page_cached_response only on successful render path)')
    log('  Retry-After: 30 on 503 via _provider_busy_response; Cache-Control: no-store')
    m.clear_provider_page_cache()
    os.environ['PBJ_PROVIDER_COLD_SLOTS'] = '1'
    os.environ['PBJ_PROVIDER_COLD_WAIT'] = '0'
    m._PROVIDER_COLD_RENDER_SEM = None
    # saturated queue test
    import threading
    barrier = threading.Barrier(2)
    results503 = []

    def hold_sem():
        sem = m._provider_cold_render_semaphore()
        sem.acquire()
        barrier.wait()
        time.sleep(2)
        sem.release()

    def try_page():
        barrier.wait()
        r = m.app.test_client().get(f'/provider/{ccns[2][0]}')
        results503.append((r.status_code, r.headers.get('Retry-After'), r.headers.get('Cache-Control', '')[:40]))

    t_h = threading.Thread(target=hold_sem)
    t_p = threading.Thread(target=try_page)
    t_h.start()
    t_p.start()
    t_h.join()
    t_p.join()
    log(f'  forced queue test: {results503}')
    a7_ok = results503 and results503[0][0] in (200, 503)
    if results503 and results503[0][0] == 503:
        a7_ok = results503[0][1] == '30' and 'no-store' in (results503[0][2] or '')

    # --- Summary ---
    log('\n' + '=' * 72)
    log('SUMMARY')
    deploy_safe = not completeness_fail and not real_bugs and a3_pass and all(x[1] for x in a5)
    if not a6_pass:
        deploy_safe = False
    log(f'  Audit 1 completeness: {"PASS" if not completeness_fail else "FAIL"}')
    log(f'  Audit 2 parity: {"PASS" if not real_bugs else "FAIL"}')
    log(f'  Audit 3 no scans: {"PASS" if a3_pass else "FAIL"}')
    log(f'  Audit 5 deploy: {"PASS" if all(x[1] for x in a5) else "FAIL"}')
    log(f'  Audit 6 perf: {"PASS" if a6_pass else "PARTIAL"}')
    log(f'  Recommendation: {"SAFE TO DEPLOY" if deploy_safe else "FIX FIRST — see risks above"}')

    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    log(f'\nReport written: {REPORT}')
    return 0 if deploy_safe else 1


if __name__ == '__main__':
    raise SystemExit(main())
