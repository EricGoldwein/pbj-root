"""Ensure public staffing day-evidence bundle is materialized for runtime.

Production consumes a pre-built approved artifact:
  git: data/evidence/staffing_day_evidence_manifest.json (pointer + sha256)
  GitHub Release: staffing_day_evidence_CY2026Q1.sqlite.gz (~68 MB)

This script downloads (if needed), verifies sha256, gunzips, and validates row count.
It never rebuilds national evidence from CMS CSVs.

Env:
  PBJ_SKIP_STAFFING_EVIDENCE_BUNDLE=1  — skip entirely
  PBJ_REQUIRE_STAFFING_EVIDENCE=1      — fail closed if missing/corrupt (Render)
  PBJ_STAFFING_EVIDENCE_DOWNLOAD_URL   — override release URL (smoke/emergency)
  PBJ_STAFFING_EVIDENCE_FORCE_DOWNLOAD — re-fetch gzip even if present
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import staffing_evidence_bundle as seb  # noqa: E402


def _log(msg: str) -> None:
    print(f"[ensure_staffing_evidence_bundle] {msg}", flush=True)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def main() -> int:
    require = _truthy("PBJ_REQUIRE_STAFFING_EVIDENCE")
    if _truthy("PBJ_SKIP_STAFFING_EVIDENCE_BUNDLE"):
        if require:
            _log("ERROR cannot skip when PBJ_REQUIRE_STAFFING_EVIDENCE=1")
            return 1
        _log("skipped (PBJ_SKIP_STAFFING_EVIDENCE_BUNDLE)")
        return 0

    app_root = str(REPO)
    manifest = seb.load_manifest(app_root, force=True)
    if not manifest:
        msg = "approved staffing evidence manifest missing or schema mismatch"
        if require:
            _log(f"ERROR {msg}")
            return 1
        _log(f"no manifest; skip optional artifact — {msg}")
        return 0

    dist = manifest.get("distribution") if isinstance(manifest.get("distribution"), dict) else {}
    if str(dist.get("method") or "") == "github_release":
        from scripts.download_staffing_evidence_bundle import download_gzip, verify_gzip

        gz = Path(seb.sqlite_gzip_path(app_root))
        if not verify_gzip(gz, manifest):
            rc = download_gzip(app_root)
            if rc != 0:
                _log("ERROR could not download verified staffing evidence gzip from GitHub Release")
                return 1 if require else 0
    elif not seb.bundle_available(app_root):
        msg = "no local gzip/sqlite and manifest is not github_release"
        if require:
            _log(f"ERROR {msg}")
            return 1
        _log(f"skip — {msg}")
        return 0

    db = seb.materialize_sqlite(app_root)
    if not db or not Path(db).is_file():
        _log("ERROR could not materialize staffing_day_evidence.sqlite")
        return 1

    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM day_fact").fetchone()[0]
        con.close()
    except Exception as exc:
        _log(f"ERROR corrupt sqlite: {exc}")
        return 1

    expected = int(manifest.get("row_count") or 0)
    if expected and n != expected:
        _log(f"ERROR row_count mismatch sqlite={n} manifest={expected}")
        return 1

    artifact = str(manifest.get("artifact_id") or manifest.get("quarters_in_bundle"))
    _log(
        f"OK artifact={artifact} rows={n} facilities~={manifest.get('facility_count')} "
        f"sha256={str(dist.get('sqlite_gz_sha256') or '')[:12]}…"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
