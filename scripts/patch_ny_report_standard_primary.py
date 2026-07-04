#!/usr/bin/env python3
"""Promote NY full standard (miss any mapped floor) as primary daily metric.

Verified from: public/downloads/.../daily_facility_data.csv (below_350_direct_care, etc.).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
CSV = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs" / "daily_facility_data.csv"

DOWS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _truthy(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(("true", "1", "yes"))


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _load_daily_frame() -> pd.DataFrame:
    if not CSV.is_file():
        raise FileNotFoundError(CSV)
    d = pd.read_csv(CSV, dtype=str)
    below_350_col = "below_350_direct_care" if "below_350_direct_care" in d.columns else "below_350_ny_mapped"
    met_all_col = (
        "met_all_three_direct_care"
        if "met_all_three_direct_care" in d.columns
        else "met_all_three_ny_mapped"
    )
    d["miss_any"] = (
        _truthy(d[below_350_col])
        | _truthy(d["below_220_cna_side"])
        | _truthy(d["below_110_licensed"])
    )
    d["below_350"] = _truthy(d[below_350_col])
    d["met_all"] = _truthy(d[met_all_col])
    d["weekend"] = d["day_of_week"].isin(["Saturday", "Sunday"])
    d["nyc"] = d["nyc_flag"].astype(str).str.lower().eq("true")
    return d


def compute_standard_metrics() -> dict:
    return _build_standard_metrics(_load_daily_frame())


def _build_standard_metrics(d: pd.DataFrame) -> dict:
    fd = len(d)
    miss = int(d["miss_any"].sum())
    below350 = int(d["below_350"].sum())
    met_all = int(d["met_all"].sum())
    wk = d[d["weekend"]]
    wk_fd = len(wk)
    wk_miss = int(wk["miss_any"].sum())

    dow_values: list[float] = []
    dow_fds: list[int] = []
    dow_tooltips: list[str] = []
    for dow in DOWS:
        sub = d[d["day_of_week"] == dow]
        sub_fd = len(sub)
        sub_miss = int(sub["miss_any"].sum())
        pct = round(100.0 * sub_miss / sub_fd, 1) if sub_fd else 0.0
        dow_values.append(pct)
        dow_fds.append(sub_fd)
        dow_tooltips.append(f"{_fmt_int(sub_miss)} of {_fmt_int(sub_fd)} facility-days")

    sun = d[d["day_of_week"] == "Sunday"]
    wed = d[d["day_of_week"] == "Wednesday"]
    sun_pct = round(100.0 * int(sun["miss_any"].sum()) / len(sun), 1)
    wed_pct = round(100.0 * int(wed["miss_any"].sum()) / len(wed), 1)
    spread = round(sun_pct - wed_pct, 1)

    def slice_miss(mask: pd.Series) -> tuple[int, int, float]:
        sub = d.loc[mask]
        sfd = len(sub)
        sm = int(sub["miss_any"].sum())
        sp = round(100.0 * sm / sfd, 1) if sfd else 0.0
        return sm, sfd, sp

    def slice_weekend_miss(mask: pd.Series) -> tuple[int, int, float]:
        sub = d.loc[mask & d["weekend"]]
        sfd = len(sub)
        sm = int(sub["miss_any"].sum())
        sp = round(100.0 * sm / sfd, 1) if sfd else 0.0
        return sm, sfd, sp

    cna_miss = int(_truthy(d["below_220_cna_side"]).sum())
    cna_pct = round(100.0 * cna_miss / fd, 1)

    masks = {
        "all_ny": pd.Series(True, index=d.index),
        "ny_for_profit": d["ownership_type"].str.lower() == "for-profit",
        "nyc": d["nyc"],
        "nyc_for_profit": d["nyc"] & (d["ownership_type"].str.lower() == "for-profit"),
    }
    wt_slices: dict[str, dict[str, tuple[int, int, float]]] = {}
    for key, mask in masks.items():
        sm, sfd, sp = slice_miss(mask)
        wsm, wsfd, wsp = slice_weekend_miss(mask)
        wt_slices[key] = {"all": (sm, sfd, sp), "weekend": (wsm, wsfd, wsp)}

    return {
        "facility_days": fd,
        "miss_any": miss,
        "miss_pct": round(100.0 * miss / fd, 1),
        "below_350": below350,
        "below_350_pct": round(100.0 * below350 / fd, 1),
        "met_all": met_all,
        "met_all_pct": round(100.0 * met_all / fd, 1),
        "cna_miss_pct": cna_pct,
        "weekend_miss": wk_miss,
        "weekend_fd": wk_fd,
        "weekend_miss_pct": round(100.0 * wk_miss / wk_fd, 1),
        "dow_values": dow_values,
        "dow_fds": dow_fds,
        "dow_tooltips": dow_tooltips,
        "sun_pct": sun_pct,
        "wed_pct": wed_pct,
        "spread": spread,
        "wt_slices": wt_slices,
    }


def _curve_point(sub: pd.DataFrame) -> dict[str, float | int]:
    fd = len(sub)
    miss = int(sub["miss_any"].sum())
    pct = round(100.0 * miss / fd, 2) if fd else 0.0
    return {"below": miss, "pct_below": pct, "facility_days": fd}


def compute_standard_scenario_curves(d: pd.DataFrame) -> dict:
    """Miss-any curves at fixed NY floors for scenario toggle (Direct Care only)."""
    own = d["ownership_type"].astype(str).str.lower()
    wk = d["weekend"]
    nyc = d["nyc"]

    def mask(key: str) -> pd.Series:
        if key == "all_ny":
            return pd.Series(True, index=d.index)
        if key == "ny_for_profit":
            return own.eq("for-profit")
        if key == "ny_non_profit":
            return own.eq("non-profit")
        if key == "ny_government":
            return own.eq("government")
        if key == "nyc":
            return nyc
        if key == "nyc_for_profit":
            return nyc & own.eq("for-profit")
        if key == "nyc_non_profit":
            return nyc & own.eq("non-profit")
        if key == "nyc_government":
            return nyc & own.eq("government")
        if key == "weekend":
            return wk
        if key == "weekend_ny_for_profit":
            return wk & own.eq("for-profit")
        if key == "weekend_ny_non_profit":
            return wk & own.eq("non-profit")
        if key == "weekend_ny_government":
            return wk & own.eq("government")
        if key == "weekend_nyc":
            return wk & nyc
        if key == "weekend_nyc_for_profit":
            return wk & nyc & own.eq("for-profit")
        if key == "weekend_nyc_non_profit":
            return wk & nyc & own.eq("non-profit")
        if key == "weekend_nyc_government":
            return wk & nyc & own.eq("government")
        raise KeyError(key)

    curves = {key: _curve_point(d.loc[mask(key)]) for key in (
        "all_ny", "ny_for_profit", "ny_non_profit", "ny_government",
        "nyc", "nyc_for_profit", "nyc_non_profit", "nyc_government",
        "weekend", "weekend_ny_for_profit", "weekend_ny_non_profit", "weekend_ny_government",
        "weekend_nyc", "weekend_nyc_for_profit", "weekend_nyc_non_profit", "weekend_nyc_government",
    )}

    curves_by_dow = {dow: _curve_point(d.loc[d["day_of_week"] == dow]) for dow in DOWS}

    curves_by_month: dict[str, dict] = {}
    months = pd.to_numeric(d["month"], errors="coerce")
    for mo in range(1, 13):
        curves_by_month[str(mo)] = _curve_point(d.loc[months == mo])

    curves_by_county: dict[str, dict] = {}
    for county in sorted(d["county"].dropna().astype(str).unique()):
        curves_by_county[county] = _curve_point(d.loc[d["county"].astype(str) == county])

    return {
        "threshold": 3.5,
        "below_test": "ny_standard_miss_any",
        "curves": curves,
        "curves_by_dow": curves_by_dow,
        "curves_by_month": curves_by_month,
        "curves_by_county": curves_by_county,
    }


def _patch_window_var(html: str, var_name: str, payload: object) -> str:
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
    raise ValueError(var_name)


def _extract_json_after(html: str, marker: str) -> object:
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
    raise ValueError(marker)


def _patch_dow_chart_embed(html: str, m: dict) -> str:
    charts = _extract_json_after(html, "window.PBJ_REPORT_CHARTS = ")
    for chart in charts:
        if chart.get("id") != "dowChart":
            continue
        chart["values"] = m["dow_values"]
        chart["facility_days"] = m["dow_fds"]
        chart["tooltips"] = m["dow_tooltips"]
        chart["fixedStandard"] = True
        chart["metric"] = "ny_standard_miss_any"
        chart["yMin"] = max(0, min(m["dow_values"]) - 4)
        chart["yMax"] = min(100, max(m["dow_values"]) + 6)
        break
    return _patch_window_var(html, "PBJ_REPORT_CHARTS", charts)


def _pct_class(p: float) -> str:
    if p > 59.4:
        return "pct-high"
    if p > 31.7:
        return "pct-mid"
    return "pct-low"


def _fill_wt_row(
    html: str,
    curve: str,
    all_sm: int,
    all_sfd: int,
    all_sp: float,
    wk_sm: int,
    wk_sfd: int,
    wk_sp: float,
) -> str:
    wkday_fd = max(0, all_sfd - wk_sfd)
    wkday_sm = max(0, all_sm - wk_sm)
    wkday_sp = round(100.0 * wkday_sm / wkday_fd, 1) if wkday_fd else 0.0
    stats = (
        f'<span class="wt-stat wt-stat--all"><span class="wt-pct {_pct_class(all_sp)}">{all_sp}%</span>'
        f'<span class="wt-count">{_fmt_int(all_sm)}/{_fmt_int(all_sfd)}</span></span>'
        f'<span class="wt-stat wt-stat--wkday"><span class="wt-pct">{wkday_sp}%</span>'
        f'<span class="wt-count">{_fmt_int(wkday_sm)}/{_fmt_int(wkday_fd)}</span></span>'
        f'<span class="wt-stat wt-stat--wkend"><span class="wt-pct {_pct_class(wk_sp)}">{wk_sp}%</span>'
        f'<span class="wt-count">{_fmt_int(wk_sm)}/{_fmt_int(wk_sfd)}</span></span>'
    )
    pattern = (
        rf'(<div class="wt-row[^"]*"[^>]*data-all-curve="{re.escape(curve)}"[^>]*>\s*'
        rf'<span class="wt-row-label">[^<]*</span>\s*)'
        rf'(?:<span class="wt-stat wt-stat--all">.*?</span>\s*'
        rf'<span class="wt-stat wt-stat--wkday">.*?</span>\s*'
        rf'<span class="wt-stat wt-stat--wkend">.*?</span>'
        rf'(?:\s*<span class="wt-count">.*?</span>\s*</span>\s*)*)'
    )
    return re.sub(pattern, rf"\1{stats}", html, count=1, flags=re.DOTALL)


def patch_html() -> dict:
    d = _load_daily_frame()
    m = _build_standard_metrics(d)
    standard_scenario = compute_standard_scenario_curves(d)
    html = HTML.read_text(encoding="utf-8")

    html = _patch_dow_chart_embed(html, m)

    primary_embed = {
        "below_days": m["miss_any"],
        "below_pct": m["miss_pct"],
        "weekend_pct": m["weekend_miss_pct"],
        "weekend_below": m["weekend_miss"],
        "weekend_fd": m["weekend_fd"],
        "below_350_days": m["below_350"],
        "below_350_pct": m["below_350_pct"],
        "met_all_pct": m["met_all_pct"],
        "cna_miss_pct": m["cna_miss_pct"],
        "sun_pct": m["sun_pct"],
        "wed_pct": m["wed_pct"],
    }
    if "window.PBJ_REPORT_STANDARD_PRIMARY = " in html:
        html = _patch_window_var(html, "PBJ_REPORT_STANDARD_PRIMARY", primary_embed)
    else:
        html = html.replace(
            "window.PBJ_REPORT_CALENDAR_EXTRA = ",
            "window.PBJ_REPORT_STANDARD_PRIMARY = "
            + json.dumps(primary_embed, separators=(",", ":"), ensure_ascii=False)
            + ";\nwindow.PBJ_REPORT_CALENDAR_EXTRA = ",
            1,
        )

    if "window.PBJ_REPORT_STANDARD_SCENARIO = " in html:
        html = _patch_window_var(html, "PBJ_REPORT_STANDARD_SCENARIO", standard_scenario)
    else:
        html = html.replace(
            "window.PBJ_REPORT_STANDARD_PRIMARY = ",
            "window.PBJ_REPORT_STANDARD_SCENARIO = "
            + json.dumps(standard_scenario, separators=(",", ":"), ensure_ascii=False)
            + ";\nwindow.PBJ_REPORT_STANDARD_PRIMARY = ",
            1,
        )

    methods_primary = (
        "<p><strong>Primary daily metric:</strong> miss <strong>any</strong> mapped part of the NY standard "
        "(3.50 total + 2.20 CNA-side + 1.10 licensed). Hero KPIs, the day-of-week chart, and the weekend breakdown "
        "table use that full standard and do not follow scenario controls.</p>\n        "
        "<p><strong>Scenario charts (3.50 component):</strong> ownership, county, provider, calendar, and map sections "
        "use the <strong>NY-mapped total HPRD</strong> at the selected PBJ Standard threshold (default "
        "<strong>3.50</strong>). The <strong>3.50 total component</strong> is a subset of the full standard&mdash;"
        "days can miss a role floor while still meeting 3.50 total, or vice versa.</p>"
    )
    if "Primary daily metric:" not in html:
        html = html.replace(
            "<p><strong>NY statutory role floors (informative):</strong>",
            methods_primary + "\n        <p><strong>NY statutory role floors (informative):</strong>",
            1,
        )
    html = re.sub(
        r"Primary threshold: <strong>3\.50 HPRD</strong> \(report default\)\.",
        "Scenario default threshold: <strong>3.50 HPRD</strong> (3.50 total component).",
        html,
        count=1,
    )

    if "var primary = global.PBJ_REPORT_STANDARD_PRIMARY;" not in html:
        html = re.sub(
            r"function updateKpis\(threshold\) \{[\s\S]*?\n  \}\n\n  function sliceFacilityDays",
            """function updateKpis(threshold) {
    var primary = global.PBJ_REPORT_STANDARD_PRIMARY;
    var strip = document.querySelector('.kpi-strip');
    if (!strip) return;
    var nums = strip.querySelectorAll('.kpi-num');
    if (primary && nums.length >= 2) {
      var v0 = nums[0].querySelector('.kpi-num-value') || nums[0];
      var v1 = nums[1].querySelector('.kpi-num-value') || nums[1];
      v0.textContent = fmtInt(primary.below_days);
      nums[0].setAttribute('aria-label', fmtInt(primary.below_days) + ' days');
      v1.textContent = fmtPct(primary.below_pct) + '%';
      nums[1].setAttribute('aria-label', fmtPct(primary.below_pct) + ' percent');
      var wkEl = document.getElementById('kpi-weekend-pct');
      if (wkEl) {
        var wkVal = wkEl.querySelector('.kpi-num-value') || wkEl;
        wkVal.textContent = fmtPct(primary.weekend_pct) + '%';
        wkEl.setAttribute('aria-label', fmtPct(primary.weekend_pct) + ' percent weekend');
      }
    }
    var labels = strip.querySelectorAll('.kpi-label');
    function setKpiLabels(labelEl, longText, shortText) {
      if (!labelEl) return;
      var longEl = labelEl.querySelector('.kpi-label-long');
      var shortEl = labelEl.querySelector('.kpi-label-short');
      if (longEl) longEl.textContent = longText;
      if (shortEl) shortEl.textContent = shortText;
    }
    if (labels.length >= 1) {
      setKpiLabels(labels[0], 'Days below NY standard', 'Days below std');
    }
    if (labels.length >= 2) {
      setKpiLabels(labels[1], 'Share of days below standard', 'NY days below std');
    }
    if (labels.length >= 3) {
      setKpiLabels(labels[2], 'Weekend days below standard', 'Wknd below std');
    }
    strip.classList.toggle('kpi-strip--scenario', false);
  }

  function sliceFacilityDays""",
            html,
            count=1,
        )

    if "var grid = document.querySelector('.weekend-table-grid.pbj-standard-fixed');" not in html:
        html = html.replace(
            "  function updateWtBreakdownRows(threshold) {\n    var I = modeData();",
            "  function updateWtBreakdownRows(threshold) {\n    var grid = document.querySelector('.weekend-table-grid.pbj-standard-fixed');\n    if (grid) return;\n    var I = modeData();",
            1,
        )

    html = re.sub(
        r"<h1>.*?</h1>",
        (
            f"<h1>New York nursing homes missed at least one part of the state&rsquo;s daily staffing "
            f"standard on <em>{m['miss_pct']}%</em> of facility-days in 2025.</h1>"
        ),
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = re.sub(
        r'(<span class="kpi-num" aria-label=")[^"]*("><span class="kpi-num-value">)[\d,]+(</span><span class="kpi-num-unit"> Days</span></span>\s*)'
        r'(<span class="kpi-label"><span class="kpi-label-long">)[^<]+(</span><span class="kpi-label-short">)[^<]+(</span></span>)',
        rf"\g<1>{m['miss_any']:,} days\g<2>{_fmt_int(m['miss_any'])}\g<3>"
        rf"\g<4>Days below NY standard\g<5>Days below std\g<6>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<span class="kpi-num" aria-label=")[\d.]+% percent("><span class="kpi-num-value">)[\d.]+%(</span></span>)',
        rf"\g<1>{m['miss_pct']}% percent\g<2>{m['miss_pct']}%\g<3>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<span class="kpi-num" id="kpi-weekend-pct" aria-label=")[^"]*("><span class="kpi-num-value">)[\d.]+%(</span>)',
        rf"\g<1>{m['weekend_miss_pct']}% percent weekend\g<2>{m['weekend_miss_pct']}%\g<3>",
        html,
        count=1,
    )

    heading = (
        "Nearly two-thirds of NY facility-days missed part of the staffing standard"
        if m["miss_pct"] >= 60
        else "More than half of NY facility-days missed part of the staffing standard"
    )
    html = re.sub(
        r'<h2 id="definitions-heading">.*?</h2>',
        f'<h2 id="definitions-heading">{heading}</h2>',
        html,
        count=1,
    )

    callout = (
        f'<p class="standard-primary-callout" role="note">'
        f"<strong>NY daily standard</strong> (N.Y. PHL &sect;&nbsp;2895-b): "
        f"<strong>3.50</strong> total + <strong>2.20</strong> CNA-side + <strong>1.10</strong> licensed nurse HPRD. "
        f"Only <strong>{m['met_all_pct']}%</strong> of days met all three; "
        f"<strong>{m['cna_miss_pct']}%</strong> missed the CNA-side floor. "
        f'<button type="button" class="statute-modal-trigger standard-callout-link" '
        f'data-statute-modal-open="ny-standard-compliance" aria-haspopup="dialog">How NY defines compliance</button>'
        f"</p>"
        f'<p class="standard-component-note" role="note">'
        f"<strong>3.50 total component:</strong> {_fmt_int(m['below_350'])} facility-days "
        f"({m['below_350_pct']}%) fell below the 3.50 HPRD total alone. Scenario charts explore that component."
        f"</p>"
    )

    if "standard-primary-callout" not in html:
        html = html.replace(
            '<section id="definitions" aria-labelledby="definitions-heading">',
            '<section id="definitions" aria-labelledby="definitions-heading">',
            0,
        )
        html = re.sub(
            r'(<section id="definitions"[\s\S]*?<h2 id="definitions-heading">[^<]+</h2>\s*)',
            r"\1" + callout + "\n    ",
            html,
            count=1,
        )
    else:
        html = re.sub(
            r'<p class="standard-primary-callout"[^>]*>.*?</p>\s*<p class="standard-component-note"[^>]*>.*?</p>',
            callout,
            html,
            count=1,
            flags=re.DOTALL,
        )

    scope1 = (
        "New York&rsquo;s nursing home staffing standard has <strong>three parts per day</strong>: "
        "<strong>3.50</strong> total hours per resident day, including at least <strong>2.20</strong> CNA-side "
        "and <strong>1.10</strong> licensed-nurse HPRD. Though compliance is determined "
        "<strong>quarterly</strong> under state law, this report uses federal "
        "<strong>Payroll-Based Journal (PBJ)</strong> data&mdash;one record per nursing home per calendar day&mdash;"
        "to show how often daily staffing <strong>missed any part of that standard</strong>."
    )
    scope2 = (
        f"In 2025, nursing homes missed at least one mapped part of the standard on "
        f"<strong>{_fmt_int(m['miss_any'])} facility-days &mdash; {m['miss_pct']}% of all daily records analyzed</strong>. "
        f"Weekend gaps were wider: <strong>{m['weekend_miss_pct']}% of Saturday and Sunday records</strong> missed at least "
        f"one floor. Shortfalls varied by ownership and region. "
        f"These are descriptive PBJ mappings, not NY DOH enforcement determinations."
    )
    html = re.sub(
        r'<p class="report-scope-note">.*?</p>\s*<p class="report-scope-note">.*?</p>',
        f'<p class="report-scope-note">{scope1}</p>\n    <p class="report-scope-note">{scope2}</p>',
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = re.sub(
        r'<div class="report-modal-actions" role="group" aria-label="Reference">.*?</div>',
        '''<div class="report-modal-actions" role="group" aria-label="Reference">
      <button type="button" class="statute-modal-trigger" data-statute-modal-open="ny-standard-compliance" aria-haspopup="dialog" aria-label="NY staffing standard and compliance"><span class="modal-trigger-label-long">NY Standard &amp; Compliance</span><span class="modal-trigger-label-short">NY Standard</span></button>
      <button type="button" class="statute-modal-trigger" data-statute-modal-open="ny-doh-statute" aria-haspopup="dialog" aria-label="NY DOH minimum staffing summary"><span class="modal-trigger-label-long">NY DOH Summary</span><span class="modal-trigger-label-short">NY DOH</span></button>
      <button type="button" class="statute-modal-trigger definitions-modal-trigger" data-statute-modal-open="chart-definitions" aria-haspopup="dialog" aria-label="Methods summary"><span class="modal-trigger-label-long">Methods</span><span class="modal-trigger-label-short">Methodology</span></button>
      <button type="button" class="statute-modal-trigger pick-standard-trigger" data-statute-modal-open="pick-your-standard" aria-haspopup="dialog" aria-label="Pick your PBJ standard"><img src="/pbj_favicon.png" width="14" height="14" alt="" class="modal-trigger-favicon" decoding="async" aria-hidden="true"><span class="modal-trigger-label-long">Pick Your PBJ Standard</span><span class="modal-trigger-label-short">PBJ Standard</span></button>
    </div>''',
        html,
        count=1,
        flags=re.DOTALL,
    )

    compliance_modal = '''
    <dialog id="ny-standard-compliance" class="pbj-statute-dialog" aria-labelledby="ny-standard-compliance-title">
      <div class="pbj-statute-dialog-inner">
        <header class="pbj-statute-dialog-header">
          <h3 id="ny-standard-compliance-title">NY Staffing Standard &amp; Compliance</h3>
          <button type="button" class="pbj-statute-dialog-close" data-statute-modal-close aria-label="Close">&times;</button>
        </header>
        <div class="pbj-statute-dialog-body">
          <p><strong>N.Y. Public Health Law &sect;&nbsp;2895-b</strong> requires every nursing home to provide, on each day, at least <strong>3.5 hours of care per resident per day</strong> by a certified nurse aide, licensed practical nurse, or registered nurse, including at least <strong>2.2 hours</strong> from a CNA and at least <strong>1.1 hours</strong> from a licensed nurse.</p>
          <p><strong>Full standard on a facility-day:</strong> meet all three mapped parts together (AND). In this report, a day counts as <strong>below the standard</strong> when PBJ-mapped staffing misses <strong>any</strong> of the three floors&mdash;not when only a quarterly average looks adequate.</p>
          <p><strong>Quarterly enforcement:</strong> DOH determines compliance on a <strong>quarterly basis</strong> using CMS PBJ data. A facility can log many daily shortfalls in PBJ while still facing a separate quarterly compliance test; conversely, daily PBJ mapping here is <strong>not</strong> a formal violation finding.</p>
          <p class="statute-modal-penalties"><strong>Penalties (statute):</strong> civil penalties up to <strong>$2,000 per day</strong> for each day in a quarter out of compliance, subject to mitigating factors&mdash;extraordinary circumstances, acute regional labor shortage, or a verifiable union dispute.</p>
          <p><strong>PBJ320 mapping (default):</strong> total and licensed floors use RN + LPN + CNA + Med Aide + NA trainee; excludes RN DON, RN admin, and LPN admin. CNA-side uses CNA + Med Aide + NA trainee; licensed nurse uses RN + LPN only.</p>
          <p class="statute-modal-source">Primary source: <a href="https://www.nysenate.gov/legislation/laws/PBH/2895-B" target="_blank" rel="noopener">N.Y. PHL &sect; 2895-b</a> &middot; <a href="https://www.health.ny.gov/facilities/nursing/minimum_staffing/" target="_blank" rel="noopener">NY DOH public summary</a></p>
        </div>
      </div>
    </dialog>
'''
    if 'id="ny-standard-compliance"' not in html:
        html = html.replace(
            '<dialog id="ny-doh-statute"',
            compliance_modal + "\n    " + '<dialog id="ny-doh-statute"',
            1,
        )

    html = re.sub(
        r"<h3 id=\"ny-doh-statute-title\">New York Nursing Home Minimum Staffing</h3>",
        "<h3 id=\"ny-doh-statute-title\">NY DOH Minimum Staffing Summary</h3>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<dialog id="ny-doh-statute"[\s\S]*?<div class="pbj-statute-dialog-body">)[\s\S]*?(</div>\s*</div>\s*</dialog>)',
        r"""\1
          <p>Public-facing summary from the <strong>New York State Department of Health</strong>: nursing homes must maintain minimum daily staffing hours and meet CNA and licensed-nurse components. DOH reviews <strong>quarterly</strong> CMS PBJ data to assess compliance and may impose civil penalties for non-compliance.</p>
          <p>For the statutory text, penalties, mitigating factors, and how PBJ320 maps roles, see <button type="button" class="statute-modal-trigger statute-inline-link" data-statute-modal-open="ny-standard-compliance" aria-haspopup="dialog">NY Standard &amp; Compliance</button>.</p>
          <p class="statute-modal-source">Source: <a href="https://www.health.ny.gov/facilities/nursing/minimum_staffing/" target="_blank" rel="noopener">NY DOH minimum staffing</a></p>
        \2""",
        html,
        count=1,
    )

    html = re.sub(
        r'<h2 id="weekend-heading">.*?</h2>',
        f'<h2 id="weekend-heading">Any given Sunday: {int(round(m["sun_pct"]))}% of facility-days missed part of the NY standard</h2>',
        html,
        count=1,
    )
    html = re.sub(
        r"Below-standard staffing was far more common on weekends: [\d.]+% of Sunday facility-days fell below the 3\.50 HPRD threshold, compared with [\d.]+% on Wednesday\.",
        f"Below-standard staffing was far more common on weekends: {m['sun_pct']}% of Sunday facility-days missed at least one mapped floor, compared with {m['wed_pct']}% on Wednesday.",
        html,
        count=1,
    )
    html = re.sub(
        r'(<div class="chart-title" id="dow-chart-title"><span class="chart-title-long">)% of facility-days below <span data-scenario-label>3\.50</span> HPRD · by day of week · NY statewide · 2025(</span><span class="chart-title-short">)% days &lt; <span data-scenario-label>3\.50</span> HPRD · DOW · NY · 2025(</span></div>)',
        r"\1% of facility-days below NY standard · by day of week · NY statewide · 2025\2% days below std · DOW · NY · 2025\3",
        html,
        count=1,
    )
    html = html.replace(
        'data-scenario-surface role="figure" aria-labelledby="dow-chart-title"',
        'data-pbj-standard-fixed role="figure" aria-labelledby="dow-chart-title"',
        1,
    )
    html = re.sub(
        r"Midweek low: Wednesday [\d.]+%\. Weekend high: Sunday [\d.]+%\. Within-week spread about [\d.]+ pp\.",
        f"Midweek low: Wednesday {m['wed_pct']}%. Weekend high: Sunday {m['sun_pct']}%. Within-week spread about {m['spread']} pp. Fixed to NY &sect;&nbsp;2895-b mapped floors (not scenario controls).",
        html,
        count=1,
    )

    for curve in ("all_ny", "ny_for_profit", "nyc", "nyc_for_profit"):
        sl = m["wt_slices"][curve]
        sm, sfd, sp = sl["all"]
        wsm, wsfd, wsp = sl["weekend"]
        html = _fill_wt_row(html, curve, sm, sfd, sp, wsm, wsfd, wsp)

    html = re.sub(
        r'<p class="pbj-standard-reference" role="note">.*?</p>',
        '<p class="pbj-standard-reference" role="note"><strong>PBJ standard reference</strong> &middot; counts below use the full NY mapped standard (miss any of 3.50 / 2.20 / 1.10). This table does not follow scenario controls.</p>',
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = re.sub(
        r'<div class="statute-compliance-ref">.*?</div>',
        '<div class="statute-compliance-ref"><button type="button" class="statute-modal-trigger" data-statute-modal-open="ny-standard-compliance" aria-haspopup="dialog" aria-label="NY staffing standard and compliance">NY Standard &amp; Compliance</button><span class="statute-compliance-ref-note">Statutory text, quarterly enforcement, and PBJ role mapping.</span></div>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<p>New York&rsquo;s minimum staffing rule has three parts:.*?</p>\s*<div class="appendix-grid',
        '<div class="appendix-grid',
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = re.sub(
        r'<span class="section-label">06 · NY role floors</span>',
        '<span class="section-label">Appendix · Role-floor detail</span>',
        html,
        count=1,
    )
    html = re.sub(
        r'<h2 id="statute-sensitivity-heading">NY role floors \(informative\)</h2>',
        '<h2 id="statute-sensitivity-heading" class="appendix-heading">Role-floor detail (supporting)</h2>',
        html,
        count=1,
    )
    html = html.replace(
        '<a href="#statute-sensitivity" class="report-mobile-jump-link">Role floors</a>',
        '<a href="#statute-sensitivity" class="report-mobile-jump-link">Appendix</a>',
        1,
    )
    html = html.replace(
        "<li><a href=\"#statute-sensitivity\">NY role floors</a></li>",
        "<li><a href=\"#statute-sensitivity\">Appendix: role floors</a></li>",
        1,
    )

    if ".standard-primary-callout" not in html:
        html = html.replace(
            ".statute-sensitivity .statute-compliance-ref {",
            ".standard-primary-callout {\n  margin: 0 0 1rem;\n  padding: 0.85rem 1rem;\n  background: var(--surface-muted, #f8fafc);\n  border-left: 3px solid var(--accent, #4f46e5);\n  font-size: 0.95rem;\n  line-height: 1.55;\n}\n.standard-component-note {\n  margin: 0 0 1rem;\n  font-size: 0.88rem;\n  color: var(--ink-soft, #64748b);\n}\n.standard-callout-link,\n.statute-inline-link {\n  font: inherit;\n  color: var(--link, #2563eb);\n  text-decoration: underline;\n  background: none;\n  border: none;\n  padding: 0;\n  cursor: pointer;\n}\n.statute-sensitivity { opacity: 0.98; }\n.appendix-heading { font-size: 1.15rem; }\n.statute-sensitivity .statute-compliance-ref {",
            1,
        )

    if "if (spec.fixedStandard) return;" not in html:
        html = html.replace(
            "  function updateDowChart(threshold) {\n    var chart = chartStore.dowChart;",
            "  function updateDowChart(threshold) {\n    var charts = global.PBJ_REPORT_CHARTS || [];\n    for (var fi = 0; fi < charts.length; fi++) {\n      if (charts[fi].id === 'dowChart' && charts[fi].fixedStandard) return;\n    }\n    var chart = chartStore.dowChart;",
            1,
        )

    html = html.replace(
        "var lines = [fmtPct(item.raw) + '% below min'];",
        "var lines = [fmtPct(item.raw) + '% below standard'];",
        1,
    )

    HTML.write_text(html, encoding="utf-8")
    return m


def main() -> int:
    try:
        m = patch_html()
    except Exception as exc:
        print(f"FAIL patch_ny_report_standard_primary.py: {exc}", file=sys.stderr)
        return 1
    print(
        f"Patched {HTML.name}: primary {m['miss_any']:,} days ({m['miss_pct']}%), "
        f"weekend {m['weekend_miss_pct']}%, Sunday {m['sun_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
