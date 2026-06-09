#!/usr/bin/env python3
"""Regenerate NY report embedded JSON + ownership table from quarter-aligned PBJ build.

Verified from: PBJapp/scripts/analyze_ny_minimum_staffing.py (_merge_days_provider_time_aware).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PBJAPP = ROOT.parent / "PBJapp"
if PBJAPP.exists() and str(PBJAPP) not in sys.path:
    sys.path.insert(0, str(PBJAPP))

from scripts.analyze_ny_minimum_staffing import (  # noqa: E402
    DEFAULT_INTERACTIVE_MODE,
    _export_facilities_table,
    _export_gis,
    _export_interactive,
    _export_quarterly_statutory,
    _load_ny_facility_days,
    _merge_days_provider_time_aware,
    _statute_ny_summary,
    _us_federal_holidays,
)

YEAR = 2025
THRESHOLD = 3.5
REPORT_DIR = PBJAPP / "docs" / "reports"
# Verified from: ny_minimum_staffing_2025_report.html is truncated at 2,621,440 bytes in PBJapp.
HTML_PATH = ROOT / "insights-ny-minimum-staffing.html"

OWNERSHIP_TABLE_CURVES = (
    ("all_ny", "slice-row-primary"),
    ("ny_for_profit", "slice-row-state"),
    ("ny_non_profit", "slice-row-state"),
    ("ny_government", "slice-row-state"),
    ("nyc", "slice-row-metro"),
    ("nyc_for_profit", "slice-row-child"),
    ("nyc_non_profit", "slice-row-child"),
    ("nyc_government", "slice-row-child"),
)

OWNERSHIP_CHART_SLICES = (
    ("All NY", "all_ny", "weekend"),
    ("NY statewide · for-profit", "ny_for_profit", "weekend_ny_for_profit"),
    ("NY statewide · non-profit", "ny_non_profit", "weekend_ny_non_profit"),
    ("NY statewide · government", "ny_government", "weekend_ny_government"),
    ("NYC (5 boroughs)", "nyc", "weekend_nyc"),
    ("NYC · for-profit", "nyc_for_profit", "weekend_nyc_for_profit"),
    ("NYC · non-profit", "nyc_non_profit", "weekend_ny_non_profit"),
    ("NYC · government", "nyc_government", "weekend_nyc_government"),
)

WEEKEND_TABLE_ROWS = (
    ("all_ny", "weekend"),
    ("ny_for_profit", "weekend_ny_for_profit"),
    ("nyc", "weekend_nyc"),
    ("nyc_for_profit", "weekend_nyc_for_profit"),
)


def default_mode(interactive: dict[str, Any]) -> dict[str, Any]:
    key = interactive.get("default_mode") or DEFAULT_INTERACTIVE_MODE
    modes = interactive.get("modes") or {}
    return modes.get(key) or modes.get(DEFAULT_INTERACTIVE_MODE) or modes["ny_mapped_non_admin_hprd"]


def update_hero_kpis(html: str, mode: dict[str, Any]) -> str:
    curves = mode["curves"]
    all_pt = lookup_curve(curves["all_ny"])
    wk_pt = lookup_curve(curves["weekend"])
    below = int(all_pt["below"])
    pct = round(float(all_pt["pct_below"]), 1)
    wk_pct = round(float(wk_pt["pct_below"]), 1)
    html = re.sub(
        r'(<span class="kpi-num-value">)[\d,]+(</span><span class="kpi-num-unit"> Days</span>)',
        rf"\g<1>{fmt_int(below)}\g<2>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<span class="kpi-num" aria-label="[\d.]+% percent"><span class="kpi-num-value">)[\d.]+%(</span>)',
        rf"\g<1>{pct}%\g<2>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<span class="kpi-num" aria-label="[\d.]+% weekend"><span class="kpi-num-value">)[\d.]+%(</span>)',
        rf"\g<1>{wk_pct}%\g<2>",
        html,
        count=1,
    )
    return html


def update_dow_chart(charts: list[dict[str, Any]], mode: dict[str, Any]) -> list[dict[str, Any]]:
    dow_curves = mode.get("curves_by_dow") or {}
    dows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for chart in charts:
        if chart.get("id") != "dowChart":
            continue
        values: list[float] = []
        facility_days: list[int] = []
        tooltips: list[str] = []
        for dow in dows:
            curve = dow_curves.get(dow) or []
            pt = lookup_curve(curve)
            fd = int((mode.get("curve_facility_days") or {}).get(f"dow:{dow}") or pt.get("below", 0))
            bl = int(pt["below"])
            pct = round(float(pt["pct_below"]), 1)
            values.append(pct)
            facility_days.append(fd)
            tooltips.append(f"{fmt_int(bl)} of {fmt_int(fd)} facility-days")
        chart["labels"] = labels
        chart["dows"] = dows
        chart["values"] = values
        chart["facility_days"] = facility_days
        chart["tooltips"] = tooltips
    return charts


def enrich_facilities_with_quarterly(
    facilities: dict[str, Any], quarterly_payload: dict[str, Any]
) -> dict[str, Any]:
    rollups = {
        str(r["ccn"]).zfill(6): r for r in quarterly_payload.get("facility_rollups", [])
    }
    for fac in facilities.get("facilities", []):
        ccn = str(fac.get("ccn", "")).zfill(6)
        roll = rollups.get(ccn, {})
        fac["qtrs_below_350"] = roll.get("qtrs_below_350_display", "")
        fac["qtrs_below_350_display"] = roll.get("qtrs_below_350_display", "")
        fac["qtrs_missing_floor_display"] = roll.get("qtrs_missing_floor_display", "")
        fac["qtrs_missing_any_floor"] = roll.get("qtrs_missing_floor_display", "")
        fac["quarters_below_350_total"] = roll.get("quarters_below_350_total")
        fac["quarters_missing_any_floor"] = roll.get("quarters_missing_any_floor")
    return facilities


def patch_window_var(html: str, var_name: str, payload: object) -> str:
    marker = f"window.{var_name} = "
    start = html.index(marker) + len(marker)
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return html[:start] + blob + html[j + 1 :]
    raise ValueError(f"unterminated JSON for {var_name}")


EMBED_CURVE_STEP = 0.05


def _downsample_curve(curve: list[dict[str, Any]], step: float = EMBED_CURVE_STEP) -> list[dict[str, Any]]:
    if not curve:
        return curve
    out: list[dict[str, Any]] = []
    for pt in curve:
        thr = round(float(pt["threshold"]), 2)
        if abs(round(thr / step) * step - thr) < 0.001:
            out.append(pt)
    return out or curve


def _downsample_curves_in_mode(mode: dict[str, Any]) -> None:
    for key in ("curves", "curves_by_dow", "curves_by_month", "curves_by_week", "curves_by_county"):
        block = mode.get(key)
        if not isinstance(block, dict):
            continue
        for curve_key, curve in list(block.items()):
            block[curve_key] = _downsample_curve(curve)


def _downsample_interactive_for_embed(interactive: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(interactive))
    for mode_key, mode in out.get("modes", {}).items():
        raw_mode = interactive["modes"][mode_key]
        for meta_key in (
            "label",
            "metric_key",
            "facility_days_total",
            "curve_facility_days",
            "weekend_cards",
            "histogram",
            "month_order",
        ):
            if meta_key in raw_mode:
                mode[meta_key] = raw_mode[meta_key]
        _downsample_curves_in_mode(mode)
    return out


def lookup_curve(curve: list[dict[str, Any]], threshold: float = THRESHOLD) -> dict[str, Any]:
    best = curve[0]
    best_dist = abs(float(best["threshold"]) - threshold)
    for row in curve[1:]:
        dist = abs(float(row["threshold"]) - threshold)
        if dist < best_dist:
            best = row
            best_dist = dist
    return best


def pct_class(pct: float) -> str:
    if pct <= 25:
        return "pct-low"
    if pct <= 50:
        return "pct-mid"
    return "pct-high"


def fmt_int(value: int) -> str:
    return f"{value:,}"


def update_ownership_table(html: str, mode: dict[str, Any]) -> str:
    curves = mode["curves"]
    cfd = mode.get("curve_facility_days") or {}
    for curve_key, _row_class in OWNERSHIP_TABLE_CURVES:
        curve = curves.get(curve_key)
        if not curve:
            continue
        pt = lookup_curve(curve)
        fd = int(cfd.get(curve_key) or mode["facility_days_total"])
        below = int(pt["below"])
        pct = round(float(pt["pct_below"]), 1)
        pattern = (
            rf'(<tr[^>]*data-curve="{re.escape(curve_key)}"[^>]*data-fd=")\d+(">.*?'
            rf'<td class="pct-cell pct-[^"]*">)[\d.]+%(</td><td class="below-cell">)[\d,]+'
            rf'(</td><td class="fd-cell">)[\d,]+(</td></tr>)'
        )
        repl = (
            rf"\g<1>{fd}\g<2>{pct:.1f}%\g<3>{fmt_int(below)}"
            rf"\g<4>{fmt_int(fd)}\g<5>"
        )
        html, n = re.subn(pattern, repl, html, count=1, flags=re.DOTALL)
        if n != 1:
            raise ValueError(f"ownership table row not updated for {curve_key}")
        html = re.sub(
            rf'(data-curve="{re.escape(curve_key)}"[^>]*>.*?<td class="pct-cell )pct-\w+',
            rf"\g<1>{pct_class(pct)}",
            html,
            count=1,
            flags=re.DOTALL,
        )
    return html


def update_ownership_charts(charts: list[dict[str, Any]], mode: dict[str, Any]) -> list[dict[str, Any]]:
    curves = mode["curves"]
    own = next(c for c in charts if c.get("id") == "ownershipChart")
    labels: list[str] = []
    slices: list[dict[str, Any]] = []
    for label, all_key, wknd_key in OWNERSHIP_CHART_SLICES:
        cfd = mode.get("curve_facility_days") or {}
        all_pt = lookup_curve(curves[all_key])
        wk_pt = lookup_curve(curves[wknd_key])
        all_fd = int(cfd.get(all_key) or all_pt["below"] or 1)
        wk_fd = int(cfd.get(wknd_key) or wk_pt["below"] or 1)
        labels.append(label)
        slices.append(
            {
                "label": label,
                "all_curve": all_key,
                "wknd_curve": wknd_key,
                "all_pct": round(100.0 * int(all_pt["below"]) / all_fd, 1) if all_fd else 0.0,
                "wknd_pct": round(100.0 * int(wk_pt["below"]) / wk_fd, 1) if wk_fd else 0.0,
            }
        )
    own["labels"] = labels
    own["slices"] = slices
    return charts


def _replace_wt_stat_block(
    row_html: str,
    stat_class: str,
    pct: float,
    below: int,
    fd: int,
    *,
    pct_class_name: str | None = None,
) -> str:
    pattern = (
        rf'<span class="wt-stat {re.escape(stat_class)}">'
        rf'<span class="wt-pct[^"]*">[\d.]+%</span>'
        rf'<span class="wt-count">[\d,]+/[\d,]+</span></span>'
    )
    pct_span = (
        f'<span class="wt-pct {pct_class_name}">{pct:.1f}%</span>'
        if pct_class_name
        else f'<span class="wt-pct">{pct:.1f}%</span>'
    )
    replacement = (
        f'<span class="wt-stat {stat_class}">{pct_span}'
        f'<span class="wt-count">{fmt_int(below)}/{fmt_int(fd)}</span></span>'
    )
    row_html, n = re.subn(pattern, replacement, row_html, count=1)
    if n != 1:
        raise ValueError(f"failed to update {stat_class} in weekend row")
    return row_html


def update_weekend_table(html: str, mode: dict[str, Any]) -> str:
    curves = mode["curves"]
    cfd = mode.get("curve_facility_days") or {}
    for all_key, wknd_key in WEEKEND_TABLE_ROWS:
        all_pt = lookup_curve(curves[all_key])
        wk_pt = lookup_curve(curves[wknd_key])
        all_fd = int(cfd.get(all_key) or mode["facility_days_total"])
        wk_fd = int(cfd.get(wknd_key) or all_fd)
        all_bl = int(all_pt["below"])
        wk_bl = int(wk_pt["below"])
        wkday_bl = all_bl - wk_bl
        wkday_fd = all_fd - wk_fd
        all_pct = round(float(all_pt["pct_below"]), 1)
        wk_pct = round(float(wk_pt["pct_below"]), 1)
        wkday_pct = round(100.0 * wkday_bl / wkday_fd, 1) if wkday_fd else 0.0

        row_pat = (
            rf'(<div class="wt-row[^"]*"[^>]*data-all-curve="{re.escape(all_key)}"'
            rf'[^>]*data-weekend-curve="{re.escape(wknd_key)}"[^>]*>.*?</div>)'
        )
        match = re.search(row_pat, html, flags=re.DOTALL)
        if not match:
            raise ValueError(f"weekend table row not found for {all_key}/{wknd_key}")
        row_html = match.group(1)
        row_html = _replace_wt_stat_block(
            row_html, "wt-stat--all", all_pct, all_bl, all_fd, pct_class_name=pct_class(all_pct)
        )
        row_html = _replace_wt_stat_block(row_html, "wt-stat--wkday", wkday_pct, wkday_bl, wkday_fd)
        row_html = _replace_wt_stat_block(
            row_html, "wt-stat--wkend", wk_pct, wk_bl, wk_fd, pct_class_name=pct_class(wk_pct)
        )
        html = html[: match.start(1)] + row_html + html[match.end(1) :]
    return html


def build_calendar_extra(merged, *, threshold: float = THRESHOLD) -> dict[str, Any]:
    """Verified from: analyze_ny_minimum_staffing federal_holidays block (NY-mapped total)."""
    import pandas as pd

    hprd_col = "hprd_ny_mapped_total"
    below = merged[hprd_col] < threshold
    work = pd.to_datetime(merged["work_date"]).dt.normalize()
    federal_dates = _us_federal_holidays(YEAR)
    is_hol = work.isin(pd.to_datetime(sorted(federal_dates)))
    hol_sub = below[is_hol]
    non_sub = below[~is_hol]
    n_hol = int(is_hol.sum())
    n_non = int((~is_hol).sum())
    hol_pct = round(100.0 * float(hol_sub.sum()) / n_hol, 1) if n_hol else 0.0
    non_pct = round(100.0 * float(non_sub.sum()) / n_non, 1) if n_non else 0.0
    return {
        "schema_version": 1,
        "threshold": threshold,
        "facility_days_total": int(len(merged)),
        "federal_holiday": {"pct_below": hol_pct},
        "non_holiday": {"pct_below": non_pct},
        "metric_mode": DEFAULT_INTERACTIVE_MODE,
        "built": "2026-06-08",
    }


def update_methods_copy(html: str) -> str:
    html = re.sub(
        r'<p class="definitions-disclaimer" role="note"><strong>Ownership coverage:</strong>.*?</p>\s*',
        "",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = html.replace(
        "<p>Ownership type and county come from <strong>CMS Provider Info</strong> "
        "(normalized snapshot, May 2026), joined to PBJ by CCN.</p>",
        "<p>Ownership and county are assigned from <strong>CMS Provider Info</strong> "
        "snapshots aligned to each PBJ quarter where available.</p>",
    )
    html = html.replace(
        "<p>Grouped ownership bars and the slice table use the same HPRD threshold as the toggle above. "
        "For-profit, non-profit, and government rows exclude facility-days where Provider Info lists ownership "
        "outside those three categories (442 days statewide at 3.50 HPRD in this build; 109 below minimum).</p>",
        "<p>Grouped ownership bars and the slice table use the same HPRD threshold as the toggle above.</p>",
    )
    html = html.replace(
        "<li>Ownership and county from <strong>CMS Provider Info</strong>, May 2026 snapshot. NYC = five boroughs.</li>",
        "<li>Ownership and county from <strong>CMS Provider Info</strong>, quarter-aligned snapshots. NYC = five boroughs.</li>",
    )
    html = html.replace(
        "<p><strong>Total nursing HPRD:</strong> (RN + LPN + CNA + Med Aide + NA trainee + RN DON + RN admin + LPN admin) ÷ MDS census, aligned with PBJ320 facility dashboard logic.</p>",
        "<p><strong>Primary NY-mapped HPRD (§ 2895-b default):</strong> (RN + LPN + CNA + Med Aide + NA trainee) ÷ MDS census. "
        "Excludes RN DON, RN admin, and LPN admin from the total and from the licensed-nurse floor.</p>",
    )
    html = html.replace(
        "<p><strong>NY statutory role floors (informative):</strong> <strong>CNA-side HPRD</strong> = CNA + Med Aide + NA trainee hours ÷ census (floor <strong>2.20</strong>). "
        "<strong>LPN/RN-side HPRD</strong> = RN + LPN + RN DON + RN admin + LPN admin ÷ census (floor <strong>1.10</strong>). "
        "Primary charts use <strong>total nursing HPRD</strong> (all roles, default benchmark 3.50). See <a href=\"#statute-sensitivity\">NY role floors</a> for counts below 2.20 / 1.10.</p>",
        "<p><strong>NY statutory role floors (informative):</strong> <strong>CNA-side HPRD</strong> = CNA + Med Aide + NA trainee ÷ census (floor <strong>2.20</strong>). "
        "<strong>Licensed-nurse HPRD</strong> = RN + LPN only ÷ census (floor <strong>1.10</strong>). "
        "Primary charts use the <strong>NY-mapped total</strong> (default benchmark 3.50). A comparison toggle shows the broader eight-role PBJ total. "
        "See <a href=\"#statute-sensitivity\">NY role floors</a> for counts below each mapped floor.</p>",
    )
    html = html.replace(
        "<p>One bar per weekday (Mon–Sun) for NY statewide facility-days with census &gt; 0. <strong>Below minimum</strong> at threshold <em>T</em>: share of that weekday&rsquo;s facility-days with total nursing HPRD strictly below <em>T</em>. Values come from precomputed day-of-week curves and update when you move the HPRD toggle.</p>",
        "<p>One bar per weekday (Mon–Sun) for NY statewide facility-days with census &gt; 0. <strong>Below minimum</strong> at threshold <em>T</em>: share of that weekday&rsquo;s facility-days with NY-mapped HPRD strictly below <em>T</em>. Values come from precomputed day-of-week curves and update when you move the HPRD toggle.</p>",
    )
    html = html.replace(
        "<dt>Total nursing HPRD</dt>\n          <dd>All nursing roles in the default metric ÷ census. Compared to floor <strong>3.50</strong> in this report.</dd>",
        "<dt>NY-mapped total HPRD</dt>\n          <dd>RN + LPN + CNA + Med Aide + NA trainee ÷ census. Compared to floor <strong>3.50</strong> in this report.</dd>",
    )
    html = html.replace(
        "<dt>LPN/RN-side HPRD</dt>\n          <dd>RN + LPN + RN DON + RN admin + LPN admin ÷ census. Floor <strong>1.10</strong> (NY statute).</dd>",
        "<dt>Licensed-nurse HPRD</dt>\n          <dd>RN + LPN only ÷ census. Floor <strong>1.10</strong> (NY statute mapping).</dd>",
    )
    html = html.replace(
        "<p><strong>Met all three</strong> — the day meets total, CNA-side, and LPN/RN-side floors together (AND). <strong>Below 2.20 CNA-side</strong> — CNA-side HPRD is strictly under 2.20 (a facility-day can miss CNA-side but not total HPRD, or the reverse).</p>",
        "<p><strong>Met all three</strong> — the day meets NY-mapped total, CNA-side, and licensed-nurse floors together (AND). "
        "<strong>Below 2.20 CNA-side</strong> — CNA-side HPRD is strictly under 2.20 (a facility-day can miss CNA-side but not total HPRD, or the reverse).</p>",
    )
    return html


def build_artifacts() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = REPORT_DIR / f"ny_minimum_{YEAR}_total"
    days = _load_ny_facility_days(YEAR, "total")
    merged = _merge_days_provider_time_aware(days, year=YEAR)

    interactive_path = stem.with_name(stem.name + "_interactive.json")
    facilities_path = stem.with_name(stem.name + "_facilities_table.json")
    counties_path = stem.with_name(stem.name + "_counties.json")
    quarterly_path = stem.with_name(stem.name + "_quarterly_statutory.json")

    _export_interactive(merged, year=YEAR, default_threshold=THRESHOLD, out_path=interactive_path)
    _export_facilities_table(merged, facilities_path, default_threshold=THRESHOLD)
    quarterly_payload = _export_quarterly_statutory(merged, quarterly_path, year=YEAR)
    statute_ny = _statute_ny_summary(merged)
    calendar_extra = build_calendar_extra(merged, threshold=THRESHOLD)
    _export_gis(
        merged,
        year=YEAR,
        metric="total",
        default_threshold=THRESHOLD,
        facilities_path=stem.with_name(stem.name + "_facilities.geojson"),
        counties_path=counties_path,
        counties_geojson_path=stem.with_name(stem.name + "_counties.geojson"),
    )

    interactive = json.loads(interactive_path.read_text(encoding="utf-8"))
    facilities = json.loads(facilities_path.read_text(encoding="utf-8"))
    facilities = enrich_facilities_with_quarterly(facilities, quarterly_payload)
    counties = json.loads(counties_path.read_text(encoding="utf-8"))
    quarterly = {
        "schema_version": 1,
        "year": YEAR,
        "summary": quarterly_payload.get("summary", {}),
    }
    return interactive, facilities, counties, quarterly, statute_ny, calendar_extra


def patch_html(
    html: str,
    interactive: dict[str, Any],
    facilities: dict[str, Any],
    charts: list[dict[str, Any]] | None,
    quarterly: dict[str, Any] | None = None,
    statute_ny: dict[str, Any] | None = None,
    calendar_extra: dict[str, Any] | None = None,
) -> str:
    mode = default_mode(interactive)
    html = patch_window_var(html, "PBJ_REPORT_INTERACTIVE", interactive)
    if "window.PBJ_REPORT_FACILITIES = " in html:
        html = patch_window_var(html, "PBJ_REPORT_FACILITIES", facilities)
    if quarterly is not None:
        if "window.PBJ_REPORT_QUARTERLY_STATUTORY = " in html:
            html = patch_window_var(html, "PBJ_REPORT_QUARTERLY_STATUTORY", quarterly.get("summary", {}))
        elif "window.PBJ_REPORT_QUARTERLY = " in html:
            html = patch_window_var(html, "PBJ_REPORT_QUARTERLY", quarterly)
        else:
            marker = "window.PBJ_REPORT_NY_STATUTE = "
            if marker in html:
                start = html.index(marker)
                insert = (
                    "window.PBJ_REPORT_QUARTERLY_STATUTORY = "
                    + json.dumps(quarterly.get("summary", {}), separators=(",", ":"), ensure_ascii=False)
                    + ";\n"
                )
                html = html[:start] + insert + html[start:]
    if statute_ny and "window.PBJ_REPORT_NY_STATUTE = " in html:
        html = patch_window_var(html, "PBJ_REPORT_NY_STATUTE", statute_ny)
    if calendar_extra is not None:
        if "window.PBJ_REPORT_CALENDAR_EXTRA = " in html:
            html = patch_window_var(html, "PBJ_REPORT_CALENDAR_EXTRA", calendar_extra)
        else:
            marker = "window.PBJ_REPORT_NY_STATUTE = "
            if marker in html:
                start = html.index(marker)
                insert = (
                    "window.PBJ_REPORT_CALENDAR_EXTRA = "
                    + json.dumps(calendar_extra, separators=(",", ":"), ensure_ascii=False)
                    + ";\n"
                )
                html = html[:start] + insert + html[start:]
    if charts is not None and "window.PBJ_REPORT_CHARTS = " in html:
        charts = update_ownership_charts(charts, mode)
        charts = update_dow_chart(charts, mode)
        html = patch_window_var(html, "PBJ_REPORT_CHARTS", charts)
    if 'id="ownership-slices-table"' in html:
        html = update_ownership_table(html, mode)
    if 'data-weekend-curve="weekend_nyc"' in html:
        html = update_weekend_table(html, mode)
    html = update_hero_kpis(html, mode)
    html = update_methods_copy(html)
    return html


def extract_charts(html: str) -> list[dict[str, Any]]:
    marker = "window.PBJ_REPORT_CHARTS = "
    start = html.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start : j + 1])
    raise ValueError("unterminated PBJ_REPORT_CHARTS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Build artifacts only; do not patch HTML")
    args = parser.parse_args()

    interactive_raw, facilities, counties, quarterly, statute_ny, calendar_extra = build_artifacts()
    interactive = _downsample_interactive_for_embed(interactive_raw)
    mode = default_mode(interactive)
    curves = mode["curves"]
    all_pt = lookup_curve(curves["all_ny"])
    qsum = quarterly.get("summary", {})
    print(
        "Built artifacts:",
        f"fd={mode['facility_days_total']:,}",
        f"ny_mapped_below={int(all_pt['below']):,}",
        f"ny_mapped_pct={float(all_pt['pct_below']):.1f}%",
        f"ny_for_profit={lookup_curve(curves['ny_for_profit'])['below']:,}",
        f"nyc={lookup_curve(curves['nyc'])['below']:,}",
        f"counties={len(counties.get('counties', []))}",
        f"facility_quarters={qsum.get('facility_quarters_analyzed', 0):,}",
    )

    if args.dry_run:
        return 0

    if not HTML_PATH.is_file():
        print(f"missing report HTML: {HTML_PATH}", file=sys.stderr)
        return 1

    html = HTML_PATH.read_text(encoding="utf-8")
    charts = extract_charts(html) if "window.PBJ_REPORT_CHARTS = " in html else None
    patched = patch_html(
        html, interactive, facilities, charts, quarterly, statute_ny, calendar_extra
    )
    HTML_PATH.write_text(patched, encoding="utf-8")
    print(f"Patched {HTML_PATH} ({HTML_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
