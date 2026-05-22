#!/usr/bin/env python3
"""Focused production validation for /report (median + network)."""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.pbj320.com"
MEDIAN_COLS = [
    "Total_Nurse_HPRD_Median",
    "RN_HPRD_Median",
    "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD_Median",
    "Nurse_Assistant_HPRD_Median",
    "Contract_Percentage_Median",
]


def get(url: str) -> tuple[str, dict]:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read().decode("utf-8", "replace"), dict(r.headers)


def http_checks() -> dict:
    html, _rh = get(f"{BASE}/report")
    st, _sh = get(f"{BASE}/state_quarterly_metrics.csv")
    block = html[html.find("async function loadData") : html.find("function setupEventHandlers")][:12000]
    header = st.split("\n", 1)[0]
    missing = [c for c in MEDIAN_COLS if c not in header]
    spot = {}
    for abbr in ("AK", "DC", "NH"):
        for row in csv.DictReader(io.StringIO(st)):
            if row.get("STATE") == abbr and row.get("CY_Qtr") == "2025Q4":
                spot[abbr] = {
                    "avg": round(float(row["Total_Nurse_HPRD"]), 2),
                    "median": round(float(row.get("Total_Nurse_HPRD_Median") or 0), 2),
                }
                break
    perf_entries = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            page = p.chromium.launch(headless=True).new_page()
            facility_urls: list[str] = []

            def on_request(req):
                if "facility_quarterly_metrics_latest" in req.url:
                    facility_urls.append(req.url)

            page.on("request", on_request)
            page.goto(f"{BASE}/report", wait_until="networkidle", timeout=120_000)
            perf = page.evaluate(
                """() => performance.getEntriesByType('resource')
                  .filter(e => e.name.includes('facility_quarterly') || e.name.includes('state_quarterly'))
                  .map(e => ({name: e.name, transferSize: e.transferSize, duration: e.duration}))"""
            )
            page.evaluate("document.getElementById('medianToggleMap').click()")
            page.wait_for_timeout(1200)
            legend_on = page.locator(".legend-title").first.inner_text(timeout=5000)
            median_checked = page.evaluate(
                "document.getElementById('medianToggleMap').checked"
            )
            page.evaluate("document.getElementById('medianToggleMap').click()")
            page.wait_for_timeout(600)
            legend_off = page.locator(".legend-title").first.inner_text(timeout=5000)
            perf_entries = perf
    except Exception as exc:
        perf_entries = [{"playwright_error": str(exc)}]
        facility_urls = []
        legend_on = legend_off = ""
        median_checked = False

    return {
        "report_bytes": len(html),
        "state_csv_bytes": len(st),
        "deferred_loader_gone": "loadFacilityQuarterlyDeferred" not in html,
        "hasStateMedianColumns_js": "hasStateMedianColumns" in html,
        "facility_latest_in_html": "facility_quarterly_metrics_latest.csv" in html,
        "initial_loadData_fetches": re.findall(r"fetch\(['\"]([^'\"]+)['\"]", block),
        "median_cols_ok": not missing,
        "median_cols_missing": missing,
        "spot_2025Q4": spot,
        "ssr_fp_numeric": len(re.findall(r'data-report-ssr-fp="1"', html)),
        "facility_request_urls": facility_urls,
        "resource_timing": perf_entries,
        "legend_median_on": legend_on,
        "legend_median_off": legend_off,
        "median_toggle_checked": median_checked,
    }


def main() -> int:
    out = http_checks()
    print(json.dumps(out, indent=2))
    ok = (
        out["deferred_loader_gone"]
        and out["median_cols_ok"]
        and out["hasStateMedianColumns_js"]
        and not out.get("facility_request_urls")
        and "Median" in (out.get("legend_median_on") or "")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
