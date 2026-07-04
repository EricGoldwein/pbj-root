#!/usr/bin/env python3
"""Backward-compatible wrapper for SFF dataset build."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "scripts" / "sff" / "build_sff_dataset.py"
    runpy.run_path(str(target), run_name="__main__")
