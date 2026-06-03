#!/usr/bin/env python3
"""Audit prose and UI numbers in insights-ny-minimum-staffing.html against embedded JSON.

Verified from: insights-ny-minimum-staffing.html window.PBJ_REPORT_* blobs (2026-06-03 build).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
THRESHOLD = 3.5
TOL_PCT = 0.15  # allow 0.1 display rounding vs curve


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


def pct_close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL_PCT


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    issues: list[str] = []
    ok: list[str] = []

    interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
    charts = extract_json_after("window.PBJ_REPORT_CHARTS = ", html)
    facilities = extract_json_after("window.PBJ_REPORT_FACILITIES = ", html)

    statute = None
    if "window.PBJ_REPORT_NY_STATUTE = " in html:
        statute = extract_json_after("window.PBJ_REPORT_NY_STATUTE = ", html)
    calendar_extra = None
    if "window.PBJ_REPORT_CALENDAR_EXTRA = " in html:
        calendar_extra = extract_json_after("window.PBJ_REPORT_CALENDAR_EXTRA = ", html)

    mode = interactive["modes"]["total"]
    curves = mode["curves"]
    fd_total = mode["facility_days_total"]

    all_ny = lookup_curve(curves["all_ny"])
    if all_ny["below"] != 101779:
        issues.append(f"KPI below count: HTML 101779 vs curve {all_ny['below']}")
    else:
        ok.append("KPI below count 101779")
    if not pct_close(all_ny["pct_below"], 47.1):
        issues.append(f"KPI pct: HTML 47.1% vs curve {all_ny['pct_below']:.2f}%")
    else:
        ok.append("KPI share 47.1%")
    wknd = lookup_curve(curves["weekend"])
    if wknd["below"] != 47347:
        issues.append(f"weekend below: HTML 47347 vs curve {wknd['below']}")
    else:
        ok.append("weekend below count 47347")
    if not pct_close(wknd["pct_below"], 76.9):
        issues.append(f"weekend KPI: HTML 76.9% vs curve {wknd['pct_below']:.2f}%")
    else:
        ok.append("weekend KPI 76.9%")
    if fd_total != 216134:
        issues.append(f"facility_days_total {fd_total} != 216134")
    else:
        ok.append("facility_days_total 216134")
    if facilities["facility_count"] != 596:
        issues.append(f"facility_count {facilities['facility_count']} != 596")
    else:
        ok.append("facility_count 596")

    idx_35 = int(round((THRESHOLD - facilities["threshold_start"]) / facilities["threshold_step"]))
    fac_list = facilities["facilities"]
    every_day = sum(1 for f in fac_list if f["below_curve"][idx_35] >= f["facility_days"])
    at_least_90 = sum(1 for f in fac_list if f["below_curve"][idx_35] >= 0.9 * f["facility_days"])
    chronic_pct = round(100 * every_day / len(fac_list), 1)
    if every_day != 34:
        issues.append(f"facilities 100% days below: expected 34 vs {every_day}")
    else:
        ok.append("34 homes below minimum every day (5.7%)")
    if not pct_close(chronic_pct, 5.7):
        issues.append(f"100% days below share: prose 5.7% vs {chronic_pct}%")
    if at_least_90 != 95:
        issues.append(f"facilities >=90% days below: expected 95 vs {at_least_90}")
    else:
        ok.append("95 homes below minimum on >=90% of days")

    dow_spec = next(c for c in charts if c["id"] == "dowChart")
    dow_curves = mode["curves_by_dow"]
    for i, day in enumerate(dow_spec["dows"]):
        pt = lookup_curve(dow_curves[day])
        spec_val = dow_spec["values"][i]
        if not pct_close(pt["pct_below"], spec_val):
            issues.append(f"DOW {day}: chart spec {spec_val} vs curve {pt['pct_below']:.2f}")

    wed = lookup_curve(dow_curves["Wednesday"])["pct_below"]
    sun = lookup_curve(dow_curves["Sunday"])["pct_below"]
    spread = round(sun - wed, 1)
    if spread != 49.5:
        issues.append(f"DOW spread prose 49.5 vs computed {spread}")
    else:
        ok.append("DOW Wed–Sun spread 49.5 pp")

    own = next(c for c in charts if c["id"] == "ownershipChart")
    for sl in own["slices"]:
        pt_all = lookup_curve(curves[sl["all_curve"]])
        if not pct_close(pt_all["pct_below"], sl["all_pct"]):
            issues.append(f"ownership {sl['label']} all_pct {sl['all_pct']} vs curve {pt_all['pct_below']:.2f}")
        wk_key = sl.get("wknd_curve") or sl.get("sat_curve")
        pt_wk = lookup_curve(curves[wk_key])
        wk_pct = sl.get("wknd_pct", sl.get("sat_pct"))
        if not pct_close(pt_wk["pct_below"], wk_pct):
            issues.append(f"ownership {sl['label']} wknd {wk_pct} vs curve {pt_wk['pct_below']:.2f}")

    # Table rows in HTML (hard-coded)
    table_checks = [
        ("all_ny", 216134, 101779, 47.1),
        ("nyc_for_profit", 47172, 28335, 60.1),
        ("nyc_government", 1825, 99, 5.4),
    ]
    for curve_key, fd, below, pct in table_checks:
        pt = lookup_curve(curves[curve_key])
        if pt["below"] != below or not pct_close(pt["pct_below"], pct):
            issues.append(f"table {curve_key}: HTML {below}/{pct}% vs curve {pt['below']}/{pt['pct_below']:.2f}%")
        else:
            ok.append(f"table row {curve_key}")

    mo = mode["curves_by_month"]
    month_order = mode["month_order"]
    month_pcts = [lookup_curve(mo[m])["pct_below"] for m in month_order]
    apr = lookup_curve(mo["4"])["pct_below"]
    dec = lookup_curve(mo["12"])["pct_below"]
    if not pct_close(apr, 44.0):
        issues.append(f"April prose ~44% vs curve {apr:.2f}%")
    if not pct_close(dec, 50.0) and not pct_close(dec, 50.35):
        issues.append(f"December prose ~50% vs curve {dec:.2f}%")
    else:
        ok.append("monthly April/December band")

    if statute:
        fd_s = statute.get("facility_days_total", fd_total)
        met = statute.get("met_all_three", {})
        cna = statute.get("below_cna_side", {})
        if met.get("days") and fd_s:
            recomputed = round(100 * met["days"] / fd_s, 1)
            if not pct_close(recomputed, met.get("pct", 0)):
                issues.append(f"statute met_all_three pct {met.get('pct')} vs days/fd {recomputed}")
        if cna.get("days") and fd_s:
            recomputed = round(100 * cna["days"] / fd_s, 1)
            if not pct_close(recomputed, cna.get("pct", 0)):
                issues.append(f"statute below_cna pct {cna.get('pct')} vs days/fd {recomputed}")
        ok.append("PBJ_REPORT_NY_STATUTE embedded (round-trip checked)")
    else:
        issues.append("MISSING window.PBJ_REPORT_NY_STATUTE — statute cards 39.7% / 54.9% not in interactive JSON")

    if calendar_extra:
        hol = calendar_extra.get("federal_holiday", {})
        non = calendar_extra.get("non_holiday", {})
        if hol.get("pct_below") and not pct_close(hol["pct_below"], 52.0):
            issues.append(f"holiday pct embed {hol['pct_below']} vs prose 52%")
        if non.get("pct_below") and not pct_close(non["pct_below"], 47.0) and not pct_close(non["pct_below"], 47.1):
            issues.append(f"non-holiday pct embed {non['pct_below']} vs prose 47%")
        ok.append("PBJ_REPORT_CALENDAR_EXTRA embedded")
    else:
        issues.append("MISSING window.PBJ_REPORT_CALENDAR_EXTRA — holiday 52% / 47% not in curves")

    # 3.58 statewide ratio: not in interactive; cross-check state quarterly if present
    sq = ROOT / "state_quarterly_metrics.csv"
    if sq.exists():
        import pandas as pd

        df = pd.read_csv(sq)
        st_col = "STATE" if "STATE" in df.columns else "state"
        hprd_col = next((c for c in df.columns if "HPRD" in c.upper() and "TOTAL" in c.upper()), None)
        q_col = "CY_Qtr" if "CY_Qtr" in df.columns else "cy_qtr"
        if hprd_col:
            ny2025 = df[(df[st_col] == "NY") & df[q_col].astype(str).str.startswith("2025")]
            if not ny2025.empty:
                mean_hprd = ny2025[hprd_col].astype(float).mean()
                if abs(mean_hprd - 3.58) > 0.05:
                    issues.append(
                        f"prose statewide 3.58 vs mean NY 2025 quarterly {hprd_col}={mean_hprd:.3f} (cite quarter in methods)"
                    )
                else:
                    ok.append(f"statewide 3.58 ~ NY 2025 quarterly mean {mean_hprd:.3f}")

    print("=== NY minimum staffing math audit ===\n")
    print(f"OK ({len(ok)}):")
    for line in ok:
        print(f"  + {line}")
    print(f"\nISSUES ({len(issues)}):")
    for line in issues:
        print(f"  ! {line}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
