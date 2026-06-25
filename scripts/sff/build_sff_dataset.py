#!/usr/bin/env python3
"""Build canonical SFF JSON/CSV from extracted table CSVs."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sff_paths import (  # noqa: E402
    NUM_TO_MONTH_NAME,
    SFF_FACILITIES_CSV,
    SFF_FACILITIES_JSON,
    SFF_TABLES_DIR,
    extract_pdf_release_parts,
    find_latest_raw_pdf,
)

CSV_FILES = {
    "sff_table_a.csv": "SFF",
    "sff_table_b.csv": "Graduate",
    "sff_table_c.csv": "Terminated",
    "sff_table_d.csv": "Candidate",
}

CSV_COLUMNS = [
    "provider_number",
    "facility_name",
    "address",
    "city",
    "state",
    "zip",
    "phone_number",
    "category",
    "months_as_sff",
    "most_recent_inspection",
    "met_survey_criteria",
    "date_of_graduation",
    "date_of_termination",
    "source_release",
    "source_filename",
]


def _normalize_provider_number(value: str) -> str:
    digits = "".join(ch for ch in (value or "").strip() if ch.isdigit())
    if not digits:
        return ""
    return digits.zfill(6)[-6:]


def _document_date_from_pdf(pdf_path: Path) -> dict[str, Any]:
    parts = extract_pdf_release_parts(pdf_path.name)
    if not parts:
        return {"month": None, "year": None, "month_name": "Unknown", "label": pdf_path.stem}
    year, month_num, month_name = parts
    return {
        "month": month_num,
        "year": year,
        "month_name": month_name,
        "label": pdf_path.stem,
        "source_filename": pdf_path.name,
        "source_release": f"{year:04d}-{month_num:02d}",
    }


def parse_csv_file(csv_path: Path, category: str, source_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a table CSV into normalized facility records."""
    facilities: list[dict[str, Any]] = []
    if not csv_path.is_file():
        print(f"Warning: {csv_path} not found")
        return facilities

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            provider_number = _normalize_provider_number(row.get("Provider Number", ""))
            if not provider_number:
                continue

            facility: dict[str, Any] = {
                "provider_number": provider_number,
                "facility_name": (row.get("Facility Name") or "").strip() or None,
                "address": (row.get("Address") or "").strip() or None,
                "city": (row.get("City") or "").strip() or None,
                "state": ((row.get("State") or "").strip() or None),
                "zip": (row.get("Zip") or row.get("ZIP") or "").strip() or None,
                "phone_number": (row.get("Phone Number") or "").strip() or None,
                "category": category,
                "months_as_sff": None,
                "most_recent_inspection": None,
                "met_survey_criteria": None,
                "date_of_graduation": None,
                "date_of_termination": None,
                "source_release": source_meta.get("source_release"),
                "source_filename": source_meta.get("source_filename"),
            }

            if category == "SFF":
                facility["most_recent_inspection"] = (row.get("Most Recent Inspection") or "").strip() or None
                facility["met_survey_criteria"] = (row.get("Met Survey Criteria") or "").strip() or None
                months_str = (row.get("Months as an SFF") or "").strip()
            elif category == "Graduate":
                facility["date_of_graduation"] = (row.get("Date of Graduation") or "").strip() or None
                months_str = (row.get("Months as an SFF") or "").strip()
            elif category == "Terminated":
                facility["date_of_termination"] = (row.get("Date of Termination") or "").strip() or None
                months_str = (row.get("Months as an SFF") or "").strip()
            else:
                months_str = (row.get("Months as an SFF Candidate") or "").strip()

            if months_str:
                try:
                    months = int(months_str)
                    if 0 <= months <= 200:
                        facility["months_as_sff"] = months
                except ValueError:
                    pass

            facilities.append(facility)

    return facilities


def build_dataset(tables_dir: Path, source_pdf: Path) -> dict[str, Any]:
    """Build combined SFF dataset dict from extracted CSV tables."""
    source_meta = _document_date_from_pdf(source_pdf)
    all_facilities: list[dict[str, Any]] = []
    counts = {category: 0 for category in CSV_FILES.values()}

    for csv_name, category in CSV_FILES.items():
        facilities = parse_csv_file(tables_dir / csv_name, category, source_meta)
        all_facilities.extend(facilities)
        counts[category] = len(facilities)
        print(f"Loaded {csv_name}: {len(facilities)} facilities ({category})")

    return {
        "document_date": {
            "month": source_meta["month"],
            "year": source_meta["year"],
            "month_name": source_meta["month_name"],
            "label": source_meta["label"],
            "source_filename": source_meta["source_filename"],
            "source_release": source_meta["source_release"],
        },
        "facilities": all_facilities,
        "summary": {
            "current_sff_count": counts["SFF"],
            "graduated_count": counts["Graduate"],
            "no_longer_participating_count": counts["Terminated"],
            "candidates_count": counts["Candidate"],
            "total_count": len(all_facilities),
        },
    }


def write_csv(dataset: dict[str, Any], csv_path: Path) -> None:
    """Write flat CSV mirror of facility records."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for facility in dataset.get("facilities") or []:
            writer.writerow(facility)


def write_json(dataset: dict[str, Any], json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2, ensure_ascii=False)


def main() -> int:
    tables_dir = SFF_TABLES_DIR
    source_pdf = find_latest_raw_pdf()
    if source_pdf is None:
        print("Error: no raw SFF PDF found under data_sources/cms/sff/raw/")
        return 1

    dataset = build_dataset(tables_dir, source_pdf)
    write_json(dataset, SFF_FACILITIES_JSON)
    write_csv(dataset, SFF_FACILITIES_CSV)

    summary = dataset["summary"]
    print(f"\nCreated {SFF_FACILITIES_JSON}")
    print(f"Created {SFF_FACILITIES_CSV}")
    print(f"   Source: {source_pdf.name}")
    print(f"   Total facilities: {summary['total_count']}")
    print(
        "   SFF: {sff}, Graduate: {grad}, Terminated: {term}, Candidate: {cand}".format(
            sff=summary["current_sff_count"],
            grad=summary["graduated_count"],
            term=summary["no_longer_participating_count"],
            cand=summary["candidates_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
