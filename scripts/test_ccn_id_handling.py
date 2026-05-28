#!/usr/bin/env python3
"""Lightweight CCN/provider-ID handling checks for numeric + alphanumeric IDs."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as pbj_app


def _assert(name: str, cond: bool) -> None:
    if not cond:
        raise AssertionError(name)
    print(f"[ok] {name}")


def main() -> int:
    # valid numeric CCN
    ccn_numeric = "075325"
    _assert("normalize numeric", pbj_app.normalize_ccn(ccn_numeric) == ccn_numeric)
    _assert(
        "provider info numeric exists",
        bool(pbj_app._provider_info_row_for_ccn(ccn_numeric)),
    )

    # valid alphanumeric CCN (present in current source files)
    ccn_alnum = "39A438"
    _assert("normalize alnum uppercase", pbj_app.normalize_ccn("39a438") == ccn_alnum)
    _assert(
        "provider info alnum exists",
        bool(pbj_app._provider_info_row_for_ccn(ccn_alnum)),
    )
    fac_df = pbj_app.load_facility_quarterly_for_provider(ccn_alnum)
    _assert("facility quarterly alnum exists", fac_df is not None and not fac_df.empty)

    # invalid alphanumeric ID
    _assert("invalid alnum normalize empty", pbj_app.normalize_ccn("39A43!") == "")

    # malformed provider IDs should 404 quickly without heavy scans
    client = pbj_app.app.test_client()
    for bad in ("39A43!", "TOO-LONG-123"):
        t0 = time.perf_counter()
        resp = client.get(f"/provider/{bad}")
        dt_ms = (time.perf_counter() - t0) * 1000
        _assert(f"{bad} -> 404", resp.status_code == 404)
        print(f"[timing] {bad} {dt_ms:.2f}ms")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[fail] {exc}")
        raise SystemExit(1)
