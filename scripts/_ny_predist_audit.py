#!/usr/bin/env python3
"""Pre-distribution audit: displayed % vs numerator/denominator from embedded JSON."""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
THRESHOLD = 3.5
TOL = 0.05  # percentage points before rounding


def extract_json_after(marker: str, text: str) -> object:
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


def lookup_curve(curve: list, threshold: float = THRESHOLD) -> dict:
    for pt in curve:
        if abs(pt["threshold"] - threshold) < 0.001:
            return pt
    raise KeyError(f"threshold {threshold} not on curve")


def fmt_pct_from_counts(below: int, fd: int) -> float:
    return 100.0 * below / fd if fd else 0.0


def round_display(pct: float) -> float:
    return round(pct * 10) / 10


def parse_wt_rows(html: str) -> list[dict]:
    rows = []
    pattern = re.compile(
        r'data-all-curve="([^"]+)" data-weekend-curve="([^"]+)".*?'
        r'<span class="wt-row-label">([^<]+)</span>.*?'
        r'wt-stat--all"><span class="wt-pct[^"]*">([\d.]+)%</span><span class="wt-count">([\d,]+)/([\d,]+)</span>.*?'
        r'wt-stat--wkday"><span class="wt-pct[^"]*">([\d.]+)%</span><span class="wt-count">([\d,]+)/([\d,]+)</span>.*?'
        r'wt-stat--wkend"><span class="wt-pct[^"]*">([\d.]+)%</span><span class="wt-count">([\d,]+)/([\d,]+)</span>',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        rows.append(
            {
                "all_curve": m.group(1),
                "weekend_curve": m.group(2),
                "label": m.group(3),
                "all_pct": float(m.group(4)),
                "all_below": int(m.group(5).replace(",", "")),
                "all_fd": int(m.group(6).replace(",", "")),
                "wkday_pct": float(m.group(7)),
                "wkday_below": int(m.group(8).replace(",", "")),
                "wkday_fd": int(m.group(9).replace(",", "")),
                "wkend_pct": float(m.group(10)),
                "wkend_below": int(m.group(11).replace(",", "")),
                "wkend_fd": int(m.group(12).replace(",", "")),
            }
        )
    return rows


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    issues: list[str] = []

    interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
    charts = extract_json_after("window.PBJ_REPORT_CHARTS = ", html)
    ui = extract_json_after("window.PBJ_REPORT_UI = ", html)
    statute = extract_json_after("window.PBJ_REPORT_NY_STATUTE = ", html)
    calendar_extra = extract_json_after("window.PBJ_REPORT_CALENDAR_EXTRA = ", html)

    mode = interactive["modes"]["total"]
    curves = mode["curves"]
    fd_total = mode["facility_days_total"]

    # Hero KPIs from HTML
    kpi_vals = re.findall(r'kpi-num-value">([^<]+)</span>', html)
    hero_below = int(kpi_vals[0].replace(",", "").replace(" Days", "").strip())
    hero_pct = float(kpi_vals[1].rstrip("%"))
    hero_wknd = float(kpi_vals[2].rstrip("%"))

    all_ny = lookup_curve(curves["all_ny"])
    wknd = lookup_curve(curves["weekend"])

    for name, displayed, below, fd, curve_pct in [
        ("hero below count", hero_below, all_ny["below"], fd_total, None),
        ("hero all-days %", hero_pct, all_ny["below"], fd_total, all_ny["pct_below"]),
        ("hero weekend %", hero_wknd, wknd["below"], None, wknd["pct_below"]),
    ]:
        if below != displayed and name.endswith("count"):
            issues.append(f"{name}: displayed {displayed} vs curve {below}")
        if fd and name.endswith("%"):
            recomputed = fmt_pct_from_counts(below, fd)
            if abs(round_display(recomputed) - displayed) > TOL:
                issues.append(
                    f"{name}: displayed {displayed}% vs {below}/{fd}={recomputed:.4f}% "
                    f"(rounded {round_display(recomputed)}%)"
                )
        if curve_pct is not None and abs(round_display(curve_pct) - displayed) > TOL:
            issues.append(f"{name}: displayed {displayed}% vs curve pct_below {curve_pct}")

    # Weekend table rows
    wt_rows = parse_wt_rows(html)
    weekend_cards = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards", [])}
    slice_fd = mode.get("slice_facility_days", {})

    for row in wt_rows:
        all_pt = lookup_curve(curves[row["all_curve"]])
        wk_pt = lookup_curve(curves[row["weekend_curve"]])
        wk_fd = weekend_cards.get(row["weekend_curve"], row["wkend_fd"])
        all_fd = slice_fd.get(row["all_curve"], row["all_fd"])
        wkday_fd = all_fd - wk_fd
        wkday_below = all_pt["below"] - wk_pt["below"]

        checks = [
            ("all", row["all_pct"], all_pt["below"], all_fd, all_pt["pct_below"]),
            ("wkend", row["wkend_pct"], wk_pt["below"], wk_fd, wk_pt["pct_below"]),
            ("wkday", row["wkday_pct"], wkday_below, wkday_fd, None),
        ]
        for col, disp_pct, below, fd, curve_pct in checks:
            if fd <= 0:
                continue
            recomputed = fmt_pct_from_counts(below, fd)
            if abs(round_display(recomputed) - disp_pct) > TOL:
                issues.append(
                    f"WT {row['label']} {col}: displayed {disp_pct}% vs {below}/{fd}="
                    f"{recomputed:.4f}% (rounded {round_display(recomputed)}%)"
                )
            if curve_pct is not None and col != "wkday":
                if abs(round_display(curve_pct) - disp_pct) > TOL:
                    issues.append(
                        f"WT {row['label']} {col}: displayed {disp_pct}% vs curve {curve_pct}"
                    )

    # Ownership chart slices
    own = next(c for c in charts if c["id"] == "ownershipChart")
    for sl in own["slices"]:
        pt_all = lookup_curve(curves[sl["all_curve"]])
        wk_key = sl.get("wknd_curve") or sl.get("sat_curve")
        pt_wk = lookup_curve(curves[wk_key])
        wk_pct = sl.get("wknd_pct", sl.get("sat_pct"))
        for label, disp, pt in [("all", sl["all_pct"], pt_all), ("wknd", wk_pct, pt_wk)]:
            if abs(round_display(pt["pct_below"]) - disp) > TOL:
                issues.append(f"ownership chart {sl['label']} {label}: {disp}% vs curve {pt['pct_below']}")

    # County chart
    county = next(c for c in charts if c["id"] == "countyChart")
    county_curves = mode.get("curves_by_county", {})
    for i, label in enumerate(county["labels"]):
        disp = county["values"][i]
        key = county.get("county_keys", [None] * len(county["labels"]))[i]
        if key and key in county_curves:
            pt = lookup_curve(county_curves[key])
            if abs(round_display(pt["pct_below"]) - disp) > TOL:
                issues.append(f"county chart {label}: {disp}% vs curve {pt['pct_below']}")

    # Map legend
    sw = ui.get("mapLegendSwatches", [])
    low = ui.get("colorPctLow")
    mid = ui.get("colorPctMid")
    for s in sw:
        if "59.5" in s["label"] and "59.4" in s["label"]:
            issues.append(f"map legend inverted range: {s['label']} (low={low}, mid={mid})")
    if low and mid and low >= mid:
        issues.append(f"map legend thresholds inverted: low={low} mid={mid}")

    # Ownership slice totals (footnote documents intentional gap)
    for label, keys, total_key in [
        ("NY statewide ownership", ["ny_for_profit", "ny_non_profit", "ny_government"], "all_ny"),
        ("NYC ownership", ["nyc_for_profit", "nyc_non_profit", "nyc_government"], "nyc"),
    ]:
        total_pt = lookup_curve(curves[total_key])
        sum_below = sum(lookup_curve(curves[k])["below"] for k in keys)
        gap = total_pt["below"] - sum_below
        if gap and not ("Ownership coverage:" in html and "442" in html):
            issues.append(f"{label}: ownership slices below sum {sum_below} != total {total_pt['below']} (gap {gap})")

    # Statute cards
    fd_s = statute.get("facility_days_total", fd_total)
    for key, label in [("met_all_three", "met all three"), ("below_cna_side", "below CNA")]:
        block = statute.get(key, {})
        if block.get("days") and block.get("pct"):
            recomputed = round_display(100 * block["days"] / fd_s)
            if abs(recomputed - block["pct"]) > TOL:
                issues.append(f"statute {label}: {block['pct']}% vs {block['days']}/{fd_s}={recomputed}%")

    # Calendar extra
    for key in ("federal_holiday", "non_holiday"):
        block = calendar_extra.get(key, {})
        if block.get("below") and block.get("facility_days"):
            recomputed = round_display(fmt_pct_from_counts(block["below"], block["facility_days"]))
            if abs(recomputed - block["pct_below"]) > TOL:
                issues.append(f"calendar {key}: {block['pct_below']}% vs recompute {recomputed}%")

    # Scan all curve points at default threshold for pct_below vs below/fd drift
    weekend_cards = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards", [])}
    slice_fd = mode.get("slice_facility_days", {})
    for curve_key, curve in curves.items():
        try:
            pt = lookup_curve(curve)
        except KeyError:
            continue
        if curve_key.startswith("weekend"):
            fd = weekend_cards.get(curve_key, 0)
        elif curve_key in slice_fd:
            fd = slice_fd[curve_key]
        elif curve_key == "all_ny":
            fd = fd_total
        else:
            continue
        if fd <= 0:
            continue
        recomputed = fmt_pct_from_counts(pt["below"], fd)
        if abs(round_display(recomputed) - round_display(pt["pct_below"])) > TOL:
            issues.append(
                f"curve {curve_key}: pct_below {pt['pct_below']} vs {pt['below']}/{fd}="
                f"{recomputed:.4f}% (rounded {round_display(recomputed)}%)"
            )

    print("=== Pre-distribution audit ===\n")
    if issues:
        for i in issues:
            print(f"! {i}")
        return 1
    print("No issues found at tolerance", TOL, "pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
