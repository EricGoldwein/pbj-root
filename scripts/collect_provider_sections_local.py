#!/usr/bin/env python3
"""Local 10-CCN cold render: aggregate sections_ms from [PBJ_PROVIDER] logs (Render-sim)."""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["RENDER"] = "1"
os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
os.environ["PBJ_PROVIDER_PERF_LOG"] = "1"

for mod in list(sys.modules):
    if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
        del sys.modules[mod]

import builtins

from app import app, clear_provider_page_cache

import argparse

parser = argparse.ArgumentParser(description="Aggregate provider cold-render sections_ms locally.")
parser.add_argument("--limit", type=int, default=10)
parser.add_argument("--seed", type=int, default=20260525)
args = parser.parse_args()

data = json.loads((ROOT / "search_index.json").read_text(encoding="utf-8"))
ccns = [str(f["c"]).zfill(6) for f in data.get("f") or [] if f.get("c")]
sample = random.Random(args.seed).sample(ccns, min(args.limit, len(ccns)))

logs: list[dict] = []
real_print = builtins.print
buf = StringIO()


def capture_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    buf.write(msg + "\n")
    if kwargs.get("file") is sys.stderr:
        real_print(*args, **kwargs)


builtins.print = capture_print

times: list[float] = []
with app.test_client() as client:
    for ccn in sample:
        clear_provider_page_cache()
        buf.truncate(0)
        buf.seek(0)
        t0 = time.perf_counter()
        r = client.get(f"/provider/{ccn}", headers={"User-Agent": "Mozilla/5.0"})
        ms = round((time.perf_counter() - t0) * 1000, 1)
        times.append(ms)
        for line in buf.getvalue().splitlines():
            if line.startswith("[PBJ_PROVIDER]"):
                try:
                    logs.append(json.loads(line.split("[PBJ_PROVIDER]", 1)[1].strip()))
                except json.JSONDecodeError:
                    pass
        real_print(ccn, r.status_code, f"{ms}ms", logs[-1].get("sections_ms") if logs else None)

builtins.print = real_print

section_vals: dict[str, list[float]] = defaultdict(list)
for row in logs:
    for k, v in (row.get("sections_ms") or {}).items():
        section_vals[k].append(float(v))

print("\n=== COLD ELAPSED ===")
print(f"median_ms={round(statistics.median(times), 1)} max_ms={max(times)}")
print("\n=== SECTION MEDIANS (ms) ===")
for name, vals in sorted(section_vals.items(), key=lambda kv: -statistics.median(kv[1])):
    print(f"  {name}: median={round(statistics.median(vals), 1)} max={round(max(vals), 1)} n={len(vals)}")
