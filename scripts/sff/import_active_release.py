#!/usr/bin/env python3
"""Import the exact ACTIVE data-ops SFF release into the existing PBJ pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import calendar
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]


def _local(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file": raise RuntimeError("SFF ACTIVE artifact must be a local file URI")
    raw = unquote(parsed.path)
    if os.name == "nt" and raw.startswith("/") and len(raw) > 2 and raw[2] == ":": raw = raw[1:]
    return Path(raw)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def import_active(registry_path: Path, *, repo_root: Path = REPO_ROOT) -> dict:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    active = (payload.get("datasets") or {}).get("cms.sff_pdf_list")
    if not active or active.get("status") != "ACTIVE": raise RuntimeError("cms.sff_pdf_list has no ACTIVE release")
    release_id = str(active["active_release_id"])
    metadata = active.get("metadata") or {}
    pdf = _local(str(metadata.get("source_pdf_uri") or ""))
    if not pdf.is_file() or _hash(pdf) != metadata.get("source_pdf_hash"): raise RuntimeError("ACTIVE SFF PDF is missing or hash-mismatched")
    handoff = metadata.get("pbj_handoff") or []
    expected = {f"sff_table_{letter}.csv" for letter in "abcd"}
    if {item.get("role") for item in handoff} != expected: raise RuntimeError("ACTIVE SFF handoff is incomplete")
    raw_dir = repo_root / "data_sources" / "cms" / "sff" / "raw" / release_id
    table_dir = repo_root / "data" / "derived" / "sff" / "tables"
    raw_dir.mkdir(parents=True, exist_ok=True); table_dir.mkdir(parents=True, exist_ok=True)
    year, month = release_id.split("-", 1)
    pdf_name = f"sff-posting-with-candidate-list-{calendar.month_name[int(month)].lower()}-{year}.pdf"
    shutil.copy2(pdf, raw_dir / pdf_name)
    for item in handoff:
        source = _local(str(item.get("source_uri") or ""))
        if not source.is_file() or _hash(source) != item.get("hash"): raise RuntimeError(f"SFF handoff hash mismatch: {item.get('role')}")
        shutil.copy2(source, table_dir / str(item["role"]))
    (raw_dir / "manifest.json").write_text(json.dumps({"dataset_id": "cms.sff_pdf_list", "release_id": release_id, "original_filename": pdf_name, "sha256": _hash(pdf), "active_registry": str(registry_path)}, indent=2) + "\n", encoding="utf-8")
    return {"release_id": release_id, "pdf": pdf_name, "tables": sorted(expected)}


def main() -> int:
    configured = os.environ.get("PBJ_ACTIVE_RELEASE_REGISTRY", "").strip()
    if not configured: raise SystemExit("PBJ_ACTIVE_RELEASE_REGISTRY is required")
    result = import_active(Path(configured).expanduser().resolve())
    print(f"Imported ACTIVE SFF {result['release_id']} into the existing PBJ SFF build contract")
    return 0


if __name__ == "__main__": raise SystemExit(main())
