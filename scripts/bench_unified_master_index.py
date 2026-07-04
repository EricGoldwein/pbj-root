#!/usr/bin/env python3
"""Benchmark provider cold path after unified facility CSV master index."""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["RENDER"] = "1"
os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
os.environ["PBJ_PROVIDER_PERF_LOG"] = "1"

CCNS = ("676230", "035297", "015009", "525281")


def _rss_mb() -> float | None:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def main() -> int:
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    log_buf = StringIO()
    old_stdout = sys.stdout

    class Tee:
        def write(self, s):
            old_stdout.write(s)
            log_buf.write(s)

        def flush(self):
            old_stdout.flush()

    sys.stdout = Tee()

    from app import app, clear_provider_page_cache

    client = app.test_client()
    rows = []

    def run(label: str, path: str, *, clear: bool = False):
        if clear:
            clear_provider_page_cache()
        t0 = time.perf_counter()
        r = client.get(path, headers={"User-Agent": "Mozilla/5.0"})
        ms = round((time.perf_counter() - t0) * 1000, 1)
        cache = r.headers.get("X-PBJ-Provider-Cache", "-")
        rows.append((label, r.status_code, ms, cache))
        print(f"{label:32} {r.status_code} {ms:8.1f}ms cache={cache} rss={_rss_mb()}MB")

    print("=== unified master index bench ===")
    run("health", "/health")
    run("provider/676230 cold", "/provider/676230", clear=True)
    run("provider/676230 hit", "/provider/676230")
    run("provider/035297 cold", "/provider/035297", clear=True)
    run("provider/035297 hit", "/provider/035297")
    run("provider/015009 cold", "/provider/015009", clear=True)
    run("provider/525281 cold", "/provider/525281", clear=True)

    log = log_buf.getvalue()
    master = "facility_quarterly_master" in log
    separate_contract = log.count('"index": "state_contract_median"')
    separate_pct = log.count('"index": "state_percentile_hprd"')
    separate_latest = log.count("facility_latest_hprd ccns=")
    print("\n=== index build log ===")
    print(f"master_build={master}")
    print(f"separate_contract_logs={separate_contract}")
    print(f"separate_percentile_logs={separate_pct}")
    print(f"separate_latest_hprd_logs={separate_latest}")

    sys.stdout = old_stdout
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
