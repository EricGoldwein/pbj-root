#!/usr/bin/env python3
"""Build geographic intelligence bundle in pbj-root (delegates to PBJapp when available)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PBJAPP = REPO.parent / "PBJapp"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/build_geo_intelligence_bundle.py CT [--quarter 2025Q3]", file=sys.stderr)
        return 2

    state = sys.argv[1]
    extra = sys.argv[2:]

    if PBJAPP.is_dir() and (PBJAPP / "scripts" / "build_geo_intelligence_bundle.py").is_file():
        cmd = [
            sys.executable,
            str(PBJAPP / "scripts" / "build_geo_intelligence_bundle.py"),
            state,
            "--pbj-root",
            str(REPO),
            *extra,
        ]
        print("[build_geo_intelligence_bundle] delegating to PBJapp:", " ".join(cmd), flush=True)
        return subprocess.call(cmd)

    print(
        "ERROR: PBJapp sibling not found. Set PBJAPP path or run from PBJapp:\n"
        "  python scripts/build_geo_intelligence_bundle.py CT --pbj-root <pbj-root>",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
