#!/usr/bin/env python3
"""Apply daily=3.50 / quarterly=full-standard editorial rule to NY staffing report HTML."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"


def load_json_after(marker: str, html: str) -> dict:
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
    raise RuntimeError(f"JSON not found for {marker}")


def patch_window_var(html: str, name: str, payload: dict) -> str:
    marker = f"window.{name} = "
    start = html.index(marker)
    end = start + len(marker)
    depth = 0
    for j in range(end, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                repl = marker + json.dumps(payload, separators=(",", ":")) + ";"
                return html[:start] + repl + html[j + 1 :]
    raise RuntimeError(name)


def curve_at(curve: list, t: float = 3.5) -> dict:
    return next(p for p in curve if abs(p["threshold"] - t) < 0.001)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    inter = load_json_after("window.PBJ_REPORT_INTERACTIVE = ", html)
    mode = inter["modes"]["ny_mapped_non_admin_hprd"]
    all_pt = curve_at(mode["curves"]["all_ny"])
    wk_pt = curve_at(mode["curves"]["weekend"])
    sun_pt = curve_at(mode["curves_by_dow"]["Sunday"])
    wed_pt = curve_at(mode["curves_by_dow"]["Wednesday"])

    q = load_json_after("window.PBJ_REPORT_QUARTERLY_STATUTORY = ", html)
    fq_analyzed = int(q["facility_quarters_analyzed"])
    fq_below_220 = 1329
    fq_below_110 = 638
    q.update(
        {
            "facility_quarters_below_220_cna_side": fq_below_220,
            "pct_facility_quarters_below_220_cna_side": round(100 * fq_below_220 / fq_analyzed, 2),
            "facility_quarters_below_110_licensed": fq_below_110,
            "pct_facility_quarters_below_110_licensed": round(100 * fq_below_110 / fq_analyzed, 2),
            "facilities_below_350_at_least_one_quarter": 422,
            "facilities_below_350_all_four_quarters": 284,
            "facilities_missing_any_floor_at_least_one_quarter": 454,
            "facilities_missing_any_floor_all_four_quarters": 314,
        }
    )
    html = patch_window_var(html, "PBJ_REPORT_QUARTERLY_STATUTORY", q)

    primary = {
        "below_days": int(all_pt["below"]),
        "below_pct": round(float(all_pt["pct_below"]), 1),
        "weekend_pct": round(float(wk_pt["pct_below"]), 1),
        "weekend_below": int(wk_pt["below"]),
        "weekend_fd": 61586,
        "below_350_days": int(all_pt["below"]),
        "below_350_pct": round(float(all_pt["pct_below"]), 1),
        "sun_pct": round(float(sun_pt["pct_below"]), 1),
        "wed_pct": round(float(wed_pt["pct_below"]), 1),
    }
    html = patch_window_var(html, "PBJ_REPORT_STANDARD_PRIMARY", primary)

    charts = load_json_after("window.PBJ_REPORT_CHARTS = ", html)
    dows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for spec in charts:
        if spec.get("type") != "dow":
            continue
        vals, fds, tips = [], [], []
        cfd = mode.get("curve_facility_days") or {}
        for dow in dows:
            pt = curve_at(mode["curves_by_dow"][dow])
            fd = int(cfd.get(f"dow:{dow}") or pt.get("facility_days") or 0)
            vals.append(round(float(pt["pct_below"]), 1))
            fds.append(fd)
            tips.append(f"{fmt_int(int(pt['below']))} of {fmt_int(fd)} facility-days")
        spec["labels"] = labels
        spec["dows"] = dows
        spec["values"] = vals
        spec["facility_days"] = fds
        spec["tooltips"] = tips
        spec.pop("fixedStandard", None)
        spec.pop("metric", None)
        spec["yMin"] = round(min(vals) - 15, 1)
        spec["yMax"] = round(max(vals) + 10, 1)
    html = patch_window_var(html, "PBJ_REPORT_CHARTS", charts)

    # Hero
    html = html.replace(
        "<h1>New York nursing homes missed at least one part of the state&rsquo;s daily staffing standard on <em>65.1%</em> of facility-days in 2025.</h1>",
        f"<h1>New York nursing homes reported staffing below the <em>3.50 HPRD</em> standard on <em>{primary['below_pct']}%</em> of facility-days in 2025.</h1>",
    )
    html = re.sub(
        r'<span class="kpi-num-value">[\d,]+</span><span class="kpi-num-unit"> Days</span>',
        f'<span class="kpi-num-value">{fmt_int(primary["below_days"])}</span><span class="kpi-num-unit"> Days</span>',
        html,
        count=1,
    )
    html = re.sub(
        r'aria-label="[\d,]+ days"',
        f'aria-label="{fmt_int(primary["below_days"])} days"',
        html,
        count=1,
    )
    html = re.sub(
        r'(<div class="kpi">\s*<span class="kpi-num" aria-label="[^"]*percent[^"]*"><span class="kpi-num-value">)[\d.]+%',
        rf"\g<1>{primary['below_pct']}%",
        html,
        count=1,
    )
    html = re.sub(
        r'id="kpi-weekend-pct" aria-label="[^"]*"><span class="kpi-num-value">[\d.]+%',
        f'id="kpi-weekend-pct" aria-label="{primary["weekend_pct"]} percent weekend"><span class="kpi-num-value">{primary["weekend_pct"]}%',
        html,
        count=1,
    )

    # Definitions block
    old_defs_head = re.search(
        r'<h2 id="definitions-heading">.*?</h2>\s*<p class="standard-primary-callout".*?</p><p class="standard-component-note".*?</p>',
        html,
        re.DOTALL,
    )
    if old_defs_head:
        new_defs = f'''<h2 id="definitions-heading">More than half of NY facility-days were below the 3.50 HPRD standard</h2>
    <p class="section-methods"><span class="section-methods-label">Methods</span><span class="section-methods-links"><a class="methods-jump-link" href="#method-metric">HPRD metric</a><a class="methods-jump-link" href="#method-threshold">Threshold</a><a class="methods-jump-link" href="#method-quarterly-statutory">Quarterly mapping</a></span></p>'''
        html = html[: old_defs_head.start()] + new_defs + html[old_defs_head.end() :]

    html = re.sub(
        r'<p class="report-scope-note">New York&rsquo;s nursing home staffing standard has.*?</p>\s*<p class="report-scope-note">In 2025, nursing homes missed at least one mapped part.*?</p>',
        f'''<p class="report-scope-note">New York state law sets a <strong>3.50 HPRD</strong> direct-care staffing level (RN+LPN+CNA+MedAide+NAtrn on the default NY-mapped PBJ measure). Though DOH assesses the <strong>full mapped standard quarterly</strong>, this report uses federal <strong>Payroll-Based Journal (PBJ)</strong> data&mdash;one record per nursing home per calendar day&mdash;to show how often <strong>reported staffing fell below 3.50 HPRD</strong>.</p>
    <p class="report-scope-note">In 2025, New York nursing homes reported staffing below <strong>3.50 HPRD</strong> on <strong>{fmt_int(primary["below_days"])} facility-days &mdash; {primary["below_pct"]}% of all daily records analyzed</strong>. Weekend shortfalls were more common, with <strong>{primary["weekend_pct"]}% of Saturday and Sunday records below 3.50 HPRD</strong>. These daily counts describe reported staffing levels, not NY DOH quarterly compliance determinations.</p>''',
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Weekend section
    spread = round(primary["sun_pct"] - primary["wed_pct"], 1)
    html = html.replace(
        "<h2 id=\"weekend-heading\">Any given Sunday: 85% of facility-days missed part of the NY standard</h2>",
        f"<h2 id=\"weekend-heading\">Any given Sunday: {primary['sun_pct']}% of facility-days were below 3.50 HPRD</h2>",
    )
    html = re.sub(
        r"<p>Below-standard staffing was far more common on weekends:.*?on Wednesday\.</p>",
        f"<p>Below-standard staffing was far more common on weekends: {primary['sun_pct']}% of Sunday facility-days fell below the 3.50 HPRD threshold, compared with {primary['wed_pct']}% on Wednesday.</p>",
        html,
        count=1,
    )
    html = html.replace(
        'id="dow-chart-title"><span class="chart-title-long">% of facility-days below NY standard',
        'id="dow-chart-title"><span class="chart-title-long">% of facility-days below <span data-scenario-label>3.50</span> HPRD',
    )
    html = html.replace('data-pbj-standard-fixed role="figure" aria-labelledby="dow-chart-title"', 'data-scenario-surface role="figure" aria-labelledby="dow-chart-title"')
    if 'data-scenario-ribbon' not in html.split("dow-chart-title")[0][-400:]:
        html = html.replace(
            '<div class="chart-wrap" data-scenario-surface role="figure" aria-labelledby="dow-chart-title">',
            '<div class="chart-wrap" data-scenario-surface role="figure" aria-labelledby="dow-chart-title">\n      <p class="chart-scenario-ribbon" data-scenario-ribbon hidden aria-live="polite"></p>',
            1,
        )
    html = re.sub(
        r"<p class=\"chart-note\">Midweek low:.*?PBJ Standard.*?</p>",
        f"<p class=\"chart-note\">Midweek low: Wednesday {primary['wed_pct']}%. Weekend high: Sunday {primary['sun_pct']}%. Within-week spread about {spread} pp. Adjust threshold with <strong>PBJ Standard</strong> (bottom right).<span class=\"chart-source-attrib\"><span class=\"chart-source-long\"> Source: CMS PBJ; analysis by PBJ320.</span><span class=\"chart-source-short\" aria-hidden=\"true\"> Source: CMS PBJ · PBJ320 analysis</span></span></p>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Weekend table reference note (rows are maintained in HTML with verified denominators)
    html = html.replace(
        "<p class=\"pbj-standard-reference\" role=\"note\"><strong>PBJ standard reference</strong> &middot; counts below use the full NY mapped standard (miss any of 3.50 / 2.20 / 1.10). This table does not follow scenario controls.</p>",
        "<p class=\"pbj-standard-reference\" role=\"note\"><strong>Daily reference</strong> &middot; share of facility-days with reported NY-mapped direct-care HPRD strictly below <strong>3.50</strong>. Full three-floor statutory mapping appears in <a href=\"#quarterly-statutory-summary\">quarterly statutory-style rollups</a> below.</p>",
    )

    # Provider note -> quarterly only
    html = html.replace(
        '<p class="definitions-disclaimer provider-quarterly-note" role="note"><strong>Note:</strong> In Q4 2025, <strong>60.44%</strong> of facilities (<strong>356 of 589</strong>) averaged below <strong>3.50</strong> HPRD on the NY-mapped PBJ measure; <strong>67.57%</strong> missed at least one of the three mapped floors. Daily shortfalls are not the same as quarterly compliance. These are descriptive statutory-style calculations, not NY DOH enforcement determinations.</p>\n\n    ',
        "",
    )

    # Remove statute-sensitivity section
    html = re.sub(
        r'\s*<section id="statute-sensitivity".*?</section>\s*',
        "\n\n",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = html.replace('<a href="#statute-sensitivity" class="report-mobile-jump-link">Appendix</a>\n    ', "")
    html = html.replace('      <li><a href="#statute-sensitivity">Appendix: role floors</a></li>\n', "")

    # updateKpis labels
    html = html.replace(
        "setKpiLabels(labels[0], 'Days below NY standard', 'Days below std');",
        "setKpiLabels(labels[0], 'Facility-days below 3.50 HPRD', 'Days below 3.50');",
    )
    html = html.replace(
        "setKpiLabels(labels[1], 'Share of days below standard', 'NY days below std');",
        "setKpiLabels(labels[1], 'Share of days below 3.50 HPRD', '% below 3.50');",
    )
    html = html.replace(
        "setKpiLabels(labels[2], 'Weekend days below standard', 'Wknd below std');",
        "setKpiLabels(labels[2], 'Weekend days below 3.50 HPRD', 'Wknd below 3.50');",
    )
    html = html.replace(
        "v0.textContent = fmtInt(primary.below_days);",
        "v0.textContent = fmtInt(primary.below_350_days != null ? primary.below_350_days : primary.below_days);",
    )
    html = html.replace(
        "nums[0].setAttribute('aria-label', fmtInt(primary.below_days) + ' days');",
        "nums[0].setAttribute('aria-label', fmtInt(primary.below_350_days != null ? primary.below_350_days : primary.below_days) + ' days');",
    )
    html = html.replace(
        "v1.textContent = fmtPct(primary.below_pct) + '%';",
        "v1.textContent = fmtPct(primary.below_350_pct != null ? primary.below_350_pct : primary.below_pct) + '%';",
    )
    html = html.replace(
        "nums[1].setAttribute('aria-label', fmtPct(primary.below_pct) + ' percent');",
        "nums[1].setAttribute('aria-label', fmtPct(primary.below_350_pct != null ? primary.below_350_pct : primary.below_pct) + ' percent');",
    )

    HTML.write_text(html, encoding="utf-8")
    print("Patched", HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
