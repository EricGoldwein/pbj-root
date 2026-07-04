#!/usr/bin/env python3
"""Smoke: /insights/trends uses root-absolute asset URLs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app

c = app.test_client()
html = c.get("/insights/trends").data.decode("utf-8", errors="replace")
assert "/playground_distributions.json" in html
assert "fetch('national_quarterly_metrics.csv')" not in html
assert 'href="phoebe.png"' not in html

for path in (
    "/phoebe.png",
    "/pbj_favicon.png",
    "/playground_distributions.json",
    "/national_quarterly_metrics.csv",
    "/state_quarterly_metrics.csv",
    "/quarterly_medians.json",
):
    r = c.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}"

print("OK: insights/trends assets and data files resolve at site root")
