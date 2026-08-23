"""Measure compact evidence bundle sizes, cold/warm lookup latency, RSS."""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import staffing_evidence_bundle as seb  # noqa: E402


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def main() -> int:
    app_root = str(REPO)
    seb.invalidate_caches()
    baseline = rss_mb()

    db = seb.materialize_sqlite(app_root)
    gz = Path(seb.sqlite_gzip_path(app_root))
    manifest = seb.load_manifest(app_root, force=True) or {}
    after_open = rss_mb()

    if not db or not os.path.isfile(db):
        print(json.dumps({"ok": False, "error": "no sqlite"}))
        return 1

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row_count = conn.execute("SELECT COUNT(*) FROM day_fact").fetchone()[0]
    sample = conn.execute(
        "SELECT ccn, work_date FROM day_fact ORDER BY ccn, work_date LIMIT 1"
    ).fetchone()
    # spread samples
    samples = conn.execute(
        "SELECT ccn, work_date FROM day_fact WHERE rowid % 50000 = 1 LIMIT 40"
    ).fetchall()
    if not samples and sample:
        samples = [sample]
    conn.close()

    ccn0, date0 = samples[0]
    # cold
    seb.invalidate_caches()
    t0 = time.perf_counter()
    cold = seb.lookup_day_evidence(app_root, ccn0, date0, "RN_HPRD")
    cold_ms = (time.perf_counter() - t0) * 1000
    # warm same key
    t1 = time.perf_counter()
    for _ in range(100):
        seb.lookup_day_evidence(app_root, ccn0, date0, "RN_HPRD")
    warm_ms = (time.perf_counter() - t1) * 1000 / 100
    # mixed warm lookups
    t2 = time.perf_counter()
    for ccn, wd in samples:
        for m in ("RN_HPRD", "CNA_HPRD", "Total_RN_HPRD"):
            seb.lookup_day_evidence(app_root, ccn, wd, m)
    mixed_ms = (time.perf_counter() - t2) * 1000 / max(1, len(samples) * 3)
    after_lookups = rss_mb()

    out = {
        "ok": cold is not None,
        "schema": manifest.get("schema"),
        "bundle_schema_version": manifest.get("bundle_schema_version"),
        "quarters": manifest.get("quarters_in_bundle"),
        "manifest_row_count": manifest.get("row_count"),
        "sqlite_row_count": row_count,
        "facility_count": manifest.get("facility_count"),
        "sqlite_bytes": os.path.getsize(db),
        "sqlite_mb": round(os.path.getsize(db) / 1e6, 2),
        "gzip_bytes": gz.stat().st_size if gz.is_file() else None,
        "gzip_mb": round(gz.stat().st_size / 1e6, 2) if gz.is_file() else None,
        "build_elapsed_s": manifest.get("build_elapsed_s"),
        "cold_lookup_ms": round(cold_ms, 3),
        "warm_lookup_ms": round(warm_ms, 3),
        "mixed_lookup_ms": round(mixed_ms, 3),
        "rss_baseline_mb": round(baseline, 1),
        "rss_after_open_mb": round(after_open, 1),
        "rss_after_lookups_mb": round(after_lookups, 1),
        "rss_delta_open_mb": round(after_open - baseline, 1),
        "rss_delta_lookups_mb": round(after_lookups - after_open, 1),
        "sample_hit": {"ccn": ccn0, "date": date0, "value": cold.get("value") if cold else None},
    }
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
