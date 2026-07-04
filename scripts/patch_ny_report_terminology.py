#!/usr/bin/env python3
"""Standardize analytic terminology: standard vs minimum staffing law/rule."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "insights-ny-minimum-staffing.html"
PRESS = ROOT / "insights-ny-minimum-staffing-press.html"

# Order matters: longer / more specific phrases first.
REPORT_REPLACEMENTS: list[tuple[str, str]] = [
    ("Share of Days &lt; Min.", "Share of days below standard"),
    ("Share of Weekend days &lt; Min.", "Weekend days below standard"),
    ("NY Days &lt; Min.", "NY days below std"),
    ("Weekend Days &lt; Min.", "Wknd below std"),
    ("Share of Days < Min.", "Share of days below standard"),
    ("Share of Weekend days < Min.", "Weekend days below standard"),
    ("fell below the <strong>3.50 HPRD</strong> minimum on", "reported staffing below the <strong>3.50 HPRD</strong> standard on"),
    ("Below-minimum staffing was", "Below-standard staffing was"),
    ("Below-minimum rates differed", "Below-standard rates differed"),
    ("were below New York&rsquo;s <strong>3.50 HPRD</strong> minimum on", "were below New York&rsquo;s <strong>3.50 HPRD</strong> standard on"),
    ("were below minimum on", "were below the standard on"),
    ("Some homes are below minimum almost every day", "Some homes are below the standard almost every day"),
    ("state&rsquo;s <strong>3.50 HPRD</strong> minimum.", "state&rsquo;s <strong>3.50 HPRD</strong> standard."),
    ("<span data-hprd-label>3.50</span> HPRD minimum</span>", "<span data-hprd-label>3.50</span> HPRD standard</span>"),
    ('Threshold and "below minimum"', 'Threshold and "below standard"'),
    ("Threshold and \u201cbelow minimum\u201d", "Threshold and \u201cbelow standard\u201d"),
    ("<strong>Below minimum</strong> at threshold", "<strong>Below standard</strong> at threshold"),
    ("<strong>Below minimum</strong> = strictly under", "<strong>Below standard</strong> = strictly under"),
    ("below-minimum curve", "below-standard curve"),
    ("Monthly below-minimum rates", "Monthly below-standard rates"),
    ("shares below minimum by", "shares below standard by"),
    ("% below minimum at the active threshold", "% below standard at the active threshold"),
    ("% below minimum (lowest to highest", "% below standard (lowest to highest"),
    ("percent below minimum by", "percent below standard by"),
    ("share of facility-days below minimum", "share of facility-days below standard"),
    ("facility-days below minimum", "facility-days below standard"),
    ("'% below minimum'", "'% below standard'"),
    ('"% below minimum"', '"% below standard"'),
    ("label: '% below minimum'", "label: '% below standard'"),
    ("were below minimum on at least 90%", "were below the standard on at least 90%"),
    ("below minimum on 100%", "below the standard on 100%"),
    ("share below minimum staffing", "share below standard staffing"),
    ("More than half of NY facility-days fell below 3.50 HPRD", "More than half of NY facility-days were below the 3.50 HPRD standard"),
    (
        "Share of 2025 facility-days below New York&rsquo;s <span data-hprd-label>3.50</span> HPRD minimum",
        "Share of 2025 facility-days below New York&rsquo;s <span data-hprd-label>3.50</span> HPRD standard",
    ),
    ("Each bar is a band (e.g. below minimum on 100%", "Each bar is a band (e.g. below the standard on 100%"),
    ("setKpiLabels(labels[1], 'Share of Days < Min.', 'NY Days < Min.');", "setKpiLabels(labels[1], 'Share of days below standard', 'NY days below std');"),
    ("setKpiLabels(labels[2], 'Share of Weekend days < Min.', 'Weekend Days < Min.');", "setKpiLabels(labels[2], 'Weekend days below standard', 'Wknd below std');"),
]

PRESS_REPLACEMENTS: list[tuple[str, str]] = [
    ("share of facility-days below the minimum", "share of facility-days below the standard"),
    ("<strong>below minimum</strong> means strictly under 3.50", "<strong>below standard</strong> means strictly under 3.50"),
    ("were below the minimum (", "were below the standard ("),
    ("were below the minimum on every day", "were below the standard on every day"),
    ("below the minimum on at least", "below the standard on at least"),
    ("fell below New York&rsquo;s <strong>3.50 hours per resident day</strong> staffing minimum", "reported staffing below New York&rsquo;s <strong>3.50 hours per resident day</strong> standard"),
    ("3.50 hours per resident day</strong> minimum.", "3.50 hours per resident day</strong> standard."),
]


def apply_replacements(html: str, pairs: list[tuple[str, str]]) -> str:
    for old, new in pairs:
        html = html.replace(old, new)
    return html


def patch_report() -> list[str]:
    html = REPORT.read_text(encoding="utf-8")
    before = html
    html = apply_replacements(html, REPORT_REPLACEMENTS)
    REPORT.write_text(html, encoding="utf-8")
    applied = [f"{o} -> {n}" for o, n in REPORT_REPLACEMENTS if o in before]
    print(f"Patched {REPORT} ({REPORT.stat().st_size:,} bytes)")
    return applied


def patch_press() -> list[str]:
    html = PRESS.read_text(encoding="utf-8")
    before = html
    html = apply_replacements(html, PRESS_REPLACEMENTS)
    PRESS.write_text(html, encoding="utf-8")
    applied = [f"{o} -> {n}" for o, n in PRESS_REPLACEMENTS if o in before]
    print(f"Patched {PRESS} ({PRESS.stat().st_size:,} bytes)")
    return applied


def main() -> int:
    report = patch_report()
    press = patch_press()
    print(f"\nReport replacements applied: {len(report)}")
    for line in report:
        print(f"  - {line}")
    print(f"Press replacements applied: {len(press)}")
    for line in press:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
