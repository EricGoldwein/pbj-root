#!/usr/bin/env python3
"""Sync press page copy with insights-ny-minimum-staffing.html embeds."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "insights-ny-minimum-staffing.html"
PRESS = ROOT / "insights-ny-minimum-staffing-press.html"
THRESHOLD = 3.5


def _load_embed(html: str, name: str) -> dict:
    marker = f"window.{name} = "
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
    raise ValueError(name)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def patch_press() -> None:
    report_html = REPORT.read_text(encoding="utf-8")
    interactive = _load_embed(report_html, "PBJ_REPORT_INTERACTIVE")
    facilities = _load_embed(report_html, "PBJ_REPORT_FACILITIES")
    statute = _load_embed(report_html, "PBJ_REPORT_NY_STATUTE")
    primary = None
    if "window.PBJ_REPORT_STANDARD_PRIMARY = " in report_html:
        primary = _load_embed(report_html, "PBJ_REPORT_STANDARD_PRIMARY")

    mode_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
    mode = interactive["modes"][mode_key]
    all_pt = next(p for p in mode["curves"]["all_ny"] if abs(float(p["threshold"]) - THRESHOLD) < 0.01)
    wk_pt = next(p for p in mode["curves"]["weekend"] if abs(float(p["threshold"]) - THRESHOLD) < 0.01)
    nyc_wk = next(p for p in mode["curves"]["weekend_nyc"] if abs(float(p["threshold"]) - THRESHOLD) < 0.01)
    nyc_fd = next(c["facility_days"] for c in mode["weekend_cards"] if c["curve"] == "weekend_nyc")

    below = int(statute["facility_days_below_any_ny_requirement"])
    pct = round(float(statute["pct_below_any_ny_requirement"]), 1)
    wk_pct = round(float(primary["weekend_pct"]), 1) if primary else round(float(wk_pt["pct_below"]), 1)
    wk_below = int(primary["weekend_below"]) if primary else int(wk_pt["below"])
    wk_fd = int(primary["weekend_fd"]) if primary else int(
        next(c["facility_days"] for c in mode["weekend_cards"] if c["curve"] == "weekend")
    )
    below_350 = int(all_pt["below"])
    pct_350 = round(float(all_pt["pct_below"]), 1)
    nyc_wk_pct = round(float(nyc_wk["pct_below"]), 1)
    nyc_wk_below = int(nyc_wk["below"])
    wed_pct = round(float(primary["wed_pct"]), 1) if primary else round(
        float(next(p for p in mode["curves_by_dow"]["Wednesday"] if abs(float(p["threshold"]) - THRESHOLD) < 0.01)["pct_below"]),
        1,
    )
    sun_pct = round(float(primary["sun_pct"]), 1) if primary else round(
        float(next(p for p in mode["curves_by_dow"]["Sunday"] if abs(float(p["threshold"]) - THRESHOLD) < 0.01)["pct_below"]),
        1,
    )

    idx_35 = int(round((THRESHOLD - facilities["threshold_start"]) / facilities["threshold_step"]))
    fac_list = facilities["facilities"]
    every_day = sum(1 for f in fac_list if f["below_curve"][idx_35] >= f["facility_days"])
    at_least_90 = sum(1 for f in fac_list if f["below_curve"][idx_35] >= 0.9 * f["facility_days"])
    chronic_pct = round(100 * every_day / len(fac_list), 1)

    two_thirds_phrase = "Nearly Two-Thirds" if pct >= 65 else "More than Half" if pct >= 50 else "Nearly Half"
    met_pct = round(float(statute.get("pct_meets_all_ny_requirements", 0)), 1)
    miss_pct = round(float(statute.get("pct_below_any_ny_requirement", 0)), 1)

    html = PRESS.read_text(encoding="utf-8")

    html = re.sub(
        r"<title>Press release:.*?</title>",
        f"<title>Press release: NY nursing homes missed part of staffing standard on {two_thirds_phrase} of Days in 2025 — PBJ320</title>",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'content="Media advisory:.*?"',
        f'content="Media advisory: {pct}% of NY nursing home facility-days in 2025 missed part of the mapped staffing standard; weekends {wk_pct}%. {pct_350}% missed the 3.50 HPRD total component alone. Searchable list of all 596 homes."',
        html,
        count=1,
    )
    html = re.sub(
        r'property="og:title" content="[^"]*"',
        f'property="og:title" content="NY Nursing Homes Missed Staffing Standard on {two_thirds_phrase} of Days in 2025 — PBJ320 Press Release"',
        html,
        count=1,
    )
    html = re.sub(
        r'property="og:description" content="[^"]*"',
        f'property="og:description" content="{pct}% of NY facility-days missed part of the mapped standard in 2025; {wk_pct}% on weekends. {pct_350}% below 3.50 HPRD total alone. All 596 homes in searchable PBJ320 report."',
        html,
        count=1,
    )
    html = re.sub(
        r'name="twitter:title" content="[^"]*"',
        f'name="twitter:title" content="NY Nursing Homes Missed Staffing Standard on {two_thirds_phrase} of Days in 2025 — PBJ320"',
        html,
        count=1,
    )
    html = re.sub(
        r'name="twitter:description" content="[^"]*"',
        f'name="twitter:description" content="PBJ320 CMS PBJ analysis: {pct}% of NY nursing home facility-days in 2025 missed part of the mapped standard; weekends {wk_pct}%."',
        html,
        count=1,
    )

    html = re.sub(
        r'<p class="hero-dek">.*?</p>',
        f'<p class="hero-dek"><strong>{pct}%</strong> of facility-days statewide missed at least one mapped part of the NY staffing standard; '
        f'<strong>{wk_pct}%</strong> on weekends. '
        f'<strong>{pct_350}%</strong> missed the 3.50 HPRD total component alone. All <strong>596</strong> homes are in the '
        f'<a href="/insights/ny-minimum-staffing">full report</a>.</p>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"found that [\d,]+ facility-days &mdash; <strong>[\d.]+%</strong> &mdash; fell below",
        f"found that {fmt_int(below)} facility-days &mdash; <strong>{pct}%</strong> &mdash; missed at least one mapped part of the standard",
        html,
        count=1,
    )
    html = re.sub(
        r"On weekends, <strong>[\d.]+%</strong> of facility-days were below that threshold\.",
        f"On weekends, <strong>{wk_pct}%</strong> of facility-days missed at least one mapped floor.",
        html,
        count=1,
    )
    html = re.sub(
        r"<strong>[\d.]+%</strong> of facility-days were below <strong>3\.50 hours per resident day</strong> "
        r"\([\d,]+ of 216,134\)[^<]*\.",
        f"<strong>{pct_350}%</strong> of facility-days missed the <strong>3.50 HPRD total component alone</strong> "
        f"({fmt_int(below_350)} of 216,134). The full mapped standard (3.50 total + 2.20 CNA-side + 1.10 licensed) "
        f"was missed on <strong>{pct}%</strong> of days ({fmt_int(below)} facility-days).",
        html,
        count=1,
    )
    html = re.sub(
        r"<strong>[\d.]+%</strong> of Saturday&ndash;Sunday facility-days[^<]*<strong>[\d.]+%</strong>\)[^<]*<strong>[\d.]+%</strong>[^<]*<strong>[\d.]+%</strong>\)\.",
        f"<strong>{wk_pct}%</strong> of Saturday&ndash;Sunday facility-days missed part of the mapped standard "
        f"({fmt_int(wk_below)} of {fmt_int(wk_fd)}). In NYC, weekends were <strong>{nyc_wk_pct}%</strong> "
        f"({fmt_int(nyc_wk_below)} of {fmt_int(nyc_fd)}). Sunday was the highest day of the week "
        f"(<strong>{sun_pct}%</strong>); Wednesday the lowest (<strong>{wed_pct}%</strong>).",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<p class="finding-row-body"><strong>[\d.]+%</strong> of Saturday&ndash;Sunday facility-days were below the standard \([\d,]+ of [\d,]+\)\. In NYC, weekends were <strong>[\d.]+%</strong> \([\d,]+ of [\d,]+\)\. Sunday was the highest day of the week \(<strong>[\d.]+%</strong>\); Wednesday the lowest \(<strong>[\d.]+%</strong>\)\.</p>',
        f'<p class="finding-row-body"><strong>{wk_pct}%</strong> of Saturday&ndash;Sunday facility-days missed part of the mapped standard '
        f"({fmt_int(wk_below)} of {fmt_int(wk_fd)}). In NYC, weekends were <strong>{nyc_wk_pct}%</strong> "
        f"({fmt_int(nyc_wk_below)} of {fmt_int(nyc_fd)}). Sunday was the highest day of the week "
        f"(<strong>{sun_pct}%</strong>); Wednesday the lowest (<strong>{wed_pct}%</strong>).</p>",
        html,
        count=1,
    )
    html = re.sub(
        r'<p class="lead"><strong>BROOKLYN, N\.Y\.</strong> &mdash; PBJ320 analyzed 216,134 daily staffing records from 596 New York nursing homes in 2025 and found that [\d,]+ facility-days &mdash; <strong>[\d.]+%</strong> &mdash; reported staffing below New York&rsquo;s <strong>3\.50 hours per resident day</strong> standard\. On weekends, <strong>[\d.]+%</strong> of facility-days missed at least one mapped floor\.</p>',
        f'<p class="lead"><strong>BROOKLYN, N.Y.</strong> &mdash; PBJ320 analyzed 216,134 daily staffing records from 596 New York nursing homes in 2025 and found that {fmt_int(below)} facility-days &mdash; <strong>{pct}%</strong> &mdash; missed at least one mapped part of New York&rsquo;s daily staffing standard (3.50 total + 2.20 CNA-side + 1.10 licensed HPRD). On weekends, <strong>{wk_pct}%</strong> of facility-days missed at least one mapped floor.</p>',
        html,
        count=1,
    )
    html = re.sub(
        r"<strong>\d+ homes \([\d.]+%\)</strong> were below the minimum on every day in 2025; "
        r"<strong>\d+ homes</strong> on at least <strong>90%</strong> of days\.",
        f"<strong>{every_day} homes ({chronic_pct}%)</strong> were below the 3.50 HPRD component on every day in 2025; "
        f"<strong>{at_least_90} homes</strong> on at least <strong>90%</strong> of days.",
        html,
        count=1,
    )
    html = re.sub(
        r"Informative PBJ mapping only \(not DOH enforcement\): mapped to 3\.5 total, 2\.2 CNA-side, and 1\.1 licensed HPRD, "
        r"<strong>[\d.]+%</strong> of facility-days met all three; <strong>[\d.]+%</strong> missed at least one\.",
        f"Informative PBJ mapping only (not DOH enforcement): mapped to 3.5 total, 2.2 CNA-side, and 1.1 licensed HPRD, "
        f"<strong>{met_pct}%</strong> of facility-days met all three; "
        f"<strong>{miss_pct}%</strong> missed at least one.",
        html,
        count=1,
    )

    fp = round(float(next(p for p in mode["curves"]["ny_for_profit"] if abs(p["threshold"] - 3.5) < 0.01)["pct_below"]), 1)
    np = round(float(next(p for p in mode["curves"]["ny_non_profit"] if abs(p["threshold"] - 3.5) < 0.01)["pct_below"]), 1)
    gov = round(float(next(p for p in mode["curves"]["ny_government"] if abs(p["threshold"] - 3.5) < 0.01)["pct_below"]), 1)
    nyc_fp = round(float(next(p for p in mode["curves"]["nyc_for_profit"] if abs(p["threshold"] - 3.5) < 0.01)["pct_below"]), 1)
    nyc_gov = round(float(next(p for p in mode["curves"]["nyc_government"] if abs(p["threshold"] - 3.5) < 0.01)["pct_below"]), 1)

    html = re.sub(
        r"For-profit homes ran higher than nonprofit and government operators: NYC for-profit <strong>[\d.]+%</strong>, statewide for-profit <strong>[\d.]+%</strong>; statewide nonprofit <strong>[\d.]+%</strong>, government <strong>[\d.]+%</strong> \(NYC government <strong>[\d.]+%</strong>\)\.",
        f"For-profit homes ran higher than nonprofit and government operators (3.50 component): NYC for-profit <strong>{nyc_fp}%</strong>, statewide for-profit <strong>{fp}%</strong>; statewide nonprofit <strong>{np}%</strong>, government <strong>{gov}%</strong> (NYC government <strong>{nyc_gov}%</strong>).",
        html,
        count=1,
    )

    PRESS.write_text(html, encoding="utf-8")
    print(f"Patched {PRESS} ({PRESS.stat().st_size:,} bytes)")


if __name__ == "__main__":
    patch_press()
