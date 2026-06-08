#!/usr/bin/env python3
"""Fail if stale NY staffing report prose appears in public-facing copy.

Scans visible HTML/markdown prose only — strips embedded window.PBJ_REPORT_* JSON
and <script> blocks before pattern checks.

Verified from: insights-ny-minimum-staffing.html ownership table (2026-06-03 build).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ROOT / "insights-ny-minimum-staffing.html",
    ROOT / "insights-ny-minimum-staffing-press.html",
    ROOT / "insights_posts" / "ny-minimum-staffing.md",
]

STALE_PATTERNS: list[tuple[str, str]] = [
    (r"60\.1\s*%", "stale NYC for-profit rate (use 60.3%)"),
    (r"48\.1\s*%", "stale NYC non-profit rate (use 49.7%)"),
    (r"5\.4\s*%", "stale NYC government rate (use 5.2%)"),
    (r"20\.5\s*%", "stale statewide government rate (use 20.7%)"),
    (r"33\.22\s*%", "stale NYC share of below-minimum days (remove or use ~33.1%)"),
    (r"60[,\s]?389", "stale below-minimum day count"),
    (r"33[,\s]?809", "stale below-minimum day count"),
    (r"17[,\s]?208", "stale below-minimum day count"),
    (r"14[,\s]?061", "stale below-minimum day count"),
    (r"81\.7\s*%", "stale percentage"),
    (r"442\s+facility-days?", "stale facility-day count"),
    (r"168\s+of\s+596", "stale NYC home-count note (prefer delete)"),
]

PBJ_REPORT_MARKER = re.compile(r"window\.PBJ_REPORT_\w+\s*=\s*")
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
APPENDIX_CARD_LABEL = re.compile(
    r'<div\s+class="appendix-card-label"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
ROLE_FLOOR_CNA_HPRD = re.compile(r"CNA\s+HPRD", re.IGNORECASE)


def strip_pbj_report_json(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        m = PBJ_REPORT_MARKER.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        start = m.end()
        depth = 0
        j = start
        while j < len(text):
            c = text[j]
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        i = j
    return "".join(out)


def prose_from_html(html: str) -> str:
    text = SCRIPT_BLOCK.sub("", html)
    text = strip_pbj_report_json(text)
    return text


def prose_from_markdown(md: str) -> str:
    if md.startswith("---"):
        end = md.find("---", 3)
        if end != -1:
            return md[end + 3 :]
    return md


def check_role_floor_card_labels(html: str) -> list[str]:
    issues: list[str] = []
    for m in APPENDIX_CARD_LABEL.finditer(html):
        label = re.sub(r"<[^>]+>", "", m.group(1))
        label = re.sub(r"\s+", " ", label).strip()
        if ROLE_FLOOR_CNA_HPRD.search(label) and "cna-side" not in label.lower():
            issues.append(
                f'role-floor card label uses "CNA HPRD" without CNA-side: {label!r}'
            )
    return issues


def scan_text(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for pattern, message in STALE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            snippet = text[max(0, match.start() - 40) : match.end() + 40]
            snippet = re.sub(r"\s+", " ", snippet).strip()
            issues.append(f"{message} — …{snippet}…")
    if path.suffix.lower() == ".html":
        issues.extend(check_role_floor_card_labels(text))
    return issues


def main() -> int:
    issues: list[str] = []
    for path in TARGETS:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".html":
            prose = prose_from_html(raw)
        else:
            prose = prose_from_markdown(raw)
        for issue in scan_text(path, prose):
            issues.append(f"{path.relative_to(ROOT)}: {issue}")

    if issues:
        print("STALE NY STAFFING PROSE:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    print("OK: no stale NY staffing prose patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
