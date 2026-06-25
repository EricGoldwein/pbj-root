#!/usr/bin/env python3
"""Validate CMS SFF raw sources and derived artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sff_paths import (  # noqa: E402
    MONTH_TO_NUM,
    SFF_CURRENT_RELEASE_FILE,
    SFF_FACILITIES_JSON,
    SFF_RAW_ROOT,
    SFF_TABLES_DIR,
    extract_pdf_release_parts,
    find_latest_raw_pdf,
    sff_facilities_json_candidates,
)

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
REQUIRED_CATEGORIES = {"SFF", "Candidate", "Graduate", "Terminated"}
CCN_RE = re.compile(r"^\d{6}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_manifest(release_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = release_dir / "manifest.json"
    pdfs = list(release_dir.glob("sff-posting-with-candidate-list*.pdf"))
    if not pdfs:
        return errors
    pdf = pdfs[0]
    if not manifest_path.is_file():
        errors.append(f"Missing manifest.json in {release_dir}")
        return errors

    manifest = _load_json(manifest_path)
    expected_name = manifest.get("original_filename")
    if expected_name and expected_name != pdf.name:
        errors.append(f"{release_dir.name}: manifest original_filename mismatch ({expected_name} vs {pdf.name})")

    recorded_hash = (manifest.get("sha256") or "").lower()
    if recorded_hash:
        actual_hash = _sha256(pdf)
        if recorded_hash != actual_hash:
            errors.append(f"{release_dir.name}: sha256 mismatch for {pdf.name}")
    return errors


def _validate_tables() -> list[str]:
    errors: list[str] = []
    for name in ("sff_table_a.csv", "sff_table_d.csv"):
        path = SFF_TABLES_DIR / name
        if not path.is_file():
            errors.append(f"Missing derived table CSV: {path}")
    return errors


def _validate_dataset(path: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats: dict = {}

    if not path.is_file():
        return [f"Missing SFF dataset: {path}"], stats

    data = _load_json(path)
    facilities = data.get("facilities")
    if not isinstance(facilities, list):
        return [f"{path}: expected facilities list"], stats

    categories = Counter()
    states = Counter()
    dup_keys = Counter()
    invalid_ccn = 0
    invalid_state = 0

    for facility in facilities:
        if not isinstance(facility, dict):
            errors.append(f"{path}: non-dict facility entry")
            continue
        category = facility.get("category")
        categories[category] += 1
        ccn = str(facility.get("provider_number") or "").strip()
        if not CCN_RE.match(ccn):
            invalid_ccn += 1
        state = (facility.get("state") or "").strip().upper()
        if state:
            states[state] += 1
            if state not in US_STATES:
                invalid_state += 1
        key = (ccn, category, facility.get("source_release"))
        dup_keys[key] += 1

    missing_categories = REQUIRED_CATEGORIES - set(categories)
    if missing_categories:
        errors.append(f"{path}: missing categories {sorted(missing_categories)}")

    duplicates = sum(1 for count in dup_keys.values() if count > 1)
    if duplicates:
        errors.append(f"{path}: {duplicates} duplicate provider/category/source_release combinations")

    doc = data.get("document_date") or {}
    latest_pdf = find_latest_raw_pdf()
    if latest_pdf:
        parts = extract_pdf_release_parts(latest_pdf.name)
        if parts:
            year, month_num, _ = parts
            if doc.get("year") != year or doc.get("month") != month_num:
                errors.append(
                    f"{path}: document_date {doc.get('month_name')} {doc.get('year')} "
                    f"does not match latest raw PDF {latest_pdf.name}"
                )

    stats = {
        "total": len(facilities),
        "categories": dict(categories),
        "states": len(states),
        "invalid_ccn": invalid_ccn,
        "invalid_state": invalid_state,
        "duplicates": duplicates,
    }
    return errors, stats


def _validate_app_load_path() -> list[str]:
    errors: list[str] = []
    try:
        from app import load_sff_facilities  # noqa: WPS433

        rows = load_sff_facilities() or []
        if not rows:
            errors.append("app.load_sff_facilities() returned empty list")
    except Exception as exc:  # pragma: no cover - surfaced in CLI
        errors.append(f"app.load_sff_facilities() failed: {exc}")
    return errors


def main() -> int:
    errors: list[str] = []

    if not SFF_RAW_ROOT.is_dir():
        errors.append(f"Missing raw archive root: {SFF_RAW_ROOT}")
    else:
        for release_dir in sorted(SFF_RAW_ROOT.iterdir()):
            if release_dir.is_dir():
                errors.extend(_validate_manifest(release_dir))

    errors.extend(_validate_tables())
    dataset_errors, stats = _validate_dataset(SFF_FACILITIES_JSON)
    errors.extend(dataset_errors)
    errors.extend(_validate_app_load_path())

    if SFF_CURRENT_RELEASE_FILE.is_file():
        current = _load_json(SFF_CURRENT_RELEASE_FILE)
        latest_pdf = find_latest_raw_pdf()
        if latest_pdf and current.get("source_filename") != latest_pdf.name:
            errors.append("current_release.json does not point at latest raw PDF")

    print("SFF validation summary")
    print(f"  Dataset: {SFF_FACILITIES_JSON}")
    if stats:
        print(f"  Total records: {stats.get('total')}")
        print(f"  By category: {stats.get('categories')}")
        print(f"  States represented: {stats.get('states')}")
        print(f"  Invalid CCN rows: {stats.get('invalid_ccn')}")
        print(f"  Invalid state rows: {stats.get('invalid_state')}")
        print(f"  Duplicate keys: {stats.get('duplicates')}")

    if errors:
        print("\nFAILURES:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nOK: SFF pipeline artifacts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
