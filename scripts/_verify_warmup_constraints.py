#!/usr/bin/env python3
"""One-off constraint checks for POST /warmup/facility-indexes (not committed)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.pop("PBJ_WARMUP_SECRET", None)

for mod in list(sys.modules):
    if mod in ("app",) or mod.startswith("app."):
        del sys.modules[mod]

import app as app_mod

app_mod.pd = None
app_mod._STATE_CONTRACT_MEDIAN_CACHE = None
app_mod._STATE_PERCENTILE_HPRD_INDEX_CACHE = None
app_mod._FACILITY_LATEST_HPRD_BY_CCN_VAL = None
app_mod._FACILITY_LATEST_HPRD_BY_CCN_KEY = None

client = app_mod.app.test_client()

# 4: no secret -> 403, no index build
r = client.post("/warmup/facility-indexes")
assert r.status_code == 403, r.status_code
assert app_mod._STATE_CONTRACT_MEDIAN_CACHE is None
assert app_mod._STATE_PERCENTILE_HPRD_INDEX_CACHE is None
print("OK: missing secret -> 403, caches untouched")

# 3: secret + header -> builds
os.environ["PBJ_WARMUP_SECRET"] = "test-secret"
for mod in list(sys.modules):
    if mod in ("app",) or mod.startswith("app."):
        del sys.modules[mod]
import app as app_mod2

client2 = app_mod2.app.test_client()
r2 = client2.post(
    "/warmup/facility-indexes",
    headers={"X-PBJ-Warmup-Key": "test-secret"},
)
assert r2.status_code == 200, (r2.status_code, r2.get_data())
body = r2.get_json()
assert body.get("contract_states", 0) > 0
assert body.get("percentile_states", 0) > 0
assert app_mod2._STATE_CONTRACT_MEDIAN_CACHE is not None
assert app_mod2._STATE_PERCENTILE_HPRD_INDEX_CACHE is not None
# 5: must not build national latest-HPRD map
assert app_mod2._FACILITY_LATEST_HPRD_BY_CCN_VAL is None
print("OK: authorized warmup builds contract+percentile only")
print("warmup_body:", body)

# wrong key -> 403
r3 = client2.post(
    "/warmup/facility-indexes",
    headers={"X-PBJ-Warmup-Key": "wrong"},
)
assert r3.status_code == 403
print("OK: wrong key -> 403")

print("All warmup constraint checks passed.")
