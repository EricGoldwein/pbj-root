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
    (r"(?<![0-9])47\.1\s*%", "stale statewide below-minimum share (use 57.1% daily 3.50)"),
    (r"(?<![0-9])101[,\s]?779", "stale below-minimum day count (use 123,428 daily 3.50)"),
    (r"(?<![0-9])76\.9\s*%", "stale weekend share"),
    (r"(?<![0-9])83\.0\s*%", "stale full-standard weekend share in daily hero/definitions (use 78.4% at 3.50)"),
    (r"(?<![0-9])39\.7\s*%", "stale met-all-three share (use NY-mapped ~34.9%)"),
    (r"(?<![0-9])82\.4\s*%", "stale NYC weekend share in press copy if embed differs"),
    (r"(?<![0-9])13[,\s]?983", "stale NYC weekend below count"),
    (r"(?<![0-9])13983\b", "stale NYC weekend below count"),
    (r"(?<![0-9])60\.1\s*%", "stale NYC for-profit rate (use 60.3%)"),
    (r"(?<![0-9])48\.1\s*%", "stale NYC non-profit rate (use 49.7%)"),
    (r"(?<![0-9])5\.4\s*%", "stale NYC government rate (use 5.2%)"),
    (r"(?<![0-9])20\.5\s*%", "stale statewide government rate (use 20.7%)"),
    (r"(?<![0-9])33\.22\s*%", "stale NYC share of below-minimum days (remove or use ~33.1%)"),
    (r"(?<![0-9])60[,\s]?389", "stale below-minimum day count"),
    (r"(?<![0-9])33[,\s]?809", "stale below-minimum day count"),
    (r"(?<![0-9])17[,\s]?208", "stale below-minimum day count"),
    (r"(?<![0-9])14[,\s]?061", "stale below-minimum day count"),
    (r"(?<![0-9])81\.7\s*%", "stale percentage"),
    (r"(?<![0-9])442\s+facility-days?", "stale facility-day count"),
    (r"168\s+of\s+596", "stale NYC home-count note (prefer delete)"),
]

ALLOWED_COMPONENT = re.compile(
    r"standard-component-note|3\.50 total component|3\.50 HPRD|scenario|below-cell|pct-cell|"
    r"slice-row|ownership-slices|Media advisory|og:description|twitter:description|"
    r"3\.50 hours per resident|reported staffing below|quarterly-statutory|method-quarterly|"
    r"ny-standard-compliance|statute-modal|quarterly statutory-style",
    re.I,
)

DAILY_BANNED_PATTERNS: list[tuple[str, str]] = [
    (r"missed at least one part of the state", "daily hero uses full-standard miss-any framing"),
    (r"missed part of the staffing standard", "daily section uses full-standard miss-any framing"),
    (r"missed at least one mapped part", "daily section uses full-standard miss-any framing"),
    (r"missed at least one floor", "daily section uses full-standard miss-any framing"),
    (r"miss any of 3\.50", "daily section uses full-standard miss-any framing"),
    (r"fully compliant", "daily compliance language"),
    (r"daily compliance", "daily compliance language"),
    (r"daily violation", "daily violation language"),
    (r"failed (?:the )?standard", "daily failed-standard language"),
    (r"out of compliance", "compliance language outside quarterly/modal context"),
    (r"140[,\s]?757 facility-days", "daily primary should use 123,428 at 3.50 HPRD"),
    (r"65\.1% of all daily records", "daily primary should use 57.1% at 3.50 HPRD"),
]

DAILY_BANNED_ALLOW = re.compile(
    r"ny-standard-compliance|statute-modal|method-quarterly|quarterly-statutory|"
    r"not NY DOH|enforcement determinations|Quarterly enforcement|out of compliance, subject",
    re.I,
)

PBJ_REPORT_MARKER = re.compile(r"window\.PBJ_REPORT_\w+\s*=\s*")
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
APPENDIX_CARD_LABEL = re.compile(
    r'<div\s+class="appendix-card-label"[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
ROLE_FLOOR_CNA_HPRD = re.compile(r"CNA\s+HPRD", re.IGNORECASE)
ROLE_FLOOR_INTRO_CNA = re.compile(
    r"including at least <strong>2\.20</strong>\s+CNA\s+HPRD",
    re.IGNORECASE,
)
ROLE_FLOOR_MODAL_CNA = re.compile(
    r"2\.20</strong>\s+CNA\s+and",
    re.IGNORECASE,
)


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
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = strip_pbj_report_json(text)
    return text


def prose_from_markdown(md: str) -> str:
    if md.startswith("---"):
        end = md.find("---", 3)
        if end != -1:
            return md[end + 3 :]
    return md


def check_role_floor_prose(html: str) -> list[str]:
    issues: list[str] = []
    if ROLE_FLOOR_INTRO_CNA.search(html):
        issues.append(
            'role-floor intro uses "2.20 CNA HPRD" — use "2.20 CNA-side HPRD"'
        )
    if ROLE_FLOOR_MODAL_CNA.search(html):
        issues.append(
            'NY role-floor modal uses "2.20 CNA" — use "2.20 CNA-side"'
        )
    return issues


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


def check_daily_banned_prose(html: str) -> list[str]:
    """Flag daily-context wording that implies formal compliance or full-standard daily primary."""
    issues: list[str] = []
    # Visible daily sections only (exclude methodology tail and modals for some patterns)
    daily_blocks = []
    for sec_id in ("hero", "definitions", "weekend", "provider-shortfalls", "ownership", "geography"):
        m = re.search(
            rf'<(?:header|section)[^>]*\bid="{sec_id}"[^>]*>(.*?)</(?:header|section)>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            daily_blocks.append(m.group(1))
    daily_text = "\n".join(daily_blocks)
    for pattern, message in DAILY_BANNED_PATTERNS:
        for match in re.finditer(pattern, daily_text, re.IGNORECASE):
            window = daily_text[max(0, match.start() - 120) : match.end() + 120]
            if DAILY_BANNED_ALLOW.search(window):
                continue
            snippet = daily_text[max(0, match.start() - 40) : match.end() + 40]
            snippet = re.sub(r"\s+", " ", snippet).strip()
            issues.append(f"{message} — …{snippet}…")
    if re.search(r'id="statute-sensitivity"', html, re.I):
        issues.append("standalone daily role-floor appendix (#statute-sensitivity) should be removed or demoted")
    return issues


def scan_text(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    for pattern, message in STALE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            window = text[max(0, match.start() - 80) : match.end() + 80]
            if ALLOWED_COMPONENT.search(window):
                continue
            snippet = text[max(0, match.start() - 40) : match.end() + 40]
            snippet = re.sub(r"\s+", " ", snippet).strip()
            issues.append(f"{message} — …{snippet}…")
    if path.suffix.lower() == ".html":
        issues.extend(check_role_floor_prose(text))
        issues.extend(check_role_floor_card_labels(text))
        issues.extend(check_daily_banned_prose(text))
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
