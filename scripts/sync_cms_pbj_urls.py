#!/usr/bin/env python3
"""Check or update CMS_PBJ_POLICY_MANUAL_URL from the CMS staffing-data-submission hub."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'site_public_config.py'

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from site_public_config import CMS_PBJ_POLICY_MANUAL_URL  # noqa: E402
from utils.cms_pbj_url_sync import fetch_policy_manual_pdf_url  # noqa: E402

_CONFIG_LINE_RE = re.compile(
    r"^CMS_PBJ_POLICY_MANUAL_URL = \(\n\s*'([^']+)'\n\)",
    re.M,
)


def _write_config(url: str) -> None:
    text = CONFIG.read_text(encoding='utf-8')
    new_block = f"CMS_PBJ_POLICY_MANUAL_URL = (\n    '{url}'\n)"
    updated, n = _CONFIG_LINE_RE.subn(new_block, text, count=1)
    if n != 1:
        raise RuntimeError('Could not find CMS_PBJ_POLICY_MANUAL_URL in site_public_config.py')
    CONFIG.write_text(updated, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Update site_public_config.py when CMS href changed')
    parser.add_argument('--print', action='store_true', dest='print_urls', help='Print configured vs live URLs')
    args = parser.parse_args()

    live = fetch_policy_manual_pdf_url()
    if not live:
        print('Could not find policy-manual PDF on CMS hub page.', file=sys.stderr)
        return 1

    configured = CMS_PBJ_POLICY_MANUAL_URL
    if args.print_urls:
        print(f'configured: {configured}')
        print(f'cms hub:    {live}')

    if live == configured:
        print('OK — CMS_PBJ_POLICY_MANUAL_URL matches CMS hub.')
        return 0

    print(f'Drift — configured:\n  {configured}\ncms hub:\n  {live}')
    if args.write:
        _write_config(live)
        print(f'Updated {CONFIG.name}')
        return 0
    print('Run with --write to update site_public_config.py', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
