#!/usr/bin/env python3
"""Publish canonical derived SFF artifacts to pbj-wrapped/public for deploy."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sff_paths import (  # noqa: E402
    SFF_CURRENT_RELEASE_FILE,
    SFF_FACILITIES_JSON,
    SFF_PUBLIC_CANDIDATE_MONTHS_JSON,
    SFF_PUBLIC_DIR,
    SFF_PUBLIC_JSON,
    SFF_TABLES_DIR,
    find_latest_raw_pdf,
)

SFF_DIST_DIR = REPO_ROOT / "pbj-wrapped" / "dist"

CSV_PUBLISH_NAMES = [
    "sff_table_a.csv",
    "sff_table_b.csv",
    "sff_table_c.csv",
    "sff_table_d.csv",
]


def _legacy_candidate_months_json(dataset: dict) -> dict:
    """Backward-compatible shape still served at /sff/sff-candidate-months.json."""
    facilities = dataset.get("facilities") or []
    by_category = {
        "SFF": "table_a_current_sff",
        "Graduate": "table_b_graduated",
        "Terminated": "table_c_no_longer_participating",
        "Candidate": "table_d_candidates",
    }
    payload = {
        "document_date": dataset.get("document_date") or {},
        "summary": dataset.get("summary") or {},
    }
    for category, key in by_category.items():
        payload[key] = [f for f in facilities if f.get("category") == category]
    return payload


def publish() -> int:
    if not SFF_FACILITIES_JSON.is_file():
        print(f"Error: missing canonical dataset {SFF_FACILITIES_JSON}")
        return 1

    source_pdf = find_latest_raw_pdf()
    if source_pdf is None:
        print("Error: no raw SFF PDF found to publish")
        return 1

    SFF_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    SFF_DIST_DIR.mkdir(parents=True, exist_ok=True)

    with SFF_FACILITIES_JSON.open("r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    shutil.copy2(SFF_FACILITIES_JSON, SFF_PUBLIC_JSON)
    shutil.copy2(SFF_FACILITIES_JSON, SFF_DIST_DIR / SFF_PUBLIC_JSON.name)
    legacy = _legacy_candidate_months_json(dataset)
    with SFF_PUBLIC_CANDIDATE_MONTHS_JSON.open("w", encoding="utf-8") as handle:
        json.dump(legacy, handle, indent=2, ensure_ascii=False)
    shutil.copy2(SFF_PUBLIC_CANDIDATE_MONTHS_JSON, SFF_DIST_DIR / SFF_PUBLIC_CANDIDATE_MONTHS_JSON.name)

    for name in CSV_PUBLISH_NAMES:
        src = SFF_TABLES_DIR / name
        if src.is_file():
            shutil.copy2(src, SFF_PUBLIC_DIR / name)
            shutil.copy2(src, SFF_DIST_DIR / name)

    published_pdf = SFF_PUBLIC_DIR / source_pdf.name
    shutil.copy2(source_pdf, published_pdf)

    release_meta = {
        "source_release": dataset.get("document_date", {}).get("source_release"),
        "source_filename": source_pdf.name,
        "published_pdf": source_pdf.name,
        "derived_json": str(SFF_FACILITIES_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "public_json": str(SFF_PUBLIC_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    SFF_CURRENT_RELEASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SFF_CURRENT_RELEASE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(release_meta, handle, indent=2)
        handle.write("\n")

    print(f"Published {SFF_PUBLIC_JSON}")
    print(f"Published {SFF_DIST_DIR / SFF_PUBLIC_JSON.name}")
    print(f"Published {SFF_PUBLIC_CANDIDATE_MONTHS_JSON}")
    print(f"Published {SFF_DIST_DIR / SFF_PUBLIC_CANDIDATE_MONTHS_JSON.name}")
    print(f"Published PDF {published_pdf}")
    print(f"Updated {SFF_CURRENT_RELEASE_FILE}")
    return 0


def main() -> int:
    return publish()


if __name__ == "__main__":
    raise SystemExit(main())
