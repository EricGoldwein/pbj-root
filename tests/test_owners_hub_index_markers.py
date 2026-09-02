"""Regression markers for nationwide /owners hub (PR #5 revert detector)."""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from ownership.state_owner_index_html import render_owners_hub_index_body

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PY = REPO_ROOT / "app.py"


def _extract_function_source(path: Path, func_name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            lines = path.read_text(encoding="utf-8").splitlines()
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            return "\n".join(lines[start:end])
    return ""


class OwnersHubIndexMarkersTests(unittest.TestCase):
    def test_render_national_hub_markers(self) -> None:
        """Canonical renderer must emit nationwide hub markers (stable, not copy-specific)."""
        body, _layout = render_owners_hub_index_body(None, get_canonical_slug=lambda s: s)
        self.assertIn('data-owners-hub="national"', body)
        self.assertIn("owners-hub-search", body)
        self.assertIn("owners-state-panels", body)
        self.assertNotIn("owners-hub-state-cards", body)

    def test_app_owners_handler_wiring_contract(self) -> None:
        """app.py /owners handler must delegate to render_owners_hub_index_body (PR #5 guard)."""
        self.assertTrue(APP_PY.is_file(), "app.py missing")
        src = _extract_function_source(APP_PY, "_owners_cms_index_html")
        self.assertTrue(src, "_owners_cms_index_html not found in app.py")
        self.assertIn("render_owners_hub_index_body", src)
        self.assertNotIn("owners-hub-state-cards", src)
        self.assertNotIn(
            "Public ownership index — links to NY/CT/FL state browse pages",
            src,
        )

    def test_app_owners_handler_not_inline_legacy_cards(self) -> None:
        """Whole-file guard: legacy four-state card landing must not return from handler."""
        text = APP_PY.read_text(encoding="utf-8")
        match = re.search(
            r"def _owners_cms_index_html\(\):\s*(?:\"\"\".*?\"\"\"\s*)?(.*?"
            r"\n(?:def |@app\.route))",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate _owners_cms_index_html body")
        body = match.group(1)
        self.assertNotIn("owners-hub-state-cards", body)


if __name__ == "__main__":
    unittest.main()
