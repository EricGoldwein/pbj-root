#!/usr/bin/env python3
"""Fail if NY report default metric or methods still use broad/admin-inclusive mapping."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"

ADMIN_COLS = ("Hrs_RNadmin", "Hrs_LPNadmin", "Hrs_RNDON")
DEFAULT_MODE = "ny_mapped_non_admin_hprd"


def extract_json(marker: str, text: str) -> dict:
    start = text.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : j + 1])
    raise ValueError(marker)


def prose(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.I | re.DOTALL)
    text = re.sub(r"window\.PBJ_REPORT_\w+\s*=\s*[\[{].*?[\]}];?", "", text, flags=re.DOTALL)
    return text


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    issues: list[str] = []

    interactive = extract_json("window.PBJ_REPORT_INTERACTIVE = ", html)
    if interactive.get("default_mode") != DEFAULT_MODE:
        issues.append(f"default_mode is {interactive.get('default_mode')!r}, expected {DEFAULT_MODE!r}")

    mode = interactive["modes"][DEFAULT_MODE]
    label = mode.get("label", "").lower()
    if re.search(r"\badmin\b", label) and "non-admin" not in label and "comparison" not in label:
        issues.append("default mode label mentions admin without comparison framing")

    statute = extract_json("window.PBJ_REPORT_NY_STATUTE = ", html) if "PBJ_REPORT_NY_STATUTE" in html else {}
    for col in ADMIN_COLS:
        if col in statute.get("total_hours_columns", []):
            issues.append(f"statute total_hours_columns includes {col}")
        if col in statute.get("lpn_rn_hours_columns", []):
            issues.append(f"statute lpn_rn_hours_columns includes {col}")

    inc = statute.get("include_don_sensitivity") or {}
    if not inc:
        issues.append("PBJ_REPORT_NY_STATUTE missing include_don_sensitivity block")
    elif inc.get("lpn_rn_hours_columns") != ["Hrs_RN", "Hrs_LPN", "Hrs_RNDON"]:
        issues.append("include-DON licensed floor must be RN+LPN+RN DON (Option 1)")
    elif "Hrs_RNDON" not in inc.get("total_hours_columns", []):
        issues.append("include-DON total must include Hrs_RNDON")

    daily = ROOT / "public/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs/daily_facility_data.csv"
    if daily.is_file():
        import pandas as pd

        head = pd.read_csv(daily, nrows=0)
        for col in (
            "direct_care_hprd",
            "below_350_direct_care",
            "below_220_cna_side",
            "below_110_licensed",
        ):
            if col not in head.columns:
                issues.append(f"workbook daily missing column {col}")

    fq = ROOT / "public/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs/facility_quarter_summary.csv"
    if not fq.is_file():
        issues.append("missing facility_quarter_summary.csv")

    visible = prose(html)
    if re.search(r"default total nursing HPRD includes RN DON", visible, re.I):
        issues.append("methods still say default includes RN DON/admin")
    if re.search(r"47\.1\s*%", visible) and "comparison" not in visible.lower():
        issues.append("stale broad-total 47.1% in visible prose")

    if issues:
        print("FAIL statutory role mapping audit:")
        for item in issues:
            print(f"  - {item}")
        return 1

    print("PASS statutory role mapping audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
