"""Tests for canonical SFF pipeline artifacts."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestSffPipelineArtifacts(unittest.TestCase):
  def test_canonical_dataset_exists_and_has_june_2026_date(self):
    path = ROOT / "data" / "derived" / "sff" / "sff_facilities.json"
    self.assertTrue(path.is_file(), msg=str(path))
    with path.open("r", encoding="utf-8") as handle:
      data = json.load(handle)
    doc = data.get("document_date") or {}
    self.assertEqual(doc.get("year"), 2026)
    self.assertEqual(doc.get("month"), 6)
    self.assertEqual(doc.get("month_name"), "June")

  def test_active_sff_and_candidates_are_distinguishable(self):
    path = ROOT / "data" / "derived" / "sff" / "sff_facilities.json"
    with path.open("r", encoding="utf-8") as handle:
      facilities = json.load(handle).get("facilities") or []
    categories = {f.get("category") for f in facilities}
    self.assertIn("SFF", categories)
    self.assertIn("Candidate", categories)

  def test_app_loads_canonical_sff_json(self):
    from app import get_sff_source_url, load_sff_facilities

    rows = load_sff_facilities() or []
    self.assertGreater(len(rows), 0)
    url = get_sff_source_url()
    self.assertIn("june-2026", url.lower())

  def test_known_sff_ccn_resolves(self):
    from app import load_sff_facilities

    rows = load_sff_facilities() or []
    match = next(
      (
        f
        for f in rows
        if str(f.get("provider_number") or "").strip().zfill(6) == "015463"
      ),
      None,
    )
    self.assertIsNotNone(match)
    self.assertEqual(match.get("category"), "SFF")
    self.assertEqual(match.get("state"), "AL")


if __name__ == "__main__":
  unittest.main()
