#!/usr/bin/env python3
"""Ingest a new CMS SFF posting PDF into the versioned raw archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sff_paths import SFF_RAW_ROOT, release_dir_for_pdf  # noqa: E402

CMS_SFF_POSTING_TITLE = "Special Focus Facility (SFF) Posting with Candidate List"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest(pdf_path: Path, *, notes: str = "", source_url: str | None = None) -> Path:
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    release_dir = SFF_RAW_ROOT / release_dir_for_pdf(pdf_path.name)
    release_dir.mkdir(parents=True, exist_ok=True)
    dest_pdf = release_dir / pdf_path.name
    if dest_pdf.resolve() != pdf_path.resolve():
        shutil.copy2(pdf_path, dest_pdf)

    manifest = {
        "cms_source_title": CMS_SFF_POSTING_TITLE,
        "original_filename": pdf_path.name,
        "publication_month": release_dir.name,
        "ingested_at": date.today().isoformat(),
        "sha256": _sha256(dest_pdf),
        "source_url": source_url,
        "notes": notes or "Active SFFs (Table A), graduates (B), terminated (C), and candidates (D).",
    }
    manifest_path = release_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")

    return dest_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a CMS SFF posting PDF into data_sources/cms/sff/raw/")
    parser.add_argument("pdf", type=Path, help="Path to sff-posting-with-candidate-list-<month>-<year>.pdf")
    parser.add_argument("--notes", default="", help="Optional ingestion notes")
    parser.add_argument("--source-url", default=None, help="CMS download URL if known")
    args = parser.parse_args()

    try:
        dest = ingest(args.pdf, notes=args.notes, source_url=args.source_url)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Ingested {dest}")
    print(f"Manifest: {dest.parent / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
