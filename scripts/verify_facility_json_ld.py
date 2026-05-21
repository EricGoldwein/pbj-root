#!/usr/bin/env python3
"""Check facility JSON-LD: valid JSON, PBJ rules, and match to visible provider page cues."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

JSON_LD_PATTERN = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _json_ld_docs(html: str) -> list[dict]:
    return [json.loads(block.strip()) for block in JSON_LD_PATTERN.findall(html)]


def _props_list(doc: dict) -> list[dict]:
    props = doc.get('additionalProperty') or []
    return [props] if isinstance(props, dict) else list(props)


def _prop_by_name(org: dict, name: str) -> dict | None:
    for p in _props_list(org):
        if str(p.get('name', '')).strip().lower() == name.strip().lower():
            return p
    return None


def _visible_entity_href(html: str) -> str | None:
    m = re.search(r'href="/entity/(\d+)"', html)
    return m.group(1) if m else None


def _visible_flag_cues(html: str) -> set[str]:
    cues: set[str] = set()
    if re.search(r'abuse', html, re.I) and (
        'pbj-risk-badge' in html or 'abuse icon' in html.lower()
    ):
        if '★' in html and re.search(r'Overall:\s*★(?!\s*★)', html):
            pass
    if 'SFF Candidate' in html or 'SFF Cand.' in html:
        cues.add('Special Focus Facility candidate')
    elif re.search(r'\bSFF\b', html) or 'Special Focus' in html:
        cues.add('Special Focus Facility')
    if re.search(r'Overall:\s*★\s*</span>', html) or re.search(
        r'Overall:\s*<[^>]+>\s*★\s*</', html
    ):
        cues.add('one-star overall CMS rating')
    if re.search(r'Staffing:\s*<[^>]*>★</', html) or 'one-star staffing' in html.lower():
        cues.add('one-star staffing CMS rating')
    if 'pbj-risk-badge' in html and re.search(r'abuse', html, re.I):
        if 'pbj-badge' in html:
            cues.add('CMS abuse icon')
    return cues


def verify_provider_page(ccn: str, *, verbose: bool = True) -> int:
    from app import app

    ccn = str(ccn).strip().zfill(6)
    with app.test_client() as client:
        resp = client.get(f'/provider/{ccn}')
    if resp.status_code != 200:
        print(f'FAIL {ccn}: HTTP {resp.status_code}')
        return 1

    html = resp.get_data(as_text=True)
    docs = _json_ld_docs(html)
    org = next((d for d in docs if d.get('@type') == 'MedicalOrganization'), None)
    if not org:
        print(f'FAIL {ccn}: no MedicalOrganization JSON-LD')
        return 1

    props = _props_list(org)
    quarter_props = [
        p for p in props if str(p.get('name', '')).startswith('PBJ staffing (')
    ]
    blob = ' '.join(
        str(p.get(k, ''))
        for p in props
        for k in ('name', 'value', 'propertyID')
    ).lower()

    errors: list[str] = []
    notes: list[str] = []

    if 'turnover' in blob:
        errors.append('turnover must not appear in JSON-LD')
    if 'cna hprd' in blob:
        errors.append('use nurse aide HPRD label (Nurse_Assistant_HPRD), not CNA HPRD')
    if len(quarter_props) > 4:
        errors.append(f'at most 4 quarterly PBJ properties expected, got {len(quarter_props)}')
    if len(quarter_props) < 1:
        errors.append('expected at least 1 quarterly PBJ property')

    for p in quarter_props:
        val = str(p.get('value', '')).lower()
        if 'five-star' in val or 'turnover' in val:
            errors.append(f'quarterly row must not include stars/turnover: {p.get("name")}')

    latest_ratings = _prop_by_name(org, 'Latest CMS ratings')
    if latest_ratings and 'five-star' not in str(latest_ratings.get('value', '')).lower():
        errors.append('Latest CMS ratings should contain Five-Star ratings when present')

    for p in quarter_props:
        if latest_ratings and str(p.get('value', '')) == str(latest_ratings.get('value', '')):
            errors.append('quarterly row duplicates Latest CMS ratings')

    ent_prop = _prop_by_name(org, 'Associated ownership entities')
    visible_ent = _visible_entity_href(html)
    if ent_prop and not visible_ent:
        errors.append('Associated ownership entities in JSON-LD but no /entity/ link on page')
    if visible_ent and not ent_prop:
        errors.append('visible /entity/ link on page but no Associated ownership entities in JSON-LD')

    flags_prop = _prop_by_name(org, 'PBJ320 facility flags')
    if flags_prop:
        json_flags = {f.strip() for f in str(flags_prop.get('value', '')).split(';') if f.strip()}
        visible = _visible_flag_cues(html)
        if json_flags and not visible and not any(
            x in str(flags_prop.get('value', '')).lower()
            for x in ('staffing', 'overall', 'sff', 'abuse')
        ):
            notes.append('flags present in JSON-LD; spot-check visible badges manually')
        if 'one-star staffing cms rating' in json_flags and 'Staffing:' not in html:
            errors.append('one-star staffing flag in JSON-LD but no Staffing badge on page')

    if not (org.get('identifier') or {}).get('value'):
        errors.append('missing CCN identifier')

    has_census = any(
        'average resident census' in str(p.get('value', '')).lower() for p in quarter_props
    )
    if has_census:
        notes.append('census in quarterly rows')
    else:
        notes.append('no census in quarterly rows (OK if source missing)')

    if latest_ratings:
        notes.append('Latest CMS ratings present')
    if flags_prop:
        notes.append('PBJ320 facility flags present')

    if quarter_props and latest_ratings:
        q_idx = next(
            (i for i, p in enumerate(props) if str(p.get('name', '')).startswith('PBJ staffing (')),
            -1,
        )
        r_idx = next(
            (i for i, p in enumerate(props) if str(p.get('name', '')).strip().lower() == 'latest cms ratings'),
            -1,
        )
        if q_idx >= 0 and r_idx >= 0 and q_idx > r_idx:
            errors.append('quarterly PBJ rows should appear before Latest CMS ratings')

    if errors:
        print(f'FAIL {ccn}:')
        for e in errors:
            print(f'  - {e}')
        return 1

    if verbose:
        line = f'OK {ccn}: {len(quarter_props)} quarter rows, valid JSON'
        if notes:
            line += ' (' + '; '.join(notes) + ')'
        print(line)
    return 0


def _sample_ccns() -> dict[str, str]:
    """Find example CCNs for spot-check categories (best effort from local data)."""
    import re

    out: dict[str, str] = {'baseline': '335513'}
    path = ROOT / 'search_index.json'
    if path.is_file():
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for row in data.get('f') or []:
            ccn = str(row.get('c') or '').strip().zfill(6)
            h = (row.get('h') or '').strip().lower()
            if not ccn:
                continue
            if 'abuse' in h:
                out.setdefault('abuse', ccn)
            if 'sff candidate' in h:
                out.setdefault('sff_candidate', ccn)
            elif re.search(r'\bsff\b', h) and 'candidate' not in h:
                out.setdefault('sff', ccn)
            if row.get('r') != 1:
                out.setdefault('no_flags', ccn)

    pi_files = sorted((ROOT / 'provider_info').glob('ProviderInfoNorm_*.csv'))
    if pi_files:
        try:
            import pandas as pd

            df = pd.read_csv(pi_files[-1], dtype=str, low_memory=False)
            cols = {c.lower(): c for c in df.columns}
            ccn_col = cols.get('ccn') or cols.get('provnum')
            staff_col = cols.get('staffing_rating')
            overall_col = cols.get('overall_rating')
            if ccn_col and staff_col:
                s = pd.to_numeric(df[staff_col], errors='coerce')
                o = pd.to_numeric(df[overall_col], errors='coerce') if overall_col else None
                mask = s == 1
                if o is not None:
                    mask &= o != 1
                hit = df.loc[mask, ccn_col].dropna().head(1)
                if not hit.empty:
                    out.setdefault('one_star_staffing', str(hit.iloc[0]).zfill(6))
        except Exception:
            pass

    fq_path = ROOT / 'facility_quarterly_metrics.csv'
    if not fq_path.is_file():
        fq_path = ROOT / 'facility_quarterly_metrics_latest.csv'
    if fq_path.is_file():
        try:
            import pandas as pd

            df = pd.read_csv(
                fq_path,
                usecols=lambda c: c in ('PROVNUM', 'CY_Qtr', 'avg_daily_census', 'Avg_Daily_Census'),
            )
            df['PROVNUM'] = df['PROVNUM'].astype(str).str.zfill(6)
            census_cols = [c for c in df.columns if 'census' in c.lower()]
            for prov, grp in df.groupby('PROVNUM'):
                sub = grp.sort_values('CY_Qtr').tail(4)
                if sub[census_cols].isna().all().all():
                    out.setdefault('missing_census', prov)
                    break
        except Exception:
            pass

    return out


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == '--spot':
        samples = _sample_ccns()
        print('Spot-check CCNs:', samples)
        return max(verify_provider_page(ccn, verbose=True) for ccn in samples.values())

    ccns = args if args else ['335513']
    return max(verify_provider_page(c) for c in ccns)


if __name__ == '__main__':
    raise SystemExit(main())
