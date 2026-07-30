"""
Active SNF ownership release handoff — validate and stage policy-selected source.

Package assembly must consume only files under ``<repo>/ownership/`` after staging.
Inbound reads use declared handoff locations only (no glob, mtime, or filename ordering).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ownership.ownership_release_policy import (
    OwnershipReleasePolicyError,
    OwnershipReleaseEntry,
    active_release_date,
    load_policy,
    resolve_release_entry,
)

HANDOFF_DIR = Path("ownership") / "_handoff"
PROVENANCE_FILENAME = "staged_active_release.json"


def file_sha256(path: Path) -> str:
    """Return lowercase hex SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _handoff_config(policy: dict[str, Any]) -> dict[str, Any]:
    cfg = policy.get("active_release_handoff")
    if not isinstance(cfg, dict):
        raise OwnershipReleasePolicyError("Policy missing active_release_handoff object")
    return cfg


def _resolve_repo_relative_inbound(root: Path, repo_role: str, relative_path: str) -> Path:
    rel = Path(relative_path.replace("\\", "/"))
    if repo_role == "pbj_root_sibling":
        base = root.parent / "pbj-root"
    elif repo_role == "pbjapp_repo":
        base = root
    else:
        raise OwnershipReleasePolicyError(f"Unsupported handoff repo_role: {repo_role!r}")
    return base / rel


def resolve_handoff_inbound_path(
    root: Path,
    entry: OwnershipReleaseEntry,
    *,
    policy: dict[str, Any],
    explicit_source: Path | None = None,
) -> Path:
    """Resolve declared inbound source for the active release (handoff step only)."""
    if explicit_source is not None:
        src = explicit_source.resolve()
        if not src.is_file():
            raise OwnershipReleasePolicyError(f"Explicit handoff source missing: {src}")
        if src.name != entry.ownership_source_filename:
            raise OwnershipReleasePolicyError(
                f"Explicit handoff source {src.name} != policy {entry.ownership_source_filename}"
            )
        return src

    cfg = _handoff_config(policy)
    sources = cfg.get("inbound_sources")
    if not isinstance(sources, list) or not sources:
        raise OwnershipReleasePolicyError("active_release_handoff.inbound_sources is required")

    tried: list[str] = []
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("kind") or "").strip() != "repo_relative":
            continue
        repo_role = str(raw.get("repo_role") or "").strip()
        rel_path = str(raw.get("relative_path") or "").strip()
        if not repo_role or not rel_path:
            continue
        candidate = _resolve_repo_relative_inbound(root, repo_role, rel_path)
        tried.append(str(candidate))
        if candidate.is_file() and candidate.name == entry.ownership_source_filename:
            return candidate

    raise OwnershipReleasePolicyError(
        f"No declared handoff source found for active release {entry.release_date}: "
        f"{entry.ownership_source_filename}. Tried: {', '.join(tried)}"
    )


def validate_source_checksum(path: Path, expected_sha256: str) -> None:
    """Fail closed when checksum does not match policy."""
    expected = str(expected_sha256 or "").strip().lower()
    if not expected:
        raise OwnershipReleasePolicyError(
            f"Active release {path.name} requires ownership_source_sha256 in policy"
        )
    actual = file_sha256(path).lower()
    if actual != expected:
        raise OwnershipReleasePolicyError(
            f"Checksum mismatch for {path.name}: expected {expected}, got {actual}"
        )


def provenance_path(root: Path, policy: dict[str, Any] | None = None) -> Path:
    pol = policy or load_policy(root)
    cfg = _handoff_config(pol)
    rel = str(cfg.get("staged_provenance_relative_path") or "").strip()
    if not rel:
        rel = str(HANDOFF_DIR / PROVENANCE_FILENAME).replace("\\", "/")
    return root / Path(rel.replace("\\", "/"))


def load_staged_provenance(root: Path) -> dict[str, Any] | None:
    path = provenance_path(root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def stage_active_ownership_source(
    root: Path,
    *,
    policy: dict[str, Any] | None = None,
    handoff_source: Path | None = None,
    dry_run: bool = False,
    skip_if_staged_valid: bool = False,
) -> dict[str, Any]:
    """
    Validate and copy the active release ownership CSV into ``ownership/``.

    Returns provenance metadata; writes ``ownership/_handoff/staged_active_release.json``.
    """
    pol = policy or load_policy(root)
    release = active_release_date(pol)
    entry = resolve_release_entry(pol, release)
    staged_path = root / "ownership" / entry.ownership_source_filename

    if skip_if_staged_valid and staged_path.is_file() and entry.ownership_source_sha256:
        validate_source_checksum(staged_path, entry.ownership_source_sha256)
        existing = load_staged_provenance(root)
        if existing and existing.get("ownership_release_date") == release:
            return {**existing, "action": "skip_valid_staged"}

    inbound = resolve_handoff_inbound_path(
        root, entry, policy=pol, explicit_source=handoff_source
    )
    validate_source_checksum(inbound, entry.ownership_source_sha256)

    record: dict[str, Any] = {
        "ownership_release_date": release,
        "ownership_source_filename": entry.ownership_source_filename,
        "ownership_source_sha256": entry.ownership_source_sha256,
        "handoff_source_path": str(inbound.resolve()),
        "staged_path": str(staged_path.resolve()),
        "staged_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "action": "staged",
    }

    if dry_run:
        record["action"] = "dry_run"
        return record

    staged_path.parent.mkdir(parents=True, exist_ok=True)
    if inbound.resolve() != staged_path.resolve():
        shutil.copy2(inbound, staged_path)
    validate_source_checksum(staged_path, entry.ownership_source_sha256)

    prov_path = provenance_path(root, pol)
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    prov_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def ensure_active_ownership_source_staged(
    root: Path,
    *,
    policy: dict[str, Any] | None = None,
    handoff_source: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage active release source when missing or checksum-invalid; idempotent when valid."""
    pol = policy or load_policy(root)
    release = active_release_date(pol)
    entry = resolve_release_entry(pol, release)
    staged_path = root / "ownership" / entry.ownership_source_filename

    if staged_path.is_file() and entry.ownership_source_sha256:
        try:
            validate_source_checksum(staged_path, entry.ownership_source_sha256)
            existing = load_staged_provenance(root)
            if existing and existing.get("ownership_release_date") == release:
                return {**existing, "action": "already_staged"}
        except OwnershipReleasePolicyError:
            pass

    return stage_active_ownership_source(
        root,
        policy=pol,
        handoff_source=handoff_source,
        dry_run=dry_run,
        skip_if_staged_valid=False,
    )
