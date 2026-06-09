#!/usr/bin/env python3
"""Patch NY report HTML prose and JS after rebuild_ny_report_embeds.py."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
THRESHOLD = 3.5


def _load_embed(name: str) -> dict:
    marker = f"window.{name} = "
    text = HTML.read_text(encoding="utf-8")
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
    raise ValueError(name)


def patch_html() -> None:
    html = HTML.read_text(encoding="utf-8")
    interactive = _load_embed("PBJ_REPORT_INTERACTIVE")
    quarterly = _load_embed("PBJ_REPORT_QUARTERLY_STATUTORY")
    mode_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
    mode = interactive["modes"][mode_key]
    all_pt = next(
        p for p in mode["curves"]["all_ny"] if abs(float(p["threshold"]) - 3.5) < 0.01
    )
    wk_pt = next(
        p for p in mode["curves"]["weekend"] if abs(float(p["threshold"]) - 3.5) < 0.01
    )
    below = int(all_pt["below"])
    pct = round(float(all_pt["pct_below"]), 1)
    wk_pct = round(float(wk_pt["pct_below"]), 1)

    html = re.sub(
        r'(<span class="kpi-num-value">)[\d.]+%(</span></span>\s*<span class="kpi-label"><span class="kpi-label-long">Share of Days)',
        rf"\g<1>{pct}%\g<2>",
        html,
        count=1,
    )
    html = re.sub(
        r'(<span class="kpi-num" id="kpi-weekend-pct"[^>]*><span class="kpi-num-value">)[\d.]+%(</span>)',
        rf"\g<1>{wk_pct}%\g<2>",
        html,
        count=1,
    )
    html = html.replace(
        'aria-label="47.1 percent"',
        f'aria-label="{pct} percent"',
    )
    html = html.replace(
        'aria-label="76.9 percent"',
        f'aria-label="{wk_pct} percent weekend"',
    )
    html = re.sub(
        r'aria-label="[\d,]+ days"',
        f'aria-label="{below:,} days"',
        html,
        count=1,
    )

    section_heading = (
        f"More than half of NY facility-days were below the 3.50 HPRD standard"
        if pct >= 50
        else f"Nearly half of NY facility-days were below the 3.50 HPRD standard"
    )
    html = re.sub(
        r'<h2 id="definitions-heading">.*?</h2>',
        f'<h2 id="definitions-heading">{section_heading}</h2>',
        html,
        count=1,
    )
    scope_note = (
        f"In 2025, New York nursing homes reported staffing below the <strong>3.50 HPRD</strong> standard on "
        f"<strong>{below:,} facility-days — {pct}% of all daily records analyzed</strong>. "
        f"Weekend shortfalls were more common, with <strong>{wk_pct}% of Saturday and Sunday records "
        f"falling below the threshold</strong>. Shortfalls were also more frequent among for-profit "
        f"facilities and varied sharply by region, with the Bronx region showing the highest rate. "
        f"These findings have implications for workforce planning, enforcement priorities, "
        f"resident advocacy, and public accountability."
    )
    html = re.sub(
        r'<p class="report-scope-note">In 2025, New York nursing homes fell below.*?</p>',
        f'<p class="report-scope-note">{scope_note}</p>',
        html,
        count=1,
        flags=re.DOTALL,
    )

    facilities = _load_embed("PBJ_REPORT_FACILITIES")
    idx_35 = int(round((THRESHOLD - facilities["threshold_start"]) / facilities["threshold_step"]))
    fac_list = facilities["facilities"]
    every_day = sum(1 for f in fac_list if f["below_curve"][idx_35] >= f["facility_days"])
    at_least_50 = sum(1 for f in fac_list if f["below_curve"][idx_35] >= 0.5 * f["facility_days"])
    at_least_90 = sum(1 for f in fac_list if f["below_curve"][idx_35] >= 0.9 * f["facility_days"])
    at_least_50_pct = round(100 * at_least_50 / len(fac_list), 1)
    html = re.sub(
        r'<p id="provider-days-below-lead">.*?</p>',
        f'<p id="provider-days-below-lead">Among <strong>596</strong> New York nursing homes, '
        f"<strong>{at_least_50}</strong> (<strong>{at_least_50_pct}%</strong>) "
        f"reported staffing below <strong>3.50</strong> HPRD on at least half of their analyzed "
        f"2025 facility-days. At the high end, <strong>{at_least_90}</strong> homes were below "
        f"the standard on at least <strong>90%</strong> of days, including "
        f"<strong>{every_day}</strong> homes below the standard on every reported day.</p>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    mo = mode.get("curves_by_month") or {}
    apr_pct = round(float(next(p for p in mo["4"] if abs(float(p["threshold"]) - 3.5) < 0.01)["pct_below"]), 1)
    dec_pct = round(float(next(p for p in mo["12"] if abs(float(p["threshold"]) - 3.5) < 0.01)["pct_below"]), 1)
    calendar = _load_embed("PBJ_REPORT_CALENDAR_EXTRA")
    hol_pct = round(float(calendar.get("federal_holiday", {}).get("pct_below", 0)), 1)
    non_pct = round(float(calendar.get("non_holiday", {}).get("pct_below", 0)), 1)
    html = re.sub(
        r"Monthly rates stayed in a narrow band—about <strong>[\d.]+%</strong> \(April\) to "
        r"<strong>[\d.]+%</strong> \(December\)—far smaller than the weekday–weekend gap above\. "
        r"<strong>December</strong> is the high month: it includes Christmas \(a federal holiday\) "
        r"and typical year-end weekend patterns\. Statewide, facility-days on <strong>federal holidays</strong> "
        r"were about <strong>[\d.]+%</strong> below 3\.50 HPRD vs\. <strong>[\d.]+%</strong> on other days\. "
        r"Use <strong>By week</strong> for detail\.",
        f"Monthly rates stayed in a narrow band—about <strong>{apr_pct}%</strong> (April) to "
        f"<strong>{dec_pct}%</strong> (December)—far smaller than the weekday–weekend gap above. "
        f"<strong>December</strong> is the high month: it includes Christmas (a federal holiday) "
        f"and typical year-end weekend patterns. Statewide, facility-days on <strong>federal holidays</strong> "
        f"were about <strong>{hol_pct}%</strong> below 3.50 HPRD vs. <strong>{non_pct}%</strong> on other days. "
        f"Use <strong>By week</strong> for detail.",
        html,
        count=1,
    )
    html = re.sub(
        r"April ~[\d.]+%\s*, December ~[\d.]+%\. December includes Christmas and more weekend-heavy weeks; "
        r"holidays statewide run slightly higher than non-holiday days\.",
        f"April ~{apr_pct}%, December ~{dec_pct}%. December includes Christmas and more weekend-heavy weeks; "
        f"holidays statewide run slightly higher than non-holiday days.",
        html,
        count=1,
    )

    headline = (
        "New York nursing homes reported staffing below the state&rsquo;s 3.50-hour standard on "
        f"<em>{pct}%</em> of facility-days in 2025."
    )
    html = re.sub(
        r"<h1>.*?</h1>",
        f"<h1>{headline}</h1>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    dow = mode.get("curves_by_dow") or {}
    wed = next(p for p in dow["Wednesday"] if abs(float(p["threshold"]) - 3.5) < 0.01)
    sun = next(p for p in dow["Sunday"] if abs(float(p["threshold"]) - 3.5) < 0.01)
    wed_pct = round(float(wed["pct_below"]), 1)
    sun_pct = round(float(sun["pct_below"]), 1)
    wknd_pt = next(p for p in mode["curves"]["weekend"] if abs(float(p["threshold"]) - 3.5) < 0.01)
    all_pt = next(p for p in mode["curves"]["all_ny"] if abs(float(p["threshold"]) - 3.5) < 0.01)
    wknd_pct = round(float(wknd_pt["pct_below"]), 1)
    wknd_fd = int(wknd_pt.get("facility_days") or 0)
    wknd_below = int(wknd_pt["below"])
    all_fd = int(all_pt.get("facility_days") or 0)
    all_below = int(all_pt["below"])
    wkday_below = all_below - wknd_below
    wkday_fd = all_fd - wknd_fd
    wkday_pct = round(100.0 * wkday_below / wkday_fd, 1) if wkday_fd else 0.0

    html = re.sub(
        r"<h2 id=\"weekend-heading\">.*?</h2>",
        '<h2 id="weekend-heading">Any given Sunday: four in five facility Sundays were below 3.50 HPRD</h2>',
        html,
        count=1,
    )
    html = re.sub(
        r"<p>Below-standard staffing was far more common on weekends.*?had the lowest\.</p>",
        f"<p>Below-standard staffing was far more common on weekends (<strong>{wknd_pct}%</strong>) compared to weekdays (<strong>{wkday_pct}%</strong>). Sundays (<strong>{sun_pct}%</strong>) had the highest rate of shortfalls while Wednesdays (<strong>{wed_pct}%</strong>) had the lowest.</p>",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<p class="chart-note chart-note--fixed-baseline" id="dow-chart-note">.*?</p>',
        f'<p class="chart-note chart-note--fixed-baseline" id="dow-chart-note"><span class="chart-note-fixed-tag">Caption fixed at NY-mapped <strong>direct-care HPRD @ 3.50</strong> (not tied to PBJ Standard controls).</span>Midweek low: Wednesday {wed_pct}%. Weekend high: Sunday {sun_pct}%.<span class="chart-source-attrib"><span class="chart-source-long"> Source: CMS PBJ; analysis by PBJ320.</span><span class="chart-source-short" aria-hidden="true"> Source: CMS PBJ · PBJ320 analysis</span></span></p>',
        html,
        count=1,
        flags=re.DOTALL,
    )

    def slice_pct(curve_key: str) -> float:
        pt = next(
            p
            for p in mode["curves"][curve_key]
            if abs(float(p["threshold"]) - 3.5) < 0.01
        )
        return round(float(pt["pct_below"]), 1)

    fp = slice_pct("ny_for_profit")
    np = slice_pct("ny_non_profit")
    gov = slice_pct("ny_government")
    nyc_fp = slice_pct("nyc_for_profit")
    nyc_np = slice_pct("nyc_non_profit")
    nyc_gov = slice_pct("nyc_government")

    html = re.sub(
        r"Statewide, for-profit nursing homes were below New York&rsquo;s <strong>3\.50 HPRD</strong> standard on <strong>[\d.]+%</strong> of 2025 facility-days, compared with <strong>[\d.]+%</strong> for non-profit homes and <strong>[\d.]+%</strong> for government-operated homes\.",
        f"Statewide, for-profit nursing homes were below New York&rsquo;s <strong>3.50 HPRD</strong> standard on <strong>{fp}%</strong> of 2025 facility-days, compared with <strong>{np}%</strong> for non-profit homes and <strong>{gov}%</strong> for government-operated homes.",
        html,
        count=1,
    )
    html = re.sub(
        r"NYC for-profit homes were below the standard on <strong>[\d.]+%</strong> of facility-days, compared with <strong>[\d.]+%</strong> for NYC non-profit homes and <strong>[\d.]+%</strong> for NYC government-operated homes\.",
        f"NYC for-profit homes were below the standard on <strong>{nyc_fp}%</strong> of facility-days, compared with <strong>{nyc_np}%</strong> for NYC non-profit homes and <strong>{nyc_gov}%</strong> for NYC government-operated homes.",
        html,
        count=1,
    )

    q4_pct = quarterly.get("pct_q4_2025_facilities_below_350_total", 0)
    q4_n = quarterly.get("q4_2025_facilities_below_350_total", 0)
    q4_fac = quarterly.get("q4_2025_facilities_analyzed", 0)
    q4_miss_pct = quarterly.get("pct_q4_2025_facilities_missing_any_floor", 0)

    quarterly_note = (
        f"In Q4 2025, <strong>{q4_pct}%</strong> of facilities (<strong>{q4_n} of {q4_fac}</strong>) "
        f"averaged below <strong>3.50</strong> HPRD on the NY-mapped PBJ measure; "
        f"<strong>{q4_miss_pct}%</strong> missed at least one of the three mapped floors."
    )
    html = re.sub(
        r'<p class="definitions-disclaimer provider-quarterly-note" role="note"><strong>Note:</strong>.*?</p>',
        f'<p class="definitions-disclaimer provider-quarterly-note" role="note"><strong>Note:</strong> {quarterly_note} Daily shortfalls are not the same as quarterly compliance. These are descriptive statutory-style calculations, not NY DOH enforcement determinations.</p>',
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = html.replace(
        'global.PBJ_REPORT_METRIC_MODE = \'total\';',
        f"global.PBJ_REPORT_METRIC_MODE = '{mode_key}';",
    )
    html = html.replace(
        "return ui.metricToggleMode || 'excl_admin';",
        "return ui.metricToggleMode || 'broad_pbj_total_hprd';",
    )
    html = html.replace(
        "return global.PBJ_REPORT_METRIC_MODE === 'excl_admin' ? 'below_curve_excl' : 'below_curve';",
        "return global.PBJ_REPORT_METRIC_MODE === 'broad_pbj_total_hprd' ? 'below_curve_broad' : 'below_curve';",
    )
    html = html.replace(
        '"metricToggleMode": "excl_admin", "metricToggleLabel": "Exclude admin/DON", "metricToggleNote": " (excl. RN DON, RN admin, LPN admin)"',
        '"metricToggleMode": "broad_pbj_total_hprd", "metricToggleLabel": "Compare: broad PBJ total", "metricToggleNote": " (incl. RN DON, RN admin, LPN admin)"',
    )

    if 'class="fac-qtrs-col"' not in html:
        html = html.replace(
            '<th scope="col" class="fac-hprd-col" data-sort="mean_hprd"',
            '<th scope="col" class="fac-qtrs-col" data-sort="qtrs_below" data-label="Qtrs &lt; Floor" title="Quarters below 3.50 total HPRD floor / quarters analyzed (statutory-style PBJ mapping).">Qtrs &lt; Floor</th>\n                <th scope="col" class="fac-hprd-col" data-sort="mean_hprd"',
        )

    if "fac-qtrs-cell" not in html and "qtrs_below_350" not in html:
        html = html.replace(
            "'<td class=\"fac-hprd-cell\">' + fmtHprd(r.mean_hprd) + '</td>' +",
            "'<td class=\"fac-qtrs-cell\">' + escapeHtml(r.qtrs_below || '') + '</td>' +\n"
            "        '<td class=\"fac-hprd-cell\">' + fmtHprd(r.mean_hprd) + '</td>' +",
        )
        html = html.replace(
            "mean_hprd: f.mean_hprd,",
            "mean_hprd: f.mean_hprd,\n        qtrs_below: f.qtrs_below_350 || '',",
        )

    statute = _load_embed("PBJ_REPORT_NY_STATUTE")
    met_pct = round(float(statute.get("pct_meets_all_ny_requirements", 0)), 1)
    cna_pct = round(float(statute.get("pct_below_cna", 0)), 1)
    lic_pct = round(float(statute.get("pct_below_lpn_rn", 0)), 1)
    html = re.sub(
        r'(<div class="appendix-card">\s*<div class="appendix-card-stat">\s*'
        r'<span class="appendix-card-num" aria-label=")[\d.]+( percent">)[\d.]+%(</span>)',
        rf"\g<1>{met_pct}\g<2>{met_pct}%\g<3>",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'(<div class="appendix-card appendix-card--cna-miss">\s*<div class="appendix-card-stat">\s*'
        r'<span class="appendix-card-num" aria-label=")[\d.]+( percent">)[\d.]+%(</span>)',
        rf"\g<1>{cna_pct}\g<2>{cna_pct}%\g<3>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = html.replace(
        "<p>This analysis uses <strong>CMS Payroll-Based Journal (PBJ) daily nurse staffing</strong> for calendar year 2025: four quarterly CSV releases (CY2025Q1–Q4). Each record is one nursing home on one work date with role-level hours and census.</p>",
        "<p><strong>Primary legal reference:</strong> <a href=\"https://www.nysenate.gov/legislation/laws/PBH/2895-B\" target=\"_blank\" rel=\"noopener\">N.Y. Public Health Law § 2895-b</a>. "
        "This analysis uses <strong>CMS Payroll-Based Journal (PBJ) daily nurse staffing</strong> for calendar year 2025: four quarterly CSV releases (CY2025Q1–Q4). Each record is one nursing home on one work date with role-level hours and census.</p>",
    )
    html = html.replace(
        "<p><strong>Primary NY-mapped HPRD (§ 2895-b default):</strong> (RN + LPN + CNA + Med Aide + NA trainee) ÷ MDS census. Excludes RN DON, RN admin, and LPN admin from the total and from the licensed-nurse floor.</p>",
        "<p><strong>Primary NY-mapped HPRD (§ 2895-b default):</strong> (RN + LPN + CNA + Med Aide + NA trainee) ÷ MDS census. "
        "Excludes RN DON, RN admin, and LPN admin from the default total and from the default licensed-nurse floor. "
        "Daily facility-day shortfalls are descriptive PBJ mapping only—not NY DOH enforcement determinations.</p>",
    )
    html = html.replace(
        "Primary charts use the <strong>NY-mapped total</strong> (default benchmark 3.50). A comparison toggle shows the broader eight-role PBJ total.",
        "Primary charts use the <strong>NY-mapped total</strong> (default benchmark 3.50). "
        "A comparison toggle shows the broader eight-role PBJ total; an embedded include-DON sensitivity adds RN DON to both the 3.50 total and the 1.10 licensed-nurse floor (still excluding admin).",
    )
    html = html.replace(
        "<li><strong>Total nursing HPRD</strong> includes RN DON, RN admin, and LPN admin.</li>",
        "<li><strong>Default NY-mapped HPRD</strong> excludes RN DON, RN admin, and LPN admin; the comparison toggle shows the broader eight-role PBJ total.</li>",
    )
    html = html.replace(
        "<li><strong>NY role floors</strong> — Compute CNA-side and LPN/RN-side HPRD; count days meeting all three statutory floors (AND) for informative sensitivity tables.</li>",
        "<li><strong>NY role floors</strong> — Compute CNA-side and licensed-nurse (RN+LPN) HPRD on the default NY-mapped roles. For quarterly statutory-style rollups, aggregate role hours and census-days by facility-quarter, then flag whether each facility-quarter meets all three mapped floors.</li>",
    )
    html = html.replace(
        "<p class=\"footer-verification-note\">Report prepared by PBJ320 · underlying tables generated 2026-06-03</p>",
        "<p class=\"footer-verification-note\">Report prepared by PBJ320 · underlying tables generated 2026-06-08</p>",
    )

    html = patch_css_comment(html, below, pct)
    HTML.write_text(html, encoding="utf-8")
    print(f"Patched {HTML} ({HTML.stat().st_size:,} bytes)")


def patch_css_comment(html: str, below: int, pct: float) -> str:
    return re.sub(
        r"/\* Hero KPIs \([\d,]+ · [\d.]+% · weekend %\): one row, inset from screen edges \*/",
        f"/* Hero KPIs ({below:,} · {pct}% · weekend %): one row, inset from screen edges */",
        html,
        count=1,
    )


if __name__ == "__main__":
    patch_html()
