"""Build NY press page — delegates to PBJapp (slate insights palette)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PBJ_APP = Path(__file__).resolve().parents[2] / "PBJapp"
BUILD = PBJ_APP / "scripts" / "build_ny_minimum_insights_press.py"


def main() -> int:
    if not BUILD.is_file():
        print(f"Missing builder: {BUILD}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(BUILD)])


if __name__ == "__main__":
    raise SystemExit(main())
