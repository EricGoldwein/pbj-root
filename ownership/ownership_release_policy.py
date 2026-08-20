"""
Explicit CMS SNF ownership release policy loader and resolver.

No mtime, glob-order, filename-sort, or "latest available" selection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ownership.ownership_release_parse import parse_snf_owners_release_date

POLICY_FILENAME = "ownership_release_policy.json"
BRIDGE_SUBDIR = Path("ownership") / "_derived" / "cms_snf_ownership_ccn_bridge"


@dataclass(frozen=True)
class OwnershipReleaseEntry:
    release_date: str
    ownership_source_filename: str
    bridge_lookup_filename: str
    bridge_pairing_status: str
    status: str
    ownership_source_sha256: str = ""
    enrollment_source_filename: str = ""
    enrollment_source_sha256: str = ""
    enrollment_release_date: str = ""
    allow_enrollment_date_mismatch: bool = False
    provider_info_source_filename: str = ""
    pbj_period: str = ""
    chow_source: str = ""
    build_timestamp: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, release_date: str, raw: dict[str, Any]) -> OwnershipReleaseEntry:
        return cls(
            release_date=release_date,
            ownership_source_filename=str(raw.get("ownership_source_filename") or "").strip(),
            bridge_lookup_filename=str(raw.get("bridge_lookup_filename") or "").strip(),
            bridge_pairing_status=str(raw.get("bridge_pairing_status") or "").strip(),
            status=str(raw.get("status") or "").strip(),
            ownership_source_sha256=str(raw.get("ownership_source_sha256") or "").strip(),
            enrollment_source_filename=str(raw.get("enrollment_source_filename") or "").strip(),
            enrollment_source_sha256=str(raw.get("enrollment_source_sha256") or "").strip(),
            enrollment_release_date=str(raw.get("enrollment_release_date") or "").strip(),
            allow_enrollment_date_mismatch=bool(raw.get("allow_enrollment_date_mismatch")),
            provider_info_source_filename=str(raw.get("provider_info_source_filename") or "").strip(),
            pbj_period=str(raw.get("pbj_period") or "").strip(),
            chow_source=str(raw.get("chow_source") or "").strip(),
            build_timestamp=str(raw.get("build_timestamp") or "").strip(),
            notes=str(raw.get("notes") or "").strip(),
        )


class OwnershipReleasePolicyError(RuntimeError):
    """Raised when policy is missing, invalid, or cannot be satisfied."""


def policy_path(root: Path) -> Path:
    return root / "ownership" / POLICY_FILENAME


def load_policy(root: Path) -> dict[str, Any]:
    path = policy_path(root)
    if not path.is_file():
        raise OwnershipReleasePolicyError(f"Missing ownership release policy: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OwnershipReleasePolicyError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OwnershipReleasePolicyError(f"Policy root must be object: {path}")
    return data


def _entry_map(policy: dict[str, Any]) -> dict[str, OwnershipReleaseEntry]:
    releases = policy.get("releases")
    if not isinstance(releases, dict) or not releases:
        raise OwnershipReleasePolicyError("Policy releases map is missing or empty")
    out: dict[str, OwnershipReleaseEntry] = {}
    for release_date, raw in releases.items():
        if not isinstance(raw, dict):
            raise OwnershipReleasePolicyError(f"Release entry {release_date!r} must be object")
        entry = OwnershipReleaseEntry.from_dict(str(release_date), raw)
        if not entry.ownership_source_filename:
            raise OwnershipReleasePolicyError(
                f"Release {release_date} missing ownership_source_filename"
            )
        if not entry.bridge_lookup_filename:
            raise OwnershipReleasePolicyError(f"Release {release_date} missing bridge_lookup_filename")
        if entry.bridge_pairing_status != "exact_release_date_match":
            raise OwnershipReleasePolicyError(
                f"Release {release_date} bridge_pairing_status must be exact_release_date_match"
            )
        parsed = parse_snf_owners_release_date(entry.ownership_source_filename)
        if parsed and parsed != release_date:
            raise OwnershipReleasePolicyError(
                f"Release {release_date} filename parses as {parsed}, not {release_date}"
            )
        if entry.status == "active" and not entry.ownership_source_sha256:
            raise OwnershipReleasePolicyError(
                f"Release {release_date} with status active requires ownership_source_sha256"
            )
        out[str(release_date)] = entry
    return out


def active_release_date(policy: dict[str, Any]) -> str:
    active = str(policy.get("active_release_date") or "").strip()
    if not active:
        raise OwnershipReleasePolicyError("Policy active_release_date is required")
    entries = _entry_map(policy)
    if active not in entries:
        raise OwnershipReleasePolicyError(f"active_release_date {active!r} not in releases map")
    entry = entries[active]
    if entry.status not in ("active", "active_candidate"):
        raise OwnershipReleasePolicyError(
            f"active_release_date {active!r} has status {entry.status!r}; cannot drive current paths"
        )
    return active


def resolve_release_entry(policy: dict[str, Any], release_date: str) -> OwnershipReleaseEntry:
    entries = _entry_map(policy)
    key = str(release_date or "").strip()
    if key not in entries:
        raise OwnershipReleasePolicyError(f"Release {key!r} is not configured in policy")
    return entries[key]


def resolve_ownership_source_path(
    root: Path,
    release_date: str | None = None,
    *,
    policy: dict[str, Any] | None = None,
    verify_checksum: bool = True,
) -> Path:
    """Resolve staged ownership CSV under ``<root>/ownership/`` for package/runtime use."""
    from ownership.ownership_active_release_handoff import validate_source_checksum

    pol = policy or load_policy(root)
    release = release_date or active_release_date(pol)
    entry = resolve_release_entry(pol, release)
    path = root / "ownership" / entry.ownership_source_filename
    if not path.is_file():
        raise OwnershipReleasePolicyError(
            f"Configured ownership source missing for release {release}: "
            f"{entry.ownership_source_filename}. Expected staged file at {path}. "
            "Run active release handoff staging before package assembly."
        )
    if verify_checksum and entry.ownership_source_sha256:
        validate_source_checksum(path, entry.ownership_source_sha256)
    return path


def resolve_bridge_lookup_path(
    root: Path,
    release_date: str | None = None,
    *,
    policy: dict[str, Any] | None = None,
) -> Path:
    pol = policy or load_policy(root)
    release = release_date or active_release_date(pol)
    entry = resolve_release_entry(pol, release)
    path = root / BRIDGE_SUBDIR / entry.bridge_lookup_filename
    if not path.is_file():
        raise OwnershipReleasePolicyError(f"Missing bridge lookup for {release}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("ownership_release_date") != release:
        raise OwnershipReleasePolicyError(
            f"Bridge lookup {entry.bridge_lookup_filename} release mismatch: "
            f"{payload.get('ownership_release_date')!r} != {release!r}"
        )
    if payload.get("pairing_status") != entry.bridge_pairing_status:
        raise OwnershipReleasePolicyError(
            f"Bridge lookup pairing_status mismatch for {release}"
        )
    validate_enrollment_bridge_pairing(entry, payload)
    index_path = root / BRIDGE_SUBDIR / "lookup_index.json"
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        idx_entry = index.get(release) if isinstance(index, dict) else None
        if isinstance(idx_entry, dict):
            if idx_entry.get("lookup_file") != entry.bridge_lookup_filename:
                raise OwnershipReleasePolicyError(
                    f"lookup_index.json disagrees with policy for {release}"
                )
    return path


def validate_enrollment_bridge_pairing(
    entry: OwnershipReleaseEntry,
    bridge_payload: dict[str, Any],
) -> None:
    """
    Fail closed when bridge enrollment_release_date silently lags ownership release.

    Override requires explicit ``allow_enrollment_date_mismatch: true`` on the release
    entry (documented temporary exception only).
    """
    bridge_enroll = str(bridge_payload.get("enrollment_release_date") or "").strip()
    expected = entry.enrollment_release_date or entry.release_date
    if not bridge_enroll:
        raise OwnershipReleasePolicyError(
            f"Release {entry.release_date} bridge lookup missing enrollment_release_date"
        )
    if bridge_enroll == entry.release_date:
        return
    if bridge_enroll == expected and entry.allow_enrollment_date_mismatch:
        return
    if entry.allow_enrollment_date_mismatch and bridge_enroll == entry.enrollment_release_date:
        return
    if entry.allow_enrollment_date_mismatch:
        # Documented override: bridge may use an older enrollment map.
        return
    raise OwnershipReleasePolicyError(
        f"Release {entry.release_date} enrollment_release_date mismatch: "
        f"bridge has {bridge_enroll!r}, ownership release is {entry.release_date!r}. "
        "Set allow_enrollment_date_mismatch=true only with an explicit documented override."
    )


def filtered_lookup_index_entry(entry: OwnershipReleaseEntry) -> dict[str, dict[str, str]]:
    return {
        entry.release_date: {
            "lookup_file": entry.bridge_lookup_filename,
            "pairing_status": entry.bridge_pairing_status,
            "confidence_tier": "exact_direct_match",
        }
    }


def validate_policy_runtime(root: Path) -> dict[str, Any]:
    """Validate policy, sources, and bridge artifacts. Returns readiness report."""
    policy = load_policy(root)
    active = active_release_date(policy)
    entries = _entry_map(policy)
    report: dict[str, Any] = {
        "active_release_date": active,
        "releases": {},
        "blockers": [],
        "ready_for_active": True,
    }
    for release_date, entry in entries.items():
        rel: dict[str, Any] = {
            "status": entry.status,
            "ownership_source_filename": entry.ownership_source_filename,
            "bridge_lookup_filename": entry.bridge_lookup_filename,
        }
        try:
            rel["ownership_source_path"] = str(
                resolve_ownership_source_path(root, release_date, policy=policy)
            )
            rel["ownership_source_present"] = True
        except OwnershipReleasePolicyError as exc:
            rel["ownership_source_present"] = False
            rel["ownership_source_error"] = str(exc)
            if release_date == active:
                report["blockers"].append(str(exc))
                report["ready_for_active"] = False
        try:
            rel["bridge_lookup_path"] = str(
                resolve_bridge_lookup_path(root, release_date, policy=policy)
            )
            rel["bridge_lookup_present"] = True
        except OwnershipReleasePolicyError as exc:
            rel["bridge_lookup_present"] = False
            rel["bridge_lookup_error"] = str(exc)
            if release_date == active:
                report["blockers"].append(str(exc))
                report["ready_for_active"] = False
        report["releases"][release_date] = rel
    return report


def active_release_metadata(root: Path) -> dict[str, str]:
    """Non-user-facing metadata for profile/package payloads."""
    policy = load_policy(root)
    release = active_release_date(policy)
    entry = resolve_release_entry(policy, release)
    path = resolve_ownership_source_path(root, release, policy=policy)
    meta = {
        "ownership_release_date": release,
        "source_file": path.name,
        "bridge_lookup_filename": entry.bridge_lookup_filename,
        "bridge_pairing_status": entry.bridge_pairing_status,
    }
    if entry.enrollment_source_filename:
        meta["enrollment_source_filename"] = entry.enrollment_source_filename
    if entry.enrollment_release_date:
        meta["enrollment_release_date"] = entry.enrollment_release_date
    if entry.provider_info_source_filename:
        meta["provider_info_source_filename"] = entry.provider_info_source_filename
    if entry.pbj_period:
        meta["pbj_period"] = entry.pbj_period
    if entry.chow_source:
        meta["chow_source"] = entry.chow_source
    if entry.build_timestamp:
        meta["build_timestamp"] = entry.build_timestamp
    if entry.allow_enrollment_date_mismatch:
        meta["allow_enrollment_date_mismatch"] = "true"
    return meta
