#!/usr/bin/env python3
"""Print facility page JSON-LD additionalProperty names and values."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ccn = (sys.argv[1] if len(sys.argv) > 1 else '335513').strip().zfill(6)
    from app import app

    with app.test_client() as client:
        resp = client.get(f'/provider/{ccn}')
    if resp.status_code != 200:
        print(f'HTTP {resp.status_code} for /provider/{ccn}')
        return 1

    html = resp.get_data(as_text=True)
    pattern = r'<script type="application/ld\+json">(.*?)</script>'
    for block in re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE):
        doc = json.loads(block.strip())
        if doc.get('@type') != 'MedicalOrganization':
            continue
        print(f'MedicalOrganization @ {doc.get("url", "")}\n')
        props = doc.get('additionalProperty') or []
        if isinstance(props, dict):
            props = [props]
        for p in props:
            if not isinstance(p, dict):
                continue
            print('---', p.get('name'))
            val = str(p.get('value') or '')
            print('   ', val[:300] + ('…' if len(val) > 300 else ''))
        return 0

    print(f'No MedicalOrganization JSON-LD on /provider/{ccn}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
