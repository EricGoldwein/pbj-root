#!/usr/bin/env python3
"""CLI: provider index artifact status (same payload as GET /debug/provider-indexes)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import app as m

    payload = m._provider_index_status_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
