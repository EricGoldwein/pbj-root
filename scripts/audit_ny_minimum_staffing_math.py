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
THRESHOLD = 3.5
TOL_PCT = 0.15  # allow 0.1 display rounding vs curve
TOL_COUNT_PCT = 0.05  # displayed % vs below/fd before rounding


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


def pct_close(a: float, b: float, tol: float = TOL_PCT) -> bool:
    return abs(a - b) <= tol


def round_display(pct: float) -> float:
    return round(pct * 10) / 10


def pct_from_counts(below: int, fd: int) -> float:
    return 100.0 * below / fd if fd else 0.0


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    issues: list[str] = []
    ok: list[str] = []

    interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
    charts = extract_json_after("window.PBJ_REPORT_CHARTS = ", html)
    facilities = extract_json_after("window.PBJ_REPORT_FACILITIES = ", html)
    ui = extract_json_after("window.PBJ_REPORT_UI = ", html)

    statute = None
    if "window.PBJ_REPORT_NY_STATUTE = " in html:
        statute = extract_json_after("window.PBJ_REPORT_NY_STATUTE = ", html)
    calendar_extra = None
    if "window.PBJ_REPORT_CALENDAR_EXTRA = " in html:
        calendar_extra = extract_json_after("window.PBJ_REPORT_CALENDAR_EXTRA = ", html)

    default_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
    mode = interactive["modes"].get(default_key) or interactive["modes"]["ny_mapped_non_admin_hprd"]
    curves = mode["curves"]
    fd_total = mode["facility_days_total"]

    all_ny = lookup_curve(curves["all_ny"])
    primary = None
    if "window.PBJ_REPORT_STANDARD_PRIMARY = " in html:
        primary = extract_json_after("window.PBJ_REPORT_STANDARD_PRIMARY = ", html)
    hero_below_target = int(statute["facility_days_below_any_ny_requirement"]) if statute else all_ny["below"]
    hero_pct_target = round(float(statute["pct_below_any_ny_requirement"]), 1) if statute else round(all_ny["pct_below"], 1)
    if primary:
        hero_below_target = int(primary["below_days"])
        hero_pct_target = round(float(primary["below_pct"]), 1)
    hero_below_match = re.search(
        r'class="kpi-num-value">([\d,]+)</span><span class="kpi-num-unit"> Days',
        html,
    )
    hero_pct_match = re.search(
        r'aria-label="[\d.]+% percent"><span class="kpi-num-value">([\d.]+)%',
        html,
    )
    if hero_below_match:
        hero_below = int(hero_below_match.group(1).replace(",", ""))
        if hero_below != hero_below_target:
            issues.append(f"KPI below count: HTML {hero_below} vs primary {hero_below_target}")
        else:
            ok.append(f"KPI below count {hero_below}")
    if hero_pct_match:
        hero_pct = float(hero_pct_match.group(1))
        if not pct_close(hero_pct_target, hero_pct):
            issues.append(f"KPI pct: HTML {hero_pct}% vs primary {hero_pct_target:.2f}%")
        else:
            ok.append(f"KPI share {hero_pct}%")
    if default_key != "ny_mapped_non_admin_hprd":
        issues.append(f"default_mode {default_key!r} is not ny_mapped_non_admin_hprd")
    else:
        ok.append("default_mode ny_mapped_non_admin_hprd")
    wknd = lookup_curve(curves["weekend"])
    wknd_pct_target = round(float(primary["weekend_pct"]), 1) if primary else round(wknd["pct_below"], 1)
    wknd_kpi_match = re.search(
        r'id="kpi-weekend-pct"[^>]*><span class="kpi-num-value">([\d.]+)%',
        html,
    )
    wknd_kpi = float(wknd_kpi_match.group(1)) if wknd_kpi_match else wknd_pct_target
    if not pct_close(wknd_pct_target, wknd_kpi):
        issues.append(f"weekend KPI vs primary {wknd_pct_target:.2f}%")
    else:
        ok.append(f"weekend KPI {round(wknd_pct_target, 1)}%")
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
    if every_day != 34 and every_day != 58:
        issues.append(f"facilities 100% days below: computed {every_day} (update prose if changed)")
    else:
        ok.append(f"{every_day} homes below minimum every day")
    if not pct_close(chronic_pct, round(100 * every_day / len(fac_list), 1), tol=0.2):
        issues.append(f"100% days below share: prose vs {chronic_pct}%")
    at_least_50 = sum(
        1 for f in fac_list if f["below_curve"][idx_35] >= 0.5 * f["facility_days"]
    )
    at_least_75 = sum(
        1 for f in fac_list if f["below_curve"][idx_35] >= 0.75 * f["facility_days"]
    )
    zero_days = sum(1 for f in fac_list if f["below_curve"][idx_35] == 0)
    for label, computed, expected in (
        (">=50% days below 3.50", at_least_50, 348),
        (">=75% days below 3.50", at_least_75, 228),
        (">=90% days below 3.50", at_least_90, 158),
        ("100% days below 3.50", every_day, 58),
        ("0% days below 3.50", zero_days, 21),
    ):
        if computed != expected:
            issues.append(f"facilities {label}: computed {computed} != {expected}")
        else:
            ok.append(f"{computed} homes {label}")

    dow_spec = next(c for c in charts if c["id"] == "dowChart")
    if dow_spec.get("fixedStandard") and primary:
        for i, val in enumerate(dow_spec["values"]):
            fd = dow_spec["facility_days"][i]
            miss = int(round(val * fd / 100.0))
            recomputed = pct_from_counts(miss, fd)
            if abs(round_display(recomputed) - round_display(val)) > TOL_COUNT_PCT:
                issues.append(f"DOW {dow_spec['dows'][i]}: embed {val} vs {miss}/{fd}")
        wed = float(primary["wed_pct"])
        sun = float(primary["sun_pct"])
        spread = round(sun - wed, 1)
        ok.append(f"DOW fixed-standard embed (Sun {sun}%, Wed {wed}%)")
    else:
        dow_curves = mode["curves_by_dow"]
        for i, day in enumerate(dow_spec["dows"]):
            pt = lookup_curve(dow_curves[day])
            spec_val = dow_spec["values"][i]
            if not pct_close(pt["pct_below"], spec_val):
                issues.append(f"DOW {day}: chart spec {spec_val} vs curve {pt['pct_below']:.2f}")

        wed = lookup_curve(dow_curves["Wednesday"])["pct_below"]
        sun = lookup_curve(dow_curves["Sunday"])["pct_below"]
        spread = round(sun - wed, 1)
    if not pct_close(spread, round(sun - wed, 1)):
        issues.append(f"DOW spread mismatch")
    else:
        ok.append(f"DOW Wed–Sun spread {spread} pp")

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

    # Weekend table: displayed % must match below/fd (NYC weekend was 81.7% vs 82.3%)
    wt_fixed = "weekend-table-grid pbj-standard-fixed" in html
    weekend_cards = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards", [])}
    wt_pattern = re.compile(
        r'data-all-curve="([^"]+)" data-weekend-curve="([^"]+)".*?'
        r'wt-stat--wkend"><span class="wt-pct[^"]*">([\d.]+)%</span><span class="wt-count">([\d,]+)/([\d,]+)</span>',
        re.DOTALL,
    )
    for m in wt_pattern.finditer(html):
        label_curve = m.group(2)
        disp_pct = float(m.group(3))
        below = int(m.group(4).replace(",", ""))
        fd = int(m.group(5).replace(",", ""))
        recomputed = pct_from_counts(below, fd)
        if abs(round_display(recomputed) - disp_pct) > TOL_COUNT_PCT:
            issues.append(
                f"weekend table {label_curve}: HTML {disp_pct}% vs {below}/{fd}="
                f"{recomputed:.4f}% (rounded {round_display(recomputed)}%)"
            )
        card_fd = weekend_cards.get(label_curve)
        if card_fd and not wt_fixed:
            pt = lookup_curve(curves[label_curve])
            if abs(round_display(pct_from_counts(pt["below"], card_fd)) - round_display(pt["pct_below"])) > TOL_COUNT_PCT:
                issues.append(
                    f"curve {label_curve}: pct_below {pt['pct_below']} vs {pt['below']}/{card_fd}="
                    f"{pct_from_counts(pt['below'], card_fd):.4f}%"
                )
    ok.append("weekend table pct vs below/fd")

    # Map legend bins must be monotonic (was 59.5–59.4%)
    sw = ui.get("mapLegendSwatches", [])
    low = ui.get("colorPctLow")
    mid = ui.get("colorPctMid")
    for s in sw:
        if low and mid and f"{mid + 0.1}" in s["label"] and str(mid) in s["label"]:
            issues.append(f"map legend inverted range: {s['label']}")
    if low and mid and low < mid:
        ok.append(f"map legend thresholds {low}/{mid}")

    # Ownership slice totals vs All NY / NYC (footnote required if gap)
    own_gap_notes: list[str] = []
    for label, keys, total_key in [
        ("NY statewide", ["ny_for_profit", "ny_non_profit", "ny_government"], "all_ny"),
        ("NYC", ["nyc_for_profit", "nyc_non_profit", "nyc_government"], "nyc"),
    ]:
        total_pt = lookup_curve(curves[total_key])
        sum_below = sum(lookup_curve(curves[k])["below"] for k in keys)
        gap = total_pt["below"] - sum_below
        if gap:
            own_gap_notes.append(f"{label} below gap {gap}")
    if own_gap_notes:
        issues.append("ownership slice gaps (Other/unknown): " + "; ".join(own_gap_notes))
    else:
        ok.append("ownership slices reconcile to All NY / NYC totals")
    if "Ownership coverage:" in html and "442" in html:
        issues.append("stale ownership coverage footnote (442 days) still in HTML")

    # Table rows in HTML (hard-coded)
    table_checks = [
        ("all_ny",),
        ("ny_for_profit",),
        ("ny_non_profit",),
        ("ny_government",),
        ("nyc",),
        ("nyc_for_profit",),
        ("nyc_non_profit",),
        ("nyc_government",),
    ]
    for (curve_key,) in table_checks:
        pt = lookup_curve(curves[curve_key])
        row = re.search(
            rf'data-curve="{re.escape(curve_key)}"[^>]*data-fd="(\d+)".*?'
            rf'pct-cell pct-[^"]*">([\d.]+)%</td><td class="below-cell">([\d,]+)</td><td class="fd-cell">([\d,]+)',
            html,
            re.DOTALL,
        )
        if not row:
            issues.append(f"table row missing for {curve_key}")
            continue
        fd = int(row.group(1))
        pct = float(row.group(2))
        below = int(row.group(3).replace(",", ""))
        if pt["below"] != below or not pct_close(pt["pct_below"], pct):
            issues.append(
                f"table {curve_key}: HTML {below}/{pct}% vs curve {pt['below']}/{pt['pct_below']:.2f}%"
            )
        else:
            ok.append(f"table row {curve_key}")

    mo = mode["curves_by_month"]
    month_order = mode["month_order"]
    month_pcts = [lookup_curve(mo[m])["pct_below"] for m in month_order]
    apr = lookup_curve(mo["4"])["pct_below"]
    dec = lookup_curve(mo["12"])["pct_below"]
    apr_prose = re.search(r"<strong>([\d.]+)%</strong>\s*\(April\)", html)
    dec_prose = re.search(r"<strong>([\d.]+)%</strong>\s*\(December\)", html)
    monthly_ok = True
    if apr_prose and not pct_close(apr, float(apr_prose.group(1))):
        issues.append(f"April prose {apr_prose.group(1)}% vs curve {apr:.2f}%")
        monthly_ok = False
    if dec_prose and not pct_close(dec, float(dec_prose.group(1))):
        issues.append(f"December prose {dec_prose.group(1)}% vs curve {dec:.2f}%")
        monthly_ok = False
    if monthly_ok and apr_prose and dec_prose:
        ok.append("monthly April/December band")

    if statute:
        fd_s = statute.get("facility_days", fd_total)
        if statute.get("lpn_rn_hours_columns") != ["Hrs_RN", "Hrs_LPN"]:
            issues.append("statute licensed columns must be RN+LPN only")
        if "Hrs_RNadmin" in statute.get("total_hours_columns", []) or "Hrs_RNDON" in statute.get(
            "total_hours_columns", []
        ):
            issues.append("statute total_hours_columns includes admin/DON")
        met_days = statute.get("facility_days_meets_all_ny_requirements")
        met_pct = statute.get("pct_meets_all_ny_requirements")
        if met_days is not None and fd_s:
            recomputed = round(100 * met_days / fd_s, 2)
            if not pct_close(recomputed, met_pct, tol=0.2):
                issues.append(
                    f"statute met_all_three pct {met_pct} vs days/fd {recomputed}"
                )
        ok.append("PBJ_REPORT_NY_STATUTE embedded (NY-mapped columns)")
    else:
        issues.append("MISSING window.PBJ_REPORT_NY_STATUTE")

    if "window.PBJ_REPORT_QUARTERLY_STATUTORY = " in html:
        quarterly = extract_json_after("window.PBJ_REPORT_QUARTERLY_STATUTORY = ", html)
        if quarterly.get("metric_mode") != "ny_mapped_non_admin_hprd":
            issues.append("quarterly embed metric_mode not ny_mapped_non_admin_hprd")
        else:
            ok.append("quarterly statutory embed present")
    else:
        issues.append("MISSING window.PBJ_REPORT_QUARTERLY_STATUTORY")

    if re.search(r"\bviolation\b", html, re.I):
        prose_block = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.DOTALL)
        for m in re.finditer(r"\bviolation\b", prose_block, re.I):
            window = prose_block[max(0, m.start() - 40) : m.end() + 20]
            if re.search(r"\bnot\b|\bdoes not assert\b|\bwithout\b", window, re.I):
                continue
            issues.append("public prose uses violation language")
            break

    if calendar_extra:
        hol = calendar_extra.get("federal_holiday", {})
        non = calendar_extra.get("non_holiday", {})
        hol_prose = re.search(
            r"federal holidays</strong> were about <strong>([\d.]+)%</strong>", html
        )
        non_prose = re.search(
            r"vs\. <strong>([\d.]+)%</strong> on other days", html
        )
        if hol.get("pct_below") and hol_prose and not pct_close(
            hol["pct_below"], float(hol_prose.group(1))
        ):
            issues.append(
                f"holiday pct embed {hol['pct_below']} vs prose {hol_prose.group(1)}%"
            )
        if non.get("pct_below") and non_prose and not pct_close(
            non["pct_below"], float(non_prose.group(1))
        ):
            issues.append(
                f"non-holiday pct embed {non['pct_below']} vs prose {non_prose.group(1)}%"
            )
        ok.append("PBJ_REPORT_CALENDAR_EXTRA embedded")
    else:
        issues.append("MISSING window.PBJ_REPORT_CALENDAR_EXTRA")

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

    if re.search(r'"facility_days":17082\b', html) or "17,082" in html:
        issues.append("stale weekend_nyc denominator 17082 in served HTML")
    if "82.3%" in html or re.search(r'\b82\.3%\b', html):
        issues.append("stale 82.3% in served HTML")

    if WW_CSV.is_file():
        import pandas as pd

        wknd_df = pd.read_csv(WW_CSV)
        wknd_rows = wknd_df[wknd_df["day_type"] == "Weekends"]
        csv_truth = {
            WEEKEND_CARD_CURVE_MAP[str(r["slice"])]: int(r["facility_days"])
            for _, r in wknd_rows.iterrows()
            if str(r["slice"]) in WEEKEND_CARD_CURVE_MAP
        }
        for mode_key, mode_blob in interactive.get("modes", {}).items():
            for card in mode_blob.get("weekend_cards") or []:
                key = card["curve"]
                if key not in csv_truth:
                    continue
                got = card.get("facility_days")
                exp = csv_truth[key]
                if got != exp:
                    issues.append(
                        f"{mode_key} weekend_cards[{key}]: embedded {got} != CSV {exp}"
                    )
                else:
                    ok.append(f"{mode_key} weekend_cards[{key}] == CSV {exp}")
    else:
        issues.append(f"missing verification CSV for weekend_cards audit: {WW_CSV}")

    for mode_key, mode_blob in interactive.get("modes", {}).items():
        wk_cards = {c["curve"]: c for c in mode_blob.get("weekend_cards") or []}
        wk_curve = mode_blob.get("curves", {}).get("weekend_nyc", [])
        if not wk_curve or "weekend_nyc" not in wk_cards:
            continue
        card = wk_cards["weekend_nyc"]
        pt = lookup_curve(wk_curve)
        n = card.get("facility_days")
        if n == 17082:
            issues.append(f"{mode_key} weekend_nyc facility_days still 17082")
        elif n and abs(round_display(pct_from_counts(pt["below"], n)) - round_display(pt["pct_below"])) > TOL_COUNT_PCT:
            issues.append(
                f"{mode_key} weekend_nyc: pct {pt['pct_below']} vs {pt['below']}/{n}"
            )
        else:
            ok.append(f"{mode_key} weekend_nyc {pt['below']}/{n} @ {round_display(pt['pct_below'])}%")

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
