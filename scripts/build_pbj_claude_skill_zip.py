#!/usr/bin/env python3
"""Build downloads/pbj320-staffing-review.zip for Claude Skill upload.

Authoritative packaged skill tree: ``downloads/pbj320-staffing-review/`` (this script zips that folder only).
The ``_ericized_skill_inspect/pbj320-staffing-review/`` tree is a separate snapshot for inspection and may
not match; refresh it manually from ``downloads/`` when needed.
"""

from __future__ import annotations

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, 'downloads', 'pbj320-staffing-review')
ZIP_PATH = os.path.join(ROOT, 'downloads', 'pbj320-staffing-review.zip')
ZIP_PREFIX = 'pbj320-staffing-review'


def main() -> None:
    if not os.path.isdir(SKILL_DIR):
        raise SystemExit(f'Missing skill directory: {SKILL_DIR}')
    os.makedirs(os.path.dirname(ZIP_PATH), exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _dirnames, filenames in os.walk(SKILL_DIR):
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, SKILL_DIR)
                arc = os.path.join(ZIP_PREFIX, rel).replace('\\', '/')
                zf.write(full, arc)
    print(f'Wrote {ZIP_PATH}')


if __name__ == '__main__':
    main()
