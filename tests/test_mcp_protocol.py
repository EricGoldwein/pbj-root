"""MCP protocol and tool smoke tests."""

from __future__ import annotations

import json
import unittest

from mcp.http_handler import dispatch_message
from mcp.tools_registry import TOOLS, call_tool, list_tools


class McpProtocolTests(unittest.TestCase):
    def test_tools_list_via_jsonrpc(self):
        resp = dispatch_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        self.assertEqual(resp["id"], 1)
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(names, set(TOOLS.keys()))

    def test_unknown_tool_call(self):
        payload = call_tool("no_such_tool", {})
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "unknown_tool")

    def test_initialize(self):
        resp = dispatch_message({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})
        self.assertIn("protocolVersion", resp["result"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "PBJ320")

    def test_list_tools_count(self):
        self.assertEqual(len(list_tools()), 6)


class McpSafetyTests(unittest.TestCase):
    def test_invalid_ccn_rejected(self):
        payload = call_tool("get_facility", {"ccn": "12"})
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "invalid_ccn")

    def test_invalid_pac_rejected(self):
        payload = call_tool("get_owner_portfolio", {"pac": "123"})
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "invalid_pac")

    def test_excessive_limit_capped_in_search(self):
        from pbj_public_query.facility import search_facilities

        result = search_facilities(query="a", limit=999)
        self.assertLessEqual(result["limit"], 60)

    def test_sql_like_query_is_plain_text(self):
        payload = call_tool("search_facilities", {"query": "' OR 1=1 --", "limit": 5})
        self.assertIn("ok", payload)

    def test_evidence_rejects_date_range_extraction(self):
        payload = call_tool(
            "get_staffing_evidence",
            {"ccn": "366395", "date": "2026-01-15", "start_date": "2026-01-01"},
        )
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "extraction_not_allowed")

    def test_evidence_rejects_pagination(self):
        payload = call_tool(
            "get_staffing_evidence",
            {"ccn": "366395", "date": "2026-01-15", "limit": 100},
        )
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "extraction_not_allowed")

    def test_evidence_unavailable_period_no_silent_swap(self):
        payload = call_tool(
            "get_staffing_evidence",
            {"ccn": "366395", "date": "2026-01-15", "period": "CY2015Q1"},
        )
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "evidence_unavailable_for_period")

    def test_get_facility_has_citation(self):
        payload = call_tool("get_facility", {"ccn": "366395"})
        if not payload.get("ok"):
            self.skipTest("facility 366395 not in local indexes")
        cite = payload.get("citation") or {}
        self.assertEqual(cite.get("agency"), "Centers for Medicare & Medicaid Services (CMS)")
        self.assertTrue(cite.get("datasets"))
        self.assertTrue(payload.get("facility"))


if __name__ == "__main__":
    unittest.main()
