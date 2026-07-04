#!/usr/bin/env python3
"""Compare provider cold timing with vs without facility-index warmup (fresh subprocess each run)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CCN_PRIMARY = "676230"
CCN_SECOND = "035297"
WARMUP_SECRET = "bench-local-warmup-secret"


def _child_script() -> str:
    return r'''
import json, os, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
os.environ["RENDER"] = "1"
os.environ["PBJ_SKIP_PROVIDER_PAGE_CACHE"] = "0"
os.environ["PBJ_PROVIDER_PERF_LOG"] = "1"
mode = sys.argv[2]  # no_warmup | with_warmup
ccn_primary = sys.argv[3]
ccn_second = sys.argv[4]
secret = sys.argv[5]

for mod in list(sys.modules):
    if mod in ("app", "pbj_provider_perf") or mod.startswith("app."):
        del sys.modules[mod]

from app import app, clear_provider_page_cache

def rss_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None

def hit_provider(client, ccn):
    clear_provider_page_cache()
    t0 = time.perf_counter()
    r = client.get(f"/provider/{ccn}", headers={"User-Agent": "Mozilla/5.0"})
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "ccn": ccn,
        "status": r.status_code,
        "cache": r.headers.get("X-PBJ-Provider-Cache"),
        "ms": ms,
    }

out = {"mode": mode, "rss_mb_start": rss_mb()}
with app.test_client() as client:
    t_health = time.perf_counter()
    hr = client.get("/health")
    out["health_ms"] = round((time.perf_counter() - t_health) * 1000, 2)
    out["health_status"] = hr.status_code

    if mode == "with_warmup":
        os.environ["PBJ_WARMUP_SECRET"] = secret
        tw = time.perf_counter()
        wr = client.post(
            "/warmup/facility-indexes",
            headers={"X-PBJ-Warmup-Key": secret},
        )
        out["warmup_status"] = wr.status_code
        try:
            out["warmup_body"] = wr.get_json()
        except Exception:
            out["warmup_body"] = wr.get_data(as_text=True)[:500]
        out["warmup_http_ms"] = round((time.perf_counter() - tw) * 1000, 1)

    out["first_cold"] = hit_provider(client, ccn_primary)
    # HTML cache HIT before second CCN (clear_provider_page_cache wipes all entries)
    t0 = time.perf_counter()
    r = client.get(f"/provider/{ccn_primary}", headers={"User-Agent": "Mozilla/5.0"})
    out["cache_hit"] = {
        "ccn": ccn_primary,
        "status": r.status_code,
        "cache": r.headers.get("X-PBJ-Provider-Cache"),
        "ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    out["second_cold"] = hit_provider(client, ccn_second)

out["rss_mb_end"] = rss_mb()
print(json.dumps(out))
'''


def run_mode(mode: str) -> dict:
    env = os.environ.copy()
    env["PBJ_WARMUP_SECRET"] = WARMUP_SECRET
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            _child_script(),
            str(ROOT),
            mode,
            CCN_PRIMARY,
            CCN_SECOND,
            WARMUP_SECRET,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"mode={mode} failed rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def main() -> int:
    print("Fresh-process bench (b19f7ac + Option A warmup endpoint)")
    print(f"CCNs: first={CCN_PRIMARY} second={CCN_SECOND}\n")
    no_warm = run_mode("no_warmup")
    with_warm = run_mode("with_warmup")
    table = {
        "no_warmup": no_warm,
        "with_warmup": with_warm,
    }
    print(json.dumps(table, indent=2))
    print("\n--- summary (ms) ---")
    for label, row in (("no warmup", no_warm), ("with index warmup", with_warm)):
        w = row.get("warmup_body") or {}
        print(
            f"{label}: health={row.get('health_ms')} "
            f"warmup_total={w.get('total_ms', 'n/a')} "
            f"first_cold={row['first_cold']['ms']} ({row['first_cold']['cache']}) "
            f"second_cold={row['second_cold']['ms']} ({row['second_cold']['cache']}) "
            f"hit={row['cache_hit']['ms']} ({row['cache_hit']['cache']}) "
            f"rss_end={row.get('rss_mb_end')}MB"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
