#!/usr/bin/env python3
"""Fail on stale precomputed percentages in NY report embedded JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
WW_CSV = (
    ROOT
    / "public"
    / "downloads"
    / "PBJ320_NY_2025_daily_staffing_verification_csvs"
    / "weekend_weekday_summary.csv"
)
WEEKEND_CARD_CURVE_MAP: dict[str, str] = {
    "All NY": "weekend",
    "NY statewide for-profit": "weekend_ny_for_profit",
    "NYC five boroughs": "weekend_nyc",
    "NYC for-profit": "weekend_nyc_for_profit",
}
TOL_STORED = 0.011  # round(.,2) stored pct_below
TOL_DISPLAY = 0.05  # one-decimal chart/display fields


def extract_json_after(marker: str, text: str) -> object | None:
    if marker not in text:
        return None
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
    raise ValueError(f"unterminated JSON after {marker!r}")


def curve_denominator(curve: list) -> int:
    counts: list[int] = []
    for pt in curve:
        if pt.get("pct_below"):
            counts.append(int(round(pt["below"] / (pt["pct_below"] / 100.0))))
    return max(set(counts), key=counts.count) if counts else 0


def round_display(pct: float) -> float:
    return round(pct * 10) / 10


def load_weekend_card_truth() -> dict[str, int]:
    if not WW_CSV.is_file():
        return {}
    import pandas as pd

    df = pd.read_csv(WW_CSV)
    wknd = df[df["day_type"] == "Weekends"]
    return {
        WEEKEND_CARD_CURVE_MAP[str(r["slice"])]: int(r["facility_days"])
        for _, r in wknd.iterrows()
        if str(r["slice"]) in WEEKEND_CARD_CURVE_MAP
    }


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    issues: list[str] = []
    audited = 0
    weekend_truth = load_weekend_card_truth()
    if not weekend_truth:
        issues.append(f"missing weekend_cards CSV truth: {WW_CSV}")

    interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
    charts = extract_json_after("window.PBJ_REPORT_CHARTS = ", html)
    statute = extract_json_after("window.PBJ_REPORT_NY_STATUTE = ", html)
    calendar = extract_json_after("window.PBJ_REPORT_CALENDAR_EXTRA = ", html)

    if interactive:
        for mode_key, mode in interactive.get("modes", {}).items():
            curves = mode.get("curves") or {}
            cfd = mode.get("curve_facility_days") or {}
            weekend_fd = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards") or []}

            for key, curve in curves.items():
                n = cfd.get(key) or curve_denominator(curve)
                if not n:
                    continue
                for pt in curve:
                    expected = round(100.0 * pt["below"] / n, 2)
                    if abs(expected - float(pt["pct_below"])) > TOL_STORED:
                        issues.append(
                            f"{mode_key} curve {key}@T{pt['threshold']}: pct_below={pt['pct_below']} "
                            f"vs {pt['below']}/{n}={expected}"
                        )
                    audited += 1

            for card in mode.get("weekend_cards") or []:
                key = card["curve"]
                curve = curves.get(key, [])
                csv_n = weekend_truth.get(key)
                curve_n = csv_n or cfd.get(key) or curve_denominator(curve)
                if csv_n is not None and card.get("facility_days") != csv_n:
                    issues.append(
                        f"{mode_key} weekend_cards {key}: facility_days={card.get('facility_days')} "
                        f"!= CSV={csv_n}"
                    )
                elif csv_n is None and curve_n and card.get("facility_days") != curve_n:
                    issues.append(
                        f"{mode_key} weekend_cards {key}: facility_days={card.get('facility_days')} "
                        f"!= curve_n={curve_n}"
                    )
                if key == "weekend_nyc" and card.get("facility_days") == 17082:
                    issues.append(f"{mode_key} weekend_nyc stale facility_days 17082")
                audited += 1

        mode_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
        mode = interactive["modes"][mode_key]
        curves = mode.get("curves") or {}
        weekend_fd = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards") or []}

        dow_chart = charts and next((c for c in charts if c.get("id") == "dowChart"), None)
        dow_fd_map: dict[str, int] = {}
        if dow_chart:
            dows = dow_chart.get("dows") or []
            fds = dow_chart.get("facility_days") or []
            dow_fd_map = {
                str(d): int(n) for d, n in zip(dows, fds) if isinstance(n, (int, float))
            }

        for dow, curve in (mode.get("curves_by_dow") or {}).items():
            fd = dow_fd_map.get(dow) or (mode.get("curve_facility_days") or {}).get(f"dow:{dow}")
            if not fd:
                continue
            for pt in curve:
                expected = round(100.0 * pt["below"] / fd, 2)
                if abs(expected - float(pt["pct_below"])) > TOL_STORED:
                    issues.append(f"dow {dow}@T{pt['threshold']}: pct mismatch")
                audited += 1

    if charts:
        own = next((c for c in charts if c.get("id") == "ownershipChart"), None)
        if own and interactive:
            mode_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
            mode = interactive["modes"][mode_key]
            curves = mode["curves"]
            weekend_fd = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards") or []}
            slice_fd = {
                row["curve"]: row["facility_days"]
                for row in mode.get("slice_table") or []
            }
            for sl in own.get("slices", []):
                for field, curve_key in (
                    ("all_pct", sl.get("all_curve")),
                    ("wknd_pct", sl.get("wknd_curve") or sl.get("sat_curve")),
                ):
                    if not curve_key or field not in sl:
                        continue
                    pt = next(
                        p for p in curves[curve_key] if abs(p["threshold"] - 3.5) < 0.001
                    )
                    fd = slice_fd.get(curve_key) or weekend_fd.get(curve_key) or curve_denominator(
                        curves[curve_key]
                    )
                    expected = round_display(100.0 * pt["below"] / fd) if fd else float(sl[field])
                    if abs(round_display(float(sl[field])) - expected) > TOL_DISPLAY:
                        issues.append(
                            f"ownership slice {sl['label']} {field}: {sl[field]} vs {pt['below']}/{fd}"
                        )
                    audited += 1

    if statute:
        fd = statute.get("facility_days") or statute.get("facility_days_total")
        for days_key, pct_key in (
            ("facility_days_meets_all_ny_requirements", "pct_meets_all_ny_requirements"),
            ("facility_days_below_cna", "pct_below_cna"),
        ):
            days = statute.get(days_key)
            pct = statute.get(pct_key)
            if days and pct and fd:
                expected = round_display(100.0 * days / fd)
                if abs(round_display(float(pct)) - expected) > TOL_DISPLAY:
                    issues.append(f"statute {days_key}: {pct} vs {days}/{fd}")
                audited += 1

    print("=== NY pct field consistency audit ===\n")
    print(f"Fields checked: {audited}")
    print(f"ISSUES ({len(issues)}):")
    for line in issues:
        print(f"  ! {line}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
