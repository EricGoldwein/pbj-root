#!/usr/bin/env python3
"""Reorder ownership chart JSON in insights-ny-minimum-staffing.html."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"

ORDER = [
    "all_ny",
    "ny_for_profit",
    "ny_non_profit",
    "ny_government",
    "nyc",
    "nyc_for_profit",
    "nyc_non_profit",
    "nyc_government",
]

TIERS = [
    "primary",
    "state",
    "state",
    "state",
    "metro",
    "metro-child",
    "metro-child",
    "metro-child",
]


def extract_array(marker: str, text: str) -> list:
    start = text.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : j + 1])
    raise ValueError(f"unterminated JSON after {marker!r}")


def replace_array(marker: str, data: list, text: str) -> str:
    start = text.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                new_blob = json.dumps(data, separators=(",", ": "), ensure_ascii=False)
                return text[:start] + new_blob + text[j + 1 :]
    raise ValueError(f"unterminated JSON after {marker!r}")


def main() -> None:
    text = HTML.read_text(encoding="utf-8")
    charts = extract_array("window.PBJ_REPORT_CHARTS = ", text)
    own = next(c for c in charts if c["id"] == "ownershipChart")
    by_curve = {s["all_curve"]: s for s in own["slices"]}
    own["slices"] = [by_curve[k] for k in ORDER]
    own["labels"] = [s["label"] for s in own["slices"]]
    own["slice_tiers"] = TIERS
    own["datasets"][0]["values"] = [s["all_pct"] for s in own["slices"]]
    own["datasets"][1]["values"] = [
        s.get("wknd_pct", s.get("sat_pct")) for s in own["slices"]
    ]
    text = replace_array("window.PBJ_REPORT_CHARTS = ", charts, text)

    ownership = extract_array("window.PBJ_REPORT_OWNERSHIP = ", text)
    by_curve_o = {row["all_curve"]: row for row in ownership}
    text = replace_array(
        "window.PBJ_REPORT_OWNERSHIP = ",
        [by_curve_o[k] for k in ORDER],
        text,
    )

    HTML.write_text(text, encoding="utf-8")
    print("Reordered ownership chart + PBJ_REPORT_OWNERSHIP")


if __name__ == "__main__":
    main()
