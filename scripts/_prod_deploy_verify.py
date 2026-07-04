#!/usr/bin/env python3
"""Production deploy gate verification for NY staffing report."""
from __future__ import annotations

import json
import re
import sys
import zipfile
import io
from pathlib import Path

import urllib.request

BASE = "https://www.pbj320.com"
PREVIEW = f"{BASE}/preview/ny-staffing-compliance-2025/p4v8nq"
UA = {"User-Agent": "pbj320-deploy-verify/1.0"}


def fetch(url: str) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace"), dict(resp.headers)


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


def lookup_curve(curve: list, threshold: float = 3.5) -> dict:
    for pt in curve:
        if abs(pt["threshold"] - threshold) < 0.001:
            return pt
    raise KeyError(threshold)


def main() -> int:
    urls = {
        "report": f"{BASE}/insights/ny-minimum-staffing",
        "preview": PREVIEW,
        "press": f"{BASE}/insights/ny-minimum-staffing/press",
        "hub": f"{BASE}/insights",
        "classic": f"{BASE}/insights/ny-minimum-staffing/classic",
        "xlsx": f"{BASE}/downloads/PBJ320_NY_2025_daily_staffing_verification_file.xlsx",
        "zip": f"{BASE}/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs.zip",
    }
    pages: dict[str, str] = {}
    statuses: dict[str, int] = {}
    for key, url in urls.items():
        try:
            st, body, hdrs = fetch(url)
            statuses[key] = st
            pages[key] = body
            if key in ("xlsx", "zip"):
                print(f"{key}: HTTP {st} len={hdrs.get('Content-Length', len(body.encode()) if key=='xlsx' else 'bin')} ct={hdrs.get('Content-Type')}")
            else:
                print(f"{key}: HTTP {st} bytes={len(body)}")
        except Exception as exc:
            print(f"{key}: ERROR {exc}", file=sys.stderr)
            statuses[key] = 0
            pages[key] = ""

    report = pages.get("report", "")
    if not report:
        return 1

    interactive = extract_json_after("window.PBJ_REPORT_INTERACTIVE = ", report)
    mode = interactive["modes"]["total"]
    curves = mode["curves"]
    cfd = mode.get("curve_facility_days") or {}

    def row(curve_key: str, wknd_key: str | None = None) -> dict:
        pt = lookup_curve(curves[curve_key])
        fd = int(cfd.get(curve_key) or mode["facility_days_total"])
        out = {"fd": fd, "below": int(pt["below"]), "pct": round(float(pt["pct_below"]), 1)}
        if wknd_key:
            wk = lookup_curve(curves[wknd_key])
            wk_fd = int(cfd.get(wknd_key) or 0)
            wk_bl = int(wk["below"])
            wkday_fd = fd - wk_fd
            wkday_bl = int(pt["below"]) - wk_bl
            out["wkend"] = {"fd": wk_fd, "below": wk_bl, "pct": round(float(wk["pct_below"]), 1)}
            out["wkday"] = {
                "fd": wkday_fd,
                "below": wkday_bl,
                "pct": round(100.0 * wkday_bl / wkday_fd, 1) if wkday_fd else 0.0,
            }
        return out

    values = {
        "all_ny": row("all_ny"),
        "nyc": row("nyc", "weekend_nyc"),
        "for_profit": row("ny_for_profit"),
        "non_profit": row("ny_non_profit"),
        "government": row("ny_government"),
    }
    print("VALUES", json.dumps(values, indent=2))

    stale_tokens = [
        "17,082", "17082", "17,208", "17208", "81.7%", "82.3%",
        "60,389", "60389", "33,809", "33809", "43,181", "43181",
        "14,061", "14061", "442 facility-days", 'provider_name": "nan"',
    ]
    stale_hits: dict[str, list[str]] = {}
    for name in ("report", "preview", "press", "hub"):
        body = pages.get(name, "")
        hits = [t for t in stale_tokens if t in body]
        stale_hits[name] = hits
        print(f"STALE {name}: {hits or 'none'}")

    footer_ok = "Methods &amp; sources" in report and "PBJ320 verification workbook" in report
    note_ok = "Rows show daily shortfalls" in report
    press_wknd = "82.4%" in pages.get("press", "")
    press_methods = "quarter" in pages.get("press", "").lower() and "Provider Info" in pages.get("press", "")
    print(f"COPY footer_ok={footer_ok} note_ok={note_ok} press_wknd={press_wknd} press_methods={press_methods}")

    classic_st = statuses.get("classic", 0)
    classic_loc = ""
    if pages.get("classic"):
        m = re.search(r"insights/ny-minimum-staffing/classic", pages["classic"])
    print(f"CLASSIC status={classic_st}")

    # reconciliation from zip if 200
    if statuses.get("zip") == 200:
        raw = urllib.request.urlopen(
            urllib.request.Request(urls["zip"], headers=UA), timeout=120
        ).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            recon = zf.read("reconciliation_checks.csv").decode("utf-8")
            ww = zf.read("weekend_weekday_summary.csv").decode("utf-8")
        print("ZIP recon snippet:", [ln for ln in recon.splitlines() if "NYC weekend" in ln][:2])
        print("ZIP ww nyc:", [ln for ln in ww.splitlines() if "NYC" in ln or "nyc" in ln][:4])

    # playwright
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(urls["report"] + "#calendar", wait_until="networkidle", timeout=120_000)
            page.wait_for_selector("#dowChart", timeout=30_000)
            page.wait_for_timeout(1200)
            init = page.evaluate(
                """() => {
                  const c = window.PBJ320Threshold.chartStore.dowChart;
                  return { labels: c.data.labels.slice(), data: c.data.datasets[0].data.slice(), yMin: c.scales.y.min, yMax: c.scales.y.max, ticks: c.scales.y.ticks.map(t=>t.label) };
                }"""
            )
            page.evaluate(
                """() => {
                  const s = document.getElementById('hprd-slider');
                  s.value = '4.00';
                  s.dispatchEvent(new Event('input', { bubbles: true }));
                  s.dispatchEvent(new Event('change', { bubbles: true }));
                }"""
            )
            page.wait_for_timeout(800)
            after = page.evaluate(
                """() => {
                  const c = window.PBJ320Threshold.chartStore.dowChart;
                  return { labels: c.data.labels.slice(), data: c.data.datasets[0].data.slice() };
                }"""
            )
            browser.close()
        print("CHART init", init)
        print("CHART after", after)
    except Exception as exc:
        print(f"CHART ERROR {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
