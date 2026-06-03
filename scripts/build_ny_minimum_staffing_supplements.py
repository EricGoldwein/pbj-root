#!/usr/bin/env python3
"""
Rebuild PBJ_REPORT_NY_STATUTE and PBJ_REPORT_CALENDAR_EXTRA for the NY minimum staffing report.

Requires NY PBJ daily facility-day pipeline output (same build that produces
PBJ_REPORT_INTERACTIVE). Set PBJ_NY_REPORT_BUILD_DIR to that artifact directory,
or pass --build-dir.

Verified from: insights-ny-minimum-staffing.html window.PBJ_REPORT_* embeds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def patch_window_var(html: str, var_name: str, payload: dict) -> str:
    marker = f"window.{var_name} = "
    start = html.index(marker) + len(marker)
    blob = json.dumps(payload, separators=(",", ": "), ensure_ascii=False)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="Directory with ny_statute.json and calendar_extra.json from PBJ daily build",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payloads only")
    args = parser.parse_args()
    build_dir = args.build_dir or Path(os.environ.get("PBJ_NY_REPORT_BUILD_DIR", ""))

    statute_path = build_dir / "ny_statute.json" if build_dir else None
    calendar_path = build_dir / "calendar_extra.json" if build_dir else None

    if not build_dir or not statute_path or not statute_path.is_file():
        print(
            "No supplement build artifacts found.\n"
            "  1. Run your NY PBJ daily facility-day pipeline (same job that writes PBJ_REPORT_INTERACTIVE).\n"
            "  2. Export ny_statute.json and calendar_extra.json into one directory.\n"
            "  3. Re-run:  python scripts/build_ny_minimum_staffing_supplements.py --build-dir PATH\n"
            "     or set PBJ_NY_REPORT_BUILD_DIR=PATH\n"
            "  4. Run:  python scripts/audit_ny_minimum_staffing_math.py\n",
            file=sys.stderr,
        )
        return 2

    statute = load_json(statute_path)
    calendar = load_json(calendar_path)

    if args.dry_run:
        print(json.dumps({"statute": statute, "calendar": calendar}, indent=2))
        return 0

    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 1

    html = HTML.read_text(encoding="utf-8")
    html = patch_window_var(html, "PBJ_REPORT_NY_STATUTE", statute)
    html = patch_window_var(html, "PBJ_REPORT_CALENDAR_EXTRA", calendar)
    HTML.write_text(html, encoding="utf-8")
    print(f"Patched {HTML.name} with supplements from {build_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
