#!/usr/bin/env python3
"""Local cold-provider timing (Render-sim cache on)."""
from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["RENDER"] = "1"
os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
os.environ["PBJ_PROVIDER_PERF_LOG"] = "1"

for mod in list(sys.modules):
    if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
        del sys.modules[mod]

import json
import random

from app import app, clear_provider_page_cache

data = json.loads((ROOT / "search_index.json").read_text(encoding="utf-8"))
ccns = [str(f["c"]).zfill(6) for f in data.get("f") or [] if f.get("c")]
rng = random.Random(20260521)
sample = rng.sample(ccns, 10)

clear_provider_page_cache()
times: list[float] = []
charts: list[float] = []
with app.test_client() as client:
    for ccn in sample:
        clear_provider_page_cache()
        t0 = time.perf_counter()
        r = client.get(f"/provider/{ccn}", headers={"User-Agent": "Mozilla/5.0"})
        ms = round((time.perf_counter() - t0) * 1000, 1)
        times.append(ms)
        print(ccn, r.status_code, r.headers.get("X-PBJ-Provider-Cache"), f"{ms}ms")

print("median_ms", round(statistics.median(times), 1), "max_ms", max(times))
