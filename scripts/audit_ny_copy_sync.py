#!/usr/bin/env python3
"""Audit NY report public prose against NY-mapped default anchors.

Verified from: insights-ny-minimum-staffing.html window.PBJ_REPORT_* embeds.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ROOT / "insights-ny-minimum-staffing.html",
    ROOT / "insights-ny-minimum-staffing-press.html",
    ROOT / "insights_posts" / "ny-minimum-staffing.md",
    ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs" / "readme.csv",
]

STALE_PRIMARY = [
    (r"\b101[,\s]?779\b", "101,779 default below-days (broad only)"),
    (r"\b47\.1\s*%", "47.1% default statewide rate (broad only)"),
    (r"\b47[,\s]?347\b", "47,347 weekend below (broad only)"),
    (r"\b76\.9\s*%", "76.9% weekend rate (broad only)"),
    (r"\b13[,\s]?983\b", "13,983 NYC weekend below (broad only)"),
    (r"\b82\.4\s*%", "82.4% NYC weekend (broad only)"),
    (r"\b39\.7\s*%", "39.7% met-all-three (old broad/admin mapping)"),
    (r"<strong>34</strong> were below", "34 homes 100% below (broad only)"),
    (r"<strong>95</strong> on at least", "95 homes >=90% below (broad only)"),
]

COMPONENT_OK = re.compile(
    r"standard-component-note|3\.50 total component|3\.50 HPRD|scenario|component alone|"
    r"below-cell|pct-cell|slice-row|ownership-slices|Media advisory|og:description|"
    r"twitter:description|3\.50 hours per resident|reported staffing below",
    re.I,
)

COMPARISON_OK = re.compile(
    r"broad|comparison|compare|sensitivity|below_curve_broad|broad_pbj",
    re.I,
)

PBJ_MARKER = re.compile(r"window\.PBJ_REPORT_\w+\s*=\s*")
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.DOTALL)
STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.DOTALL)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_embeds(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        m = PBJ_MARKER.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        start = m.end()
        depth = 0
        j = start
        while j < len(text):
            c = text[j]
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        i = j
    return "".join(out)


def visible_prose(path: Path, raw: str) -> str:
    if path.suffix.lower() == ".md":
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end != -1:
                return raw[end + 3 :]
        return raw
    text = SCRIPT.sub("", raw)
    text = STYLE.sub("", text)
    text = strip_embeds(text)
    text = CSS_COMMENT.sub("", text)
    return text


def extract_json(marker: str, text: str) -> dict:
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
    raise ValueError(marker)


def main() -> int:
    report = ROOT / "insights-ny-minimum-staffing.html"
    html = report.read_text(encoding="utf-8")
    interactive = extract_json("window.PBJ_REPORT_INTERACTIVE = ", html)
    statute = extract_json("window.PBJ_REPORT_NY_STATUTE = ", html)
    primary = None
    if "window.PBJ_REPORT_STANDARD_PRIMARY = " in html:
        primary = extract_json("window.PBJ_REPORT_STANDARD_PRIMARY = ", html)
    mode = interactive["modes"][interactive.get("default_mode", "ny_mapped_non_admin_hprd")]
    all_pt = next(p for p in mode["curves"]["all_ny"] if abs(p["threshold"] - 3.5) < 0.01)
    wk_pt = next(p for p in mode["curves"]["weekend"] if abs(p["threshold"] - 3.5) < 0.01)
    nyc_pt = next(p for p in mode["curves"]["weekend_nyc"] if abs(p["threshold"] - 3.5) < 0.01)

    issues: list[str] = []
    ok: list[str] = []

    for path in TARGETS:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        prose = visible_prose(path, raw)
        for pattern, msg in STALE_PRIMARY:
            for m in re.finditer(pattern, prose, re.I):
                window = prose[max(0, m.start() - 80) : m.end() + 80]
                if COMPARISON_OK.search(window):
                    continue
                if COMPONENT_OK.search(window):
                    continue
                snippet = re.sub(r"\s+", " ", window).strip()
                issues.append(f"{path.relative_to(ROOT)}: {msg} — …{snippet}…")

    hero_below = re.search(
        r'class="kpi-num-value">([\d,]+)</span><span class="kpi-num-unit"> Days',
        html,
    )
    hero_pct = re.search(
        r'aria-label="[\d.]+% percent"><span class="kpi-num-value">([\d.]+)%',
        html,
    )
    hero_below_target = int(statute["facility_days_below_any_ny_requirement"])
    hero_pct_target = round(float(statute["pct_below_any_ny_requirement"]), 1)
    if primary:
        hero_below_target = int(primary["below_days"])
        hero_pct_target = round(float(primary["below_pct"]), 1)
    if hero_below and int(hero_below.group(1).replace(",", "")) != hero_below_target:
        issues.append(f"hero below-days {hero_below.group(1)} != {hero_below_target}")
    else:
        ok.append(f"hero below-days {hero_below_target:,}")
    if hero_pct and abs(float(hero_pct.group(1)) - hero_pct_target) > 0.05:
        issues.append(f"hero pct {hero_pct.group(1)} != {hero_pct_target}")
    else:
        ok.append(f"hero pct {hero_pct_target}%")

    comp_note = re.search(
        r'standard-component-note[^>]*>.*?([\d,]+) facility-days \(([\d.]+)%\)',
        html,
        re.DOTALL,
    )
    if comp_note:
        comp_below = int(comp_note.group(1).replace(",", ""))
        comp_pct = float(comp_note.group(2))
        if comp_below != int(all_pt["below"]):
            issues.append(f"3.50 component note {comp_below} != curve {all_pt['below']}")
        elif abs(comp_pct - round(all_pt["pct_below"], 1)) > 0.05:
            issues.append(f"3.50 component pct {comp_pct} != curve {all_pt['pct_below']:.1f}")
        else:
            ok.append(f"3.50 component note {comp_below:,} ({comp_pct}%)")

    met_pct = round(float(statute["pct_meets_all_ny_requirements"]), 1)
    met_card = re.search(
        r'appendix-card">\s*<div class="appendix-card-stat">\s*'
        r'<span class="appendix-card-num" aria-label="([\d.]+) percent"',
        html,
        re.DOTALL,
    )
    if met_card and abs(float(met_card.group(1)) - met_pct) > 0.05:
        issues.append(f"role-floor met-all-three card {met_card.group(1)}% != {met_pct}%")
    else:
        ok.append(f"role-floor met-all-three card {met_pct}%")

    cna_pct = round(float(statute["pct_below_cna"]), 1)
    cna_card = re.search(
        r'appendix-card--cna-miss">\s*<div class="appendix-card-stat">\s*'
        r'<span class="appendix-card-num" aria-label="([\d.]+) percent"',
        html,
        re.DOTALL,
    )
    if cna_card and abs(float(cna_card.group(1)) - cna_pct) > 0.05:
        issues.append(f"CNA-side card {cna_card.group(1)}% != {cna_pct}%")
    else:
        ok.append(f"CNA-side card {cna_pct}%")

    if "include_don_sensitivity" not in statute:
        issues.append("PBJ_REPORT_NY_STATUTE missing include_don_sensitivity block")
    else:
        inc = statute["include_don_sensitivity"]
        if inc.get("lpn_rn_hours_columns") != ["Hrs_RN", "Hrs_LPN", "Hrs_RNDON"]:
            issues.append("include-DON licensed columns not RN+LPN+RN DON")
        else:
            ok.append("include-DON sensitivity uses RN+LPN+RN DON licensed floor")

    required_methods = [
        "N.Y. Public Health Law § 2895-b",
        "descriptive",
        "NY DOH enforcement",
        "comparison toggle",
    ]
    methods = visible_prose(report, html)
    for phrase in required_methods:
        if phrase.lower() not in methods.lower():
            issues.append(f"methods missing phrase: {phrase!r}")

    print("=== NY copy sync audit ===\n")
    print(f"OK ({len(ok)}):")
    for line in ok:
        print(f"  + {line}")
    print(f"\nISSUES ({len(issues)}):")
    for line in issues:
        print(f"  ! {line}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
