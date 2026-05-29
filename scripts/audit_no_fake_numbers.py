#!/usr/bin/env python3
"""
Read-only scan for risky fallback / placeholder / hardcoded threshold patterns.

Does not modify files. Classifies hits for review (A–E scale in docs).

Usage:
  python scripts/audit_no_fake_numbers.py
  python scripts/audit_no_fake_numbers.py --public-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "_linkedin-brand-extract",
    "premium/demo",
}

PUBLIC_GLOBS = ("app.py", "ownership/**/*.py", "ownership/**/*.js", "*.html", "data-sources.html")

PATTERNS: list[tuple[str, str]] = [
    (r"\bfallback\b", "fallback"),
    (r"\bplaceholder\b", "placeholder"),
    (r"\bmock\b", "mock"),
    (r"\bdummy\b", "dummy"),
    (r"\bsynthetic\b", "synthetic"),
    (r"\bfake\b", "fake"),
    (r"\bestimat(e|ed|ion)\b", "estimate"),
    (r"\bhardcoded\b", "hardcoded"),
    (r"\bif missing\b", "if missing"),
    (r"\bor 0\b", "or 0"),
    (r"fillna\s*\(", "fillna"),
    (r"\bcoalesce\b", "coalesce"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bdemo\b", "demo"),
    (r"\bsample data\b", "sample data"),
    (r"\btest data\b", "test data"),
]

THRESHOLD_LITERALS = [
    ("3.56", "NY/MACPAC threshold"),
    ("3.06", "CT MACPAC threshold"),
    ("3.5", "NY statute discussion"),
    ("3.50", "about/press copy"),
    ("4.1", "MACPAC chart"),
    ("0.55", "RN HPRD reference"),
    ("8", "RN hours rule (context-dependent)"),
    ("24", "hours/day"),
]

EXTENSIONS = {".py", ".js", ".html", ".md", ".json", ".tsx", ".ts", ".css"}


def _iter_files(public_only: bool):
    if public_only:
        for pat in PUBLIC_GLOBS:
            for p in ROOT.glob(pat):
                if p.is_file() and p.suffix in EXTENSIONS:
                    yield p
        return
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix not in EXTENSIONS:
            continue
        if "audit_no_fake_numbers" in p.name:
            continue
        yield p


def _is_public_path(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith("scripts/") and "test" not in rel:
        return False
    if rel.startswith("docs/"):
        return False
    if rel.startswith("premium/samples"):
        return True
    if rel in ("app.py", "data-sources.html", "about.html", "press.html"):
        return True
    if rel.startswith("ownership/"):
        return True
    return rel.endswith(".html")


def _safe_print(line: str) -> None:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--max-per-pattern", type=int, default=40)
    args = ap.parse_args()

    hits: dict[str, list[str]] = {label: [] for _, label in PATTERNS}
    thresh_hits: dict[str, list[str]] = {lit: [] for lit, _ in THRESHOLD_LITERALS}

    for path in _iter_files(args.public_only):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for i, line in enumerate(text.splitlines(), 1):
            for rx, label in PATTERNS:
                if len(hits[label]) >= args.max_per_pattern:
                    continue
                if re.search(rx, line, re.IGNORECASE):
                    pub = " [PUBLIC]" if _is_public_path(path) else ""
                    hits[label].append(f"{rel}:{i}{pub}: {line.strip()[:120]}")
            for lit, desc in THRESHOLD_LITERALS:
                if lit in line and len(thresh_hits[lit]) < args.max_per_pattern:
                    if re.search(rf"(?<!\d){re.escape(lit)}(?!\d)", line):
                        pub = " [PUBLIC]" if _is_public_path(path) else ""
                        thresh_hits[lit].append(f"{rel}:{i}{pub} ({desc}): {line.strip()[:100]}")

    print("=== Risky pattern scan ===\n")
    total = 0
    for _, label in PATTERNS:
        rows = hits[label]
        if not rows:
            continue
        print(f"## {label} ({len(rows)} hits, capped)")
        for r in rows[:15]:
            _safe_print(f"  {r}")
        if len(rows) > 15:
            _safe_print(f"  ... +{len(rows) - 15} more")
        print()
        total += len(rows)

    print("=== Threshold literals ===\n")
    for lit, desc in THRESHOLD_LITERALS:
        rows = thresh_hits[lit]
        if not rows:
            continue
        print(f"## {lit} — {desc} ({len(rows)} hits)")
        for r in rows[:10]:
            _safe_print(f"  {r}")
        if len(rows) > 10:
            _safe_print(f"  ... +{len(rows) - 10} more")
        print()

    print(f"Total pattern hits (capped): {total}")
    print("Review docs/data_quality_and_fallbacks_audit.md for classification guidance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
