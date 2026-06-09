#!/usr/bin/env python3
"""Sync provider persistence metrics into CSV package + report embed from facility summary."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs"
FACILITY_CSV = CSV_DIR / "facility_summary.csv"
HTML = ROOT / "insights-ny-minimum-staffing.html"

sys.path.insert(0, str(ROOT))
from scripts.build_ny_verification_workbook import (  # noqa: E402
    _build_provider_day_bands_summary,
    _build_provider_persistence_summary,
    _enrich_facility_persistence_flags,
    _provider_persistence_counts,
)


def patch_window_var(html: str, var_name: str, payload: object) -> str:
    marker = f"window.{var_name} = "
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
    raise ValueError(f"unterminated JSON for {var_name}")


def main() -> int:
    if not FACILITY_CSV.is_file():
        print(f"Missing {FACILITY_CSV}", file=sys.stderr)
        return 1

    fac = pd.read_csv(FACILITY_CSV)
    fac = _enrich_facility_persistence_flags(fac)
    persistence = _provider_persistence_counts(fac)

    fac.to_csv(FACILITY_CSV, index=False)
    _build_provider_persistence_summary(persistence).to_csv(
        CSV_DIR / "provider_persistence_summary.csv", index=False
    )
    _build_provider_day_bands_summary(persistence).to_csv(
        CSV_DIR / "provider_day_bands_summary.csv", index=False
    )

    t50 = persistence["thresholds"]["at_least_50pct"]
    t90 = persistence["thresholds"]["at_least_90pct"]
    t100 = persistence["thresholds"]["all_analyzed_days"]
    prose = (
        f'<p id="provider-days-below-lead">Among <strong>596</strong> New York nursing homes, '
        f"<strong>{t50['facilities']}</strong> (<strong>{t50['pct_of_facilities']}%</strong>) "
        f"reported staffing below <strong>3.50</strong> HPRD on at least half of their analyzed "
        f"2025 facility-days. At the high end, <strong>{t90['facilities']}</strong> homes were below "
        f"the standard on at least <strong>90%</strong> of days, including "
        f"<strong>{t100['facilities']}</strong> homes below the standard on every reported day.</p>"
    )

    html = HTML.read_text(encoding="utf-8")
    html = re.sub(
        r'<p id="provider-days-below-lead">.*?</p>',
        prose,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if "window.PBJ_REPORT_PROVIDER_PERSISTENCE = " in html:
        html = patch_window_var(html, "PBJ_REPORT_PROVIDER_PERSISTENCE", persistence)
    else:
        insert_after = "window.PBJ_REPORT_STANDARD_PRIMARY = "
        idx = html.index(insert_after)
        end = html.index(";", idx) + 1
        blob = "window.PBJ_REPORT_PROVIDER_PERSISTENCE = " + json.dumps(
            persistence, separators=(",", ":")
        ) + ";"
        html = html[:end] + "\n" + blob + html[end:]

    HTML.write_text(html, encoding="utf-8")
    print("Synced provider persistence:")
    print(json.dumps(persistence["thresholds"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
