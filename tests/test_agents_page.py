"""Focused checks for the public /agents connection page."""

from __future__ import annotations

import unittest

import app as app_mod
from mcp.tools_registry import TOOLS


class AgentsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = app_mod.app.test_client()
        cls.html = cls.client.get("/agents").get_data(as_text=True)

    def test_agents_returns_200(self):
        resp = self.client.get("/agents")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.content_type)

    def test_canonical_and_title(self):
        self.assertIn("<title>PBJ320 for agents", self.html)
        self.assertIn('rel="canonical" href="https://www.pbj320.com/agents"', self.html)
        self.assertIn('property="og:title"', self.html)

    def test_mcp_endpoint_and_no_sse(self):
        self.assertIn("https://www.pbj320.com/mcp", self.html)
        self.assertNotIn("/mcp/sse", self.html)
        self.assertIn("Streamable HTTP", self.html)

    def test_six_tool_names(self):
        self.assertEqual(len(TOOLS), 6)
        for name in TOOLS:
            self.assertIn(name, self.html)

    def test_discovery_and_methodology_links(self):
        self.assertIn('href="/llms.txt"', self.html)
        self.assertIn("/data-sources", self.html)
        self.assertIn("/data-sources#methodology", self.html)

    def test_copyable_blocks(self):
        self.assertIn("<pre>", self.html)
        self.assertIn("<code", self.html)
        self.assertIn('class="copy-btn"', self.html)
        self.assertIn("claude mcp add --transport http pbj320 https://www.pbj320.com/mcp", self.html)
        self.assertEqual(self.html.count('"mcpServers"'), 1)
        self.assertIn("Seagate in Brooklyn", self.html)
        self.assertNotIn("366395", self.html)
        self.assertNotIn("CCN 335513", self.html)
        self.assertNotIn("Seagate Rehabilitation and Nursing Center", self.html)
        self.assertNotIn("link me to its PBJ320 page", self.html)
        self.assertNotIn("What you can ask", self.html)
        self.assertNotIn("Copy prompt", self.html)
        self.assertNotIn("nursing-home", self.html)
        self.assertNotIn("Connect a compatible MCP client", self.html)
        self.assertIn("insights-theme.css", self.html)
        self.assertIn("pbj-insights-article", self.html)

    def test_indexable(self):
        from site_public_config import ROBOTS_TXT, SITEMAP_TRUST_PAGES

        self.assertNotIn("noindex", self.html.lower())
        resp = self.client.get("/agents")
        self.assertNotIn("noindex", (resp.headers.get("X-Robots-Tag") or "").lower())
        self.assertIn(("/agents", "0.7", "monthly"), SITEMAP_TRUST_PAGES)
        self.assertIn("Allow: /", ROBOTS_TXT)
        self.assertNotIn("Disallow: /agents", ROBOTS_TXT)

    def test_json_endpoint_grammar(self):
        self.assertIn("/api/public/provider/{ccn}.json", self.html)
        self.assertIn("/api/public/owners/{pac}.json", self.html)

    def test_chatgpt_not_advertised_without_sse(self):
        self.assertNotIn("ChatGPT", self.html)
        self.assertNotIn("/mcp/sse", self.html)


if __name__ == "__main__":
    unittest.main()
