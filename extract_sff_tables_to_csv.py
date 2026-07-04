#!/usr/bin/env python3
"""Backward-compatible wrapper for SFF PDF table extraction."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "scripts" / "sff" / "extract_sff_posting.py"
    runpy.run_path(str(target), run_name="__main__")
