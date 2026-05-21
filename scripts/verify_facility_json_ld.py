#!/usr/bin/env python3
"""Lightweight check: facility page JSON-LD is valid JSON and matches PBJ320 rules."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _json_ld_docs(html: str) -> list[dict]:
    docs = []
    for block in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        docs.append(json.loads(block.strip()))
    return docs


def _all_property_text(doc: dict) -> str:
    chunks: list[str] = []
    props = doc.get('additionalProperty') or []
    if isinstance(props, dict):
        props = [props]
    for p in props:
        if not isinstance(p, dict):
            continue
        for key in ('name', 'value', 'propertyID'):
            v = p.get(key)
            if v is not None:
                chunks.append(str(v))
    return ' '.join(chunks).lower()


def verify_provider_page(ccn: str) -> int:
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

    props = org.get('additionalProperty') or []
    if isinstance(props, dict):
        props = [props]
    quarter_props = [
        p for p in props if isinstance(p, dict) and str(p.get('name', '')).startswith('PBJ staffing (')
    ]
    blob = _all_property_text(org)

    errors: list[str] = []
    if 'turnover' in blob:
        errors.append('turnover must not appear in JSON-LD')
    if len(quarter_props) > 4:
        errors.append(f'expected at most 4 quarterly PBJ properties, got {len(quarter_props)}')
    if len(quarter_props) < 1:
        errors.append('expected at least 1 quarterly PBJ property')

    for p in quarter_props:
        val = str(p.get('value', '')).lower()
        if 'five-star' in val or 'turnover' in val:
            errors.append(f'quarterly property must not include stars/turnover: {p.get("name")}')

    has_ccn = 'cms certification number' in blob or (org.get('identifier') or {}).get('value')
    if not has_ccn:
        errors.append('missing CCN')

    if any('average resident census' in str(p.get('value', '')).lower() for p in quarter_props):
        print(f'  OK census present in quarterly summary ({ccn})')
    else:
        print(f'  note: no census in quarterly rows for {ccn} (may be missing in source data)')

    if 'pbj320 facility flags' in blob:
        print(f'  OK PBJ320 facility flags ({ccn})')

    if 'latest cms provider information' in blob:
        print(f'  OK Latest CMS Provider Information block ({ccn})')

    if errors:
        for e in errors:
            print(f'FAIL {ccn}: {e}')
        return 1

    print(
        f'OK {ccn}: {len(docs)} JSON-LD doc(s), {len(quarter_props)} quarterly PBJ properties, '
        f'valid JSON'
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    ccns = args if args else ['335513', '015009']
    return max(verify_provider_page(c) for c in ccns)


if __name__ == '__main__':
    raise SystemExit(main())
