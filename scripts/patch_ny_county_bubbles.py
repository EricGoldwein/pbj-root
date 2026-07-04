#!/usr/bin/env python3
"""Embed county_bubbles into PBJ_REPORT_INTERACTIVE for the NY bubble map."""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "insights-ny-minimum-staffing.html"


def _load_window_var(html: str, name: str) -> dict:
    marker = f"window.{name} = "
    start = html.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start : j + 1])
    raise ValueError(f"unterminated JSON for {name}")


def _patch_window_var(html: str, name: str, payload: object) -> str:
    marker = f"window.{name} = "
    start = html.index(marker) + len(marker)
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return html[:start] + blob + html[j + 1 :]
    raise ValueError(f"unterminated JSON for {name}")


def _ny_centroids() -> dict[str, tuple[float, float]]:
    url = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"
    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8-sig")
    out: dict[str, tuple[float, float]] = {}
    for row in csv.DictReader(io.StringIO(raw)):
        if row["STATEFP"] != "36":
            continue
        fips = row["STATEFP"] + row["COUNTYFP"]
        out[fips] = (float(row["LONGITUDE"].lstrip("+")), float(row["LATITUDE"].lstrip("+")))
    return out


def build_county_bubbles(facilities: dict) -> list[dict]:
    centroids = _ny_centroids()
    by_fips: dict[str, dict] = defaultdict(lambda: {"name": "", "fd": 0, "nyc": False})
    for fac in facilities.get("facilities", []):
        fips = str(fac.get("county_fips", ""))
        if not fips:
            continue
        by_fips[fips]["name"] = fac.get("county") or by_fips[fips]["name"]
        by_fips[fips]["fd"] += int(fac.get("facility_days") or 0)
        by_fips[fips]["nyc"] = bool(fac.get("is_nyc"))
    bubbles: list[dict] = []
    for fips in sorted(by_fips):
        lon, lat = centroids[fips]
        row = by_fips[fips]
        bubbles.append(
            {
                "fips": fips,
                "name": row["name"],
                "lon": lon,
                "lat": lat,
                "facility_days": row["fd"],
                "is_nyc": row["nyc"],
            }
        )
    return bubbles


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    facilities = _load_window_var(html, "PBJ_REPORT_FACILITIES")
    interactive = _load_window_var(html, "PBJ_REPORT_INTERACTIVE")
    interactive["county_bubbles"] = build_county_bubbles(facilities)
    html = _patch_window_var(html, "PBJ_REPORT_INTERACTIVE", interactive)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"patched {len(interactive['county_bubbles'])} county_bubbles into {HTML_PATH.name}")


if __name__ == "__main__":
    main()
