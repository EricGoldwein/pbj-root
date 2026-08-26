#!/usr/bin/env python3
"""Wrapper: python scripts/run_cms_release_watcher.py → python -m cms_watcher."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cms_watcher.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
