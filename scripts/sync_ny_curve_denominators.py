#!/usr/bin/env python3
"""Align weekend_cards denominators with verification workbook / CSV truth.

Verified from: public/downloads/.../weekend_weekday_summary.csv (weekend_flag masks).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
WW_CSV = (
    ROOT
    / "public"
    / "downloads"
    / "PBJ320_NY_2025_daily_staffing_verification_csvs"
    / "weekend_weekday_summary.csv"
)
THRESHOLD = 3.5

# CSV slice label -> weekend_cards curve key (total-nursing report modes)
WEEKEND_CARD_CURVE_MAP: dict[str, str] = {
    "All NY": "weekend",
    "NY statewide for-profit": "weekend_ny_for_profit",
    "NYC five boroughs": "weekend_nyc",
    "NYC for-profit": "weekend_nyc_for_profit",
}


def extract_json_after(marker: str, text: str) -> tuple[object, int, int]:
    start = text.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : j + 1]), start, j + 1
    raise ValueError(f"unterminated JSON after {marker!r}")


def load_weekend_denominators() -> dict[str, int]:
    if not WW_CSV.is_file():
        raise FileNotFoundError(f"missing verification CSV: {WW_CSV}")
    df = pd.read_csv(WW_CSV)
    wknd = df[df["day_type"] == "Weekends"]
    out: dict[str, int] = {}
    for slice_label, curve_key in WEEKEND_CARD_CURVE_MAP.items():
        row = wknd[wknd["slice"] == slice_label]
        if row.empty:
            raise KeyError(f"no Weekends row for slice {slice_label!r}")
        out[curve_key] = int(row.iloc[0]["facility_days"])
    return out


def curve_denominator(curve: list) -> int:
    """Fallback when CSV has no row for a curve (non-report slices)."""
    counts: list[int] = []
    for pt in curve:
        if pt.get("pct_below"):
            counts.append(int(round(pt["below"] / (pt["pct_below"] / 100.0))))
    if not counts:
        return 0
    return max(set(counts), key=counts.count)


def main() -> int:
    truth = load_weekend_denominators()
    text = HTML.read_text(encoding="utf-8")
    interactive, istart, iend = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", text)
    charts, cstart, cend = extract_json_after("window.PBJ_REPORT_CHARTS = ", text)

    changes: list[str] = []

    for mode_key, mode in interactive.get("modes", {}).items():
        curves = mode["curves"]
        cfd = mode.get("curve_facility_days") or {}
        cards = mode.get("weekend_cards") or []
        for card in cards:
            key = card["curve"]
            n = truth.get(key)
            if n is None:
                n = cfd.get(key) or curve_denominator(curves.get(key, []))
            if n and card.get("facility_days") != n:
                changes.append(
                    f"{mode_key} weekend_cards[{key}]: {card.get('facility_days')} -> {n}"
                )
                card["facility_days"] = n
        for key, curve in curves.items():
            n = truth.get(key) or cfd.get(key) or curve_denominator(curve)
            if not n:
                continue
            for pt in curve:
                fixed = round(100.0 * pt["below"] / n, 2)
                if abs(fixed - float(pt["pct_below"])) > 0.01:
                    changes.append(
                        f"{mode_key} curve[{key}]@T{pt['threshold']}: "
                        f"pct {pt['pct_below']} -> {fixed}"
                    )
                    pt["pct_below"] = fixed

    total_mode = interactive["modes"]["total"]
    total_curves = total_mode["curves"]
    own = next(c for c in charts if c["id"] == "ownershipChart")
    for sl in own.get("slices", []):
        wk_key = sl.get("wknd_curve") or sl.get("sat_curve")
        if not wk_key or wk_key not in total_curves:
            continue
        pt = next(p for p in total_curves[wk_key] if abs(p["threshold"] - THRESHOLD) < 0.001)
        n = truth.get(wk_key) or curve_denominator(total_curves[wk_key])
        pct = round(100.0 * pt["below"] / n, 1) if n else pt["pct_below"]
        wk_field = "wknd_pct" if "wknd_pct" in sl else "sat_pct"
        if sl.get(wk_field) != pct:
            changes.append(f"ownership slice {sl['label']} {wk_field}: {sl.get(wk_field)} -> {pct}")
            sl[wk_field] = pct

    new_i = json.dumps(interactive, separators=(",", ":"))
    new_c = json.dumps(charts, separators=(",", ":"))
    text = text[:istart] + new_i + text[iend:cstart] + new_c + text[cend:]

    HTML.write_text(text, encoding="utf-8")
    print(f"Updated {HTML.name} ({len(changes)} changes):")
    for line in changes:
        print(f"  + {line}")
    print("\nVerification weekend denominators:")
    for k, v in sorted(truth.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
