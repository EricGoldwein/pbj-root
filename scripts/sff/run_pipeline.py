#!/usr/bin/env python3
"""Run the full SFF pipeline: extract -> build -> publish -> validate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script_name: str, *args: str) -> int:
    cmd = [sys.executable, str(SCRIPT_DIR / script_name), *args]
    print(f"\n==> {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    return int(result.returncode)


def main() -> int:
    steps = (
        "extract_sff_posting.py",
        "build_sff_dataset.py",
        "publish_sff_artifacts.py",
        "validate_sff_dataset.py",
    )
    for step in steps:
        code = _run(step)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
