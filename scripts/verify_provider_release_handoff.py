#!/usr/bin/env python3
"""Cross-check PBJapp provider release vs pbj-root before commit.

Catches the common failure mode: ProviderInfoNorm copied without paired
NH_ProviderInfo (backfill/parity cannot run; search_index dates drift).

Usage:
    python scripts/verify_provider_release_handoff.py
    python scripts/verify_provider_release_handoff.py --release-key 2026-06

Exit 0 = OK. Exit 1 = action required before push.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.date_utils import _parse_provider_filename  # noqa: E402


def _pbjapp_root() -> Path | None:
    env = os.environ.get("PBJAPP_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None
    sibling = REPO_ROOT.parent / "PBJapp"
    return sibling if sibling.is_dir() else None


def _newest_norm_path() -> Path | None:
    provider_dir = REPO_ROOT / "provider_info"
    paths = [
        p
        for p in provider_dir.glob("ProviderInfoNorm_*.csv")
        if p.is_file() and _parse_provider_filename(p)
    ]
    if not paths:
        return None
    return max(
        paths,
        key=lambda p: _parse_provider_filename(p) or (0, 0),
    )


def _nh_path_for_norm(norm_path: Path) -> Path | None:
    parsed = _parse_provider_filename(norm_path)
    if not parsed:
        return None
    year, month = parsed
    month_names = (
        "",
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    provider_dir = REPO_ROOT / "provider_info"
    for name in (
        f"NH_ProviderInfo_{month_names[month]}{year}.csv",
        f"NH_ProviderInfo_{month_names[month]}_{year}.csv",
    ):
        path = provider_dir / name
        if path.is_file():
            return path
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_handoff(pbjapp: Path, release_key: str) -> dict | None:
    handoff = pbjapp / "provider_info" / "_manifests" / release_key / "pbj_root_handoff.json"
    if not handoff.is_file():
        return None
    return json.loads(handoff.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PBJapp → pbj-root provider handoff")
    parser.add_argument(
        "--release-key",
        default="",
        help="YYYY-MM (default: month from newest ProviderInfoNorm in pbj-root)",
    )
    args = parser.parse_args()

    norm = _newest_norm_path()
    if norm is None:
        print("verify_provider_release_handoff: ERROR no ProviderInfoNorm_*.csv in pbj-root", file=sys.stderr)
        return 1

    parsed = _parse_provider_filename(norm)
    release_key = args.release_key.strip() or (f"{parsed[0]}-{parsed[1]:02d}" if parsed else "")
    nh_local = _nh_path_for_norm(norm)
    pbjapp = _pbjapp_root()

    errors: list[str] = []
    notes: list[str] = []

    notes.append(f"newest_norm={norm.name}")
    notes.append(f"release_key={release_key or 'n/a'}")

    if nh_local is None:
        errors.append(
            f"paired NH snapshot missing in pbj-root for {norm.name} "
            f"(run PBJapp: python scripts/sync_to_pbj_root.py provider-release "
            f"--release-key {release_key} --force)"
        )
    else:
        notes.append(f"paired_nh_local={nh_local.name}")

    if pbjapp is not None:
        handoff = _load_handoff(pbjapp, release_key) if release_key else None
        if handoff:
            sync = handoff.get("pbj_root_sync") or {}
            expected_sha = str(sync.get("sha256") or "")
            if expected_sha and _sha256(norm) != expected_sha:
                errors.append(
                    f"Norm sha256 mismatch vs PBJapp handoff ({release_key}): "
                    f"pbj-root differs from ingest — re-sync from PBJapp"
                )
            else:
                notes.append("handoff_sha256=match" if expected_sha else "handoff_sha256=not_recorded")
        else:
            notes.append(f"no PBJapp handoff manifest for {release_key}")

        if nh_local is None and parsed:
            year, month = parsed
            month_names = (
                "",
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            )
            nh_pbjapp = pbjapp / "provider_info" / f"NH_ProviderInfo_{month_names[month]}{year}.csv"
            if nh_pbjapp.is_file():
                errors.append(
                    f"PBJapp has {nh_pbjapp.name} but pbj-root does not — sync did not copy NH for backfill"
                )
    else:
        notes.append("PBJapp sibling not found (set PBJAPP_ROOT to cross-check handoff)")

    validate = REPO_ROOT / "scripts" / "validate_provider_norm_snapshot.py"
    if validate.is_file():
        proc = subprocess.run(
            [sys.executable, str(validate), "--path", str(norm)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()
        summary = tail[-1] if tail else f"exit {proc.returncode}"
        if proc.returncode != 0:
            errors.append(f"validate_provider_norm_snapshot failed: {summary}")
        else:
            mode = "NH parity" if nh_local is not None and "NH parity" in summary else "self-check"
            notes.append(f"norm_validate={mode}: {summary}")

    print("=== Provider release handoff ===")
    for n in notes:
        print(f"[INFO] {n}")
    for e in errors:
        print(f"[FAIL] {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
