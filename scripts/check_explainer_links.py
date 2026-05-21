#!/usr/bin/env python3
"""HTTP-check external URLs on PBJ explainer pages and shared CMS constants."""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from site_public_config import (  # noqa: E402
    CARE_COMPARE_URL,
    CMS_2001_STAFFING_STUDY_URL,
    CMS_MDS_URL,
    CMS_NURSING_HOME_IMPROVEMENT_URL,
    CMS_OPEN_DATA_URL,
    CMS_PBJ_DAILY_DATASET_URL,
    CMS_PBJ_EMPLOYEE_DETAIL_URL,
    CMS_PBJ_POLICY_MANUAL_URL,
    CMS_PBJ_PUF_DOCUMENTATION_URL,
    CMS_PBJ_STAFFING_SUBMISSION_URL,
    CMS_PROVIDER_INFO_DATASET_URL,
    CMS_SFF_PROGRAM_URL,
    MACPAC_STATE_STAFFING_URL,
)

EXPLAINER_HTML = (ROOT / 'phoebe.html', ROOT / 'data-sources.html')
URL_RE = re.compile(r'href="(https?://[^"]+)"', re.I)


def check_url(url: str) -> tuple[int | None, str]:
    headers = {'User-Agent': 'PBJ320-link-check/1.0'}
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.status, 'ok'
        except urllib.error.HTTPError as exc:
            if method == 'GET' or exc.code in (405, 403):
                return exc.code, f'http {exc.code}'
        except Exception as exc:  # noqa: BLE001
            if method == 'GET':
                return None, str(exc)[:80]
    return None, 'unreachable'


def main() -> int:
    named = {
        'CMS_PBJ_STAFFING_SUBMISSION_URL': CMS_PBJ_STAFFING_SUBMISSION_URL,
        'CMS_PBJ_POLICY_MANUAL_URL': CMS_PBJ_POLICY_MANUAL_URL,
        'CMS_PBJ_DAILY_DATASET_URL': CMS_PBJ_DAILY_DATASET_URL,
        'CMS_PBJ_EMPLOYEE_DETAIL_URL': CMS_PBJ_EMPLOYEE_DETAIL_URL,
        'CMS_PROVIDER_INFO_DATASET_URL': CMS_PROVIDER_INFO_DATASET_URL,
        'CMS_PBJ_PUF_DOCUMENTATION_URL': CMS_PBJ_PUF_DOCUMENTATION_URL,
        'CMS_2001_STAFFING_STUDY_URL': CMS_2001_STAFFING_STUDY_URL,
        'CMS_MDS_URL': CMS_MDS_URL,
        'CMS_NURSING_HOME_IMPROVEMENT_URL': CMS_NURSING_HOME_IMPROVEMENT_URL,
        'CMS_SFF_PROGRAM_URL': CMS_SFF_PROGRAM_URL,
        'CMS_OPEN_DATA_URL': CMS_OPEN_DATA_URL,
        'MACPAC_STATE_STAFFING_URL': MACPAC_STATE_STAFFING_URL,
        'Care Compare': CARE_COMPARE_URL,
    }
    failures = 0
    print('site_public_config CMS constants:')
    for label, url in named.items():
        status, detail = check_url(url)
        ok = status and 200 <= status < 400
        if not ok:
            failures += 1
        print(f'  [{"OK" if ok else "FAIL"}] {label}: {status} {detail}')

    print('\nInline https links in phoebe.html + data-sources.html:')
    seen: set[str] = set()
    for path in EXPLAINER_HTML:
        for url in URL_RE.findall(path.read_text(encoding='utf-8')):
            if url in seen:
                continue
            seen.add(url)
            status, detail = check_url(url)
            ok = status and 200 <= status < 400
            if not ok:
                failures += 1
            print(f'  [{"OK" if ok else "FAIL"}] {status} {url[:100]}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
