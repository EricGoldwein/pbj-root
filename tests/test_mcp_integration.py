"""Integration tests for MCP + canonical queries (requires local data artifacts)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class McpIntegrationTests(unittest.TestCase):
    TEST_CCN = "366395"
    TEST_PAC = "0143110361"
    TEST_EVIDENCE_DATE = ""  # filled from day_fact in setUpClass

    @classmethod
    def setUpClass(cls) -> None:
        if not (REPO / "search_index.json").is_file():
            raise unittest.SkipTest("search_index.json missing")
        db = REPO / "data" / "evidence" / "staffing_day_evidence.sqlite"
        if not db.is_file():
            raise unittest.SkipTest("staffing evidence sqlite missing")
        import sqlite3

        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        # Prefer 366395 if present; else any row
        row = conn.execute(
            "SELECT ccn, work_date FROM day_fact WHERE ccn = ? LIMIT 1", (cls.TEST_CCN,)
        ).fetchone()
        if not row:
            row = conn.execute("SELECT ccn, work_date FROM day_fact LIMIT 1").fetchone()
        conn.close()
        if not row:
            raise unittest.SkipTest("day_fact empty")
        cls.TEST_CCN = row[0]
        cls.TEST_EVIDENCE_DATE = row[1]

    def test_get_facility_366395(self):
        from mcp.tools_registry import call_tool

        payload = call_tool("get_facility", {"ccn": self.TEST_CCN})
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload["facility"]["ccn"], self.TEST_CCN)
        canon = str(payload.get("canonical_url", ""))
        self.assertTrue("/provider/" in canon)
        self.assertIn("quarter", payload.get("period", {}))
        self.assertIn("agency", payload.get("citation", {}))

    def test_get_staffing_evidence(self):
        from mcp.tools_registry import call_tool

        payload = call_tool(
            "get_staffing_evidence",
            {"ccn": self.TEST_CCN, "date": self.TEST_EVIDENCE_DATE, "metric": "RN_HPRD"},
        )
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload["evidence"]["ccn"], self.TEST_CCN)
        self.assertIn("value", payload["evidence"])
        self.assertIn("citation", payload)
        self.assertIn("agency", payload["citation"])
        self.assertIn("numerator", payload.get("audit", {}))

    def test_owner_portfolio_or_skip(self):
        from mcp.tools_registry import call_tool

        payload = call_tool("get_owner_portfolio", {"pac": self.TEST_PAC})
        if not payload.get("ok"):
            self.skipTest(f"owner {self.TEST_PAC} not in local ownership index")
        self.assertEqual(payload["owner"]["associate_id"], self.TEST_PAC)
        self.assertIn("ownership_release", payload)

    def test_flask_mcp_tools_list(self):
        import app as app_mod

        client = app_mod.app.test_client()
        resp = client.post(
            "/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        names = {t["name"] for t in data["result"]["tools"]}
        self.assertIn("get_facility", names)

    def test_healthz_still_ok(self):
        import app as app_mod

        client = app_mod.app.test_client()
        resp = client.get("/healthz")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
