"""Smoke /agents, /llms.txt, /healthz, JSON twins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import app as app_mod  # noqa: E402


def main() -> int:
    client = app_mod.app.test_client()
    checks = []
    for path, needle in (
        ("/healthz", None),
        ("/agents", "https://www.pbj320.com/mcp"),
        ("/llms.txt", "get_staffing_evidence"),
    ):
        resp = client.get(path)
        ok = resp.status_code == 200 and (needle is None or needle in resp.get_data(as_text=True))
        checks.append((path, resp.status_code, ok))
    resp = client.get("/api/public/provider/366395.json")
    checks.append(("/api/public/provider/366395.json", resp.status_code, resp.status_code == 200))
    if resp.status_code == 200:
        data = resp.get_json()
        checks.append(("provider_json_ccn", 200, data.get("facility", {}).get("ccn") == "366395"))
    print(json.dumps({"checks": checks, "ok": all(c[2] for c in checks)}, indent=2))
    return 0 if all(c[2] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
