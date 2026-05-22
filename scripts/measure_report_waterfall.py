#!/usr/bin/env python3
"""Measure /report initial payload and whether loadData still fetches facility CSV."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("RENDER", "1")
os.environ.setdefault("PBJ_REPORT_PERF_LOG", "1")

for mod in list(sys.modules):
    if mod in ("app",) or mod.startswith("app."):
        del sys.modules[mod]

from app import app  # noqa: E402

STATIC_PATHS = [
    "state_quarterly_metrics.csv",
    "national_quarterly_metrics.csv",
    "cms_region_state_mapping.csv",
    "cms_region_quarterly_metrics.csv",
    "facility_quarterly_metrics_latest.csv",
]


def file_mb(rel: str) -> float | None:
    p = ROOT / rel
    if not p.is_file():
        return None
    return round(p.stat().st_size / (1024 * 1024), 2)


def main() -> None:
    report_html = (ROOT / "report.html").read_text(encoding="utf-8", errors="replace")
    load_block = report_html[report_html.find("async function loadData"): report_html.find("function setupEventHandlers")]
    initial_fetches = re.findall(r"fetch\(['\"]([^'\"]+)['\"]", load_block[:8000])
    deferred_fq = "facility_quarterly_metrics_latest.csv" in load_block and "loadFacilityQuarterlyDeferred" in load_block

    print("=== REPORT.HTML loadData FETCH AUDIT ===")
    print("Initial fetch() URLs in loadData (first ~8k chars of function):")
    for u in initial_fetches:
        mb = file_mb(u.lstrip("/"))
        print(f"  - {u}" + (f"  (~{mb} MB on disk)" if mb is not None else ""))
    print(f"facility_quarterly in INITIAL parallel batch: {'facility_quarterly_metrics_latest.csv' in initial_fetches[:6]}")
    print(f"facility_quarterly deferred helper present: {deferred_fq}")

    with app.test_client() as client:
        t0 = time.perf_counter()
        r = client.get("/report", headers={"User-Agent": "Mozilla/5.0"})
        html_ms = round((time.perf_counter() - t0) * 1000, 1)
        body = r.get_data(as_text=True)
        html_bytes = len(r.get_data())
        cc = r.headers.get("Cache-Control", "")
        fp_cells = len(re.findall(r'data-report-ssr-fp="1"', body))
        fp_pct_cells = len(re.findall(r'col-forprofit[^>]*>\d+\.\d+%', body))
        has_fp_bootstrap = "__REPORT_FP_BY_STATE__" in body or "window.__REPORT_FP_BY_STATE__" in body

        t1 = time.perf_counter()
        fp = client.get("/report/embed/fp?quarter=2025Q4")
        fp_ms = round((time.perf_counter() - t1) * 1000, 1)
        fp_hit = fp.headers.get("X-PBJ-Report-Fp-Cache", "?")
        fp_embed_ms = fp.headers.get("X-PBJ-Report-Embed-Ms", "?")
        fp_json = fp.get_json() if fp.is_json else {}

        t2 = time.perf_counter()
        fp2 = client.get("/report/embed/fp?quarter=2025Q4")
        fp2_ms = round((time.perf_counter() - t2) * 1000, 1)
        fp2_hit = fp2.headers.get("X-PBJ-Report-Fp-Cache", "?")

        state = client.get("/state/wyoming", headers={"User-Agent": "Mozilla/5.0"})
        state_cc = state.headers.get("Cache-Control", "")

    print("\n=== SERVER /report HTML ===")
    print(f"status={r.status_code} bytes={html_bytes} report_html_ms~{html_ms} Cache-Control={cc}")
    print(f"SSR for-profit cells (data-report-ssr-fp): {fp_cells}")
    print(f"SSR for-profit with numeric %: {fp_pct_cells}")
    print(f"FP bootstrap script injected: {has_fp_bootstrap}")

    print("\n=== /report/embed/fp ===")
    print(f"first: {fp_ms}ms cache={fp_hit} embed_ms={fp_embed_ms} states={len((fp_json or {}).get('states') or {})} warning={(fp_json or {}).get('embedWarning')}")
    print(f"second: {fp2_ms}ms cache={fp2_hit}")

    print("\n=== /state/wyoming ===")
    print(f"status={state.status_code} Cache-Control={state_cc}")

    print("\n=== STATIC FILE SIZES ===")
    for rel in STATIC_PATHS:
        mb = file_mb(rel)
        if mb is not None:
            print(f"  {rel}: {mb} MB")


if __name__ == "__main__":
    main()
