"""Capture abbreviated MCP tool responses for production-readiness sign-off."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mcp.tools_registry import call_tool  # noqa: E402


def _abbrev(payload: dict) -> dict:
    out = {k: payload[k] for k in ("ok", "ccn", "work_date", "metric", "canonical_url") if k in payload}
    if payload.get("facility"):
        out["facility"] = {
            "ccn": payload["facility"].get("ccn"),
            "name": payload["facility"].get("name"),
        }
        out["staffing"] = payload.get("staffing")
    if payload.get("citation"):
        out["citation"] = payload["citation"]
    if payload.get("analysis"):
        out["analysis"] = payload["analysis"]
    if payload.get("evidence"):
        out["evidence"] = payload["evidence"]
    if payload.get("audit"):
        aud = payload["audit"]
        out["audit"] = {
            "provenance_precision": aud.get("provenance_precision"),
            "source_record_id": aud.get("source_record_id"),
            "has_numerator_locator": bool(aud.get("numerator")),
        }
    return out


def main() -> int:
    ccn = "366395"
    db = REPO / "data" / "evidence" / "staffing_day_evidence.sqlite"
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT work_date FROM day_fact WHERE ccn=? ORDER BY work_date LIMIT 1", (ccn,)
    ).fetchone()
    con.close()
    date = row[0] if row else "2026-01-01"

    samples = {
        "get_facility": call_tool("get_facility", {"ccn": ccn}),
        "get_staffing_evidence": call_tool(
            "get_staffing_evidence", {"ccn": ccn, "date": date, "metric": "RN_HPRD"}
        ),
    }
    print(json.dumps({k: _abbrev(v) for k, v in samples.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
