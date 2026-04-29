#!/usr/bin/env python3
"""
Release guardrail checks.

Hard-fails when displayed source months drift from active files or when staged
large files are not tracked by Git LFS.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
MAX_NON_LFS_BYTES = 100 * 1024 * 1024
REQUIRED_LFS_FILES = (
    "facility_quarterly_metrics.csv",
    "provider_info_combined.csv",
    "provider_info_combined_latest.csv",
)


def _format_month_year(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


def _parse_provider_filename(path_obj: Path) -> Optional[Tuple[int, int]]:
    lower = path_obj.stem.lower()
    m_norm = re.search(r"providerinfonorm[_-](\d{4})[_-](\d{1,2})", lower)
    if m_norm:
        y, mo = int(m_norm.group(1)), int(m_norm.group(2))
        if 1 <= mo <= 12:
            return y, mo
    m_word = re.search(r"providerinfo[_-]?([a-z]+)[_-]?(\d{4})", lower)
    if m_word:
        mo = MONTH_LOOKUP.get(m_word.group(1))
        if mo:
            return int(m_word.group(2)), mo
    m_num = re.search(r"providerinfo[_-]?(\d{4})[_-]?(\d{1,2})", lower)
    if m_num:
        y, mo = int(m_num.group(1)), int(m_num.group(2))
        if 1 <= mo <= 12:
            return y, mo
    return None


def _parse_ownership_filename(path_obj: Path) -> Optional[Tuple[int, int]]:
    lower = path_obj.stem.lower()
    m_iso = re.search(r"(\d{4})[._-](\d{1,2})(?:[._-](\d{1,2}))?", lower)
    if m_iso:
        y, mo = int(m_iso.group(1)), int(m_iso.group(2))
        if 1 <= mo <= 12:
            return y, mo
    m_word = re.search(r"owners[_-]?([a-z]+)[_-]?(\d{4})", lower)
    if m_word:
        mo = MONTH_LOOKUP.get(m_word.group(1))
        if mo:
            return int(m_word.group(2)), mo
    return None


def _run_git(args: List[str]) -> str:
    out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True)
    return out.strip()


def _latest_provider_months() -> Tuple[Optional[str], Optional[str], Optional[Path]]:
    """Latest / previous provider snapshot months; file path is the newest (y, mo), then mtime."""
    provider_dir = REPO_ROOT / "provider_info"
    dated: List[Tuple[int, int, Path]] = []
    for p in provider_dir.glob("*.csv"):
        parsed = _parse_provider_filename(p)
        if parsed:
            y, mo = parsed
            dated.append((y, mo, p))
    if not dated:
        return None, None, None
    try:
        dated.sort(key=lambda t: (t[0], t[1], t[2].stat().st_mtime), reverse=True)
    except OSError:
        dated.sort(key=lambda t: (t[0], t[1]), reverse=True)
    latest_path = dated[0][2]
    uniq_months: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    for y, mo, _ in sorted(dated, key=lambda t: (t[0], t[1]), reverse=True):
        if (y, mo) not in seen:
            seen.add((y, mo))
            uniq_months.append((y, mo))
    latest = _format_month_year(uniq_months[0][0], uniq_months[0][1])
    previous = _format_month_year(uniq_months[1][0], uniq_months[1][1]) if len(uniq_months) > 1 else latest
    return latest, previous, latest_path


def _latest_provider_snapshot_file() -> Optional[Path]:
    provider_dir = REPO_ROOT / "provider_info"
    scored: List[Tuple[int, int, float, Path]] = []
    for p in provider_dir.glob("*.csv"):
        parsed = _parse_provider_filename(p)
        if not parsed:
            continue
        y, mo = parsed
        try:
            mt = p.stat().st_mtime
        except OSError:
            mt = 0.0
        scored.append((y, mo, mt, p))
    if not scored:
        return None
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    return scored[0][3]


def _latest_ownership_month_and_file() -> Tuple[Optional[str], Optional[Path]]:
    ownership_dir = REPO_ROOT / "ownership"
    files = list(ownership_dir.glob("SNF_All_Owners*.csv")) + list(ownership_dir.glob("SNF_All_Owners*.parquet"))
    if not files:
        return None, None
    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    dated = []
    for p in files:
        parsed = _parse_ownership_filename(p)
        if parsed:
            y, mo = parsed
            dated.append((y, mo))
    if not dated:
        return None, latest_file
    y, mo = sorted(set(dated), reverse=True)[0]
    return _format_month_year(y, mo), latest_file


def _check_displayed_source_months(errors: List[str], notes: List[str]) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from utils.date_utils import get_latest_data_periods  # pylint: disable=import-error
    import app as app_module  # pylint: disable=import-error

    inferred_provider_latest, inferred_provider_previous, inferred_provider_file = _latest_provider_months()
    inferred_ownership_latest, inferred_ownership_file = _latest_ownership_month_and_file()
    displayed = app_module.get_dynamic_dates()
    file_dates = get_latest_data_periods()

    # App route dynamic dates must match file-inferred dates.
    if inferred_provider_latest and displayed.get("provider_info_latest") != inferred_provider_latest:
        errors.append(
            f"provider_info_latest mismatch: displayed={displayed.get('provider_info_latest')} "
            f"active_files={inferred_provider_latest}"
        )
    if inferred_provider_previous and displayed.get("provider_info_previous") != inferred_provider_previous:
        errors.append(
            f"provider_info_previous mismatch: displayed={displayed.get('provider_info_previous')} "
            f"active_files={inferred_provider_previous}"
        )
    if inferred_ownership_latest and displayed.get("affiliated_entity_latest") != inferred_ownership_latest:
        errors.append(
            f"affiliated_entity_latest mismatch: displayed={displayed.get('affiliated_entity_latest')} "
            f"active_files={inferred_ownership_latest}"
        )

    # date_utils and app.get_dynamic_dates should not drift.
    for key in ("provider_info_latest", "provider_info_previous", "affiliated_entity_latest"):
        if str(displayed.get(key) or "") != str(file_dates.get(key) or ""):
            errors.append(f"drift between app.get_dynamic_dates and utils.date_utils for {key}")

    # Owner dashboard selected files should point to current latest files by mtime.
    import donor.owner_donor_dashboard as owner_dash  # pylint: disable=import-error

    selected_provider_file = None
    selected_ownership_file = None
    if hasattr(owner_dash, "_get_latest_provider_info_path"):
        selected_provider_file, _ = owner_dash._get_latest_provider_info_path()
    if hasattr(owner_dash, "_get_latest_ownership_raw_path"):
        selected_ownership_file, _ = owner_dash._get_latest_ownership_raw_path()
    if selected_provider_file is None and hasattr(owner_dash, "PROVIDER_INFO_LATEST"):
        selected_provider_file = owner_dash.PROVIDER_INFO_LATEST
    if selected_ownership_file is None and hasattr(owner_dash, "OWNERSHIP_RAW"):
        selected_ownership_file = owner_dash.OWNERSHIP_RAW

    if inferred_provider_file and selected_provider_file and selected_provider_file.resolve() != inferred_provider_file.resolve():
        errors.append(
            "owner dashboard provider snapshot path does not match latest inferred snapshot: "
            f"selected={selected_provider_file.name}, inferred={inferred_provider_file.name}"
        )
    if inferred_ownership_file and selected_ownership_file and selected_ownership_file.resolve() != inferred_ownership_file.resolve():
        errors.append(
            "owner dashboard ownership snapshot path is not latest by mtime: "
            f"selected={selected_ownership_file.name}, latest={inferred_ownership_file.name}"
        )

    notes.append(
        "Displayed dates: "
        f"provider_latest={displayed.get('provider_info_latest')}, "
        f"provider_previous={displayed.get('provider_info_previous')}, "
        f"ownership_latest={displayed.get('affiliated_entity_latest')}"
    )


def _check_api_dates_consistency(errors: List[str], notes: List[str]) -> None:
    import app as app_module  # pylint: disable=import-error

    q_path = REPO_ROOT / "latest_quarter_data.json"
    if not q_path.exists():
        errors.append("latest_quarter_data.json missing")
        return
    with q_path.open("r", encoding="utf-8") as f:
        q_data = json.load(f)
    expected_display = str(q_data.get("quarter_display") or "").strip()

    client = app_module.app.test_client()
    resp = client.get("/api/dates")
    if resp.status_code != 200:
        errors.append(f"/api/dates returned status {resp.status_code}")
        return
    payload = resp.get_json(silent=True) or {}
    actual_display = str(payload.get("pbj_quarter_display") or "").strip()
    if expected_display and actual_display and expected_display != actual_display:
        errors.append(f"/api/dates quarter mismatch: api={actual_display} file={expected_display}")
    notes.append(f"/api/dates pbj_quarter_display={actual_display or 'n/a'}")


def _check_entity_counts_against_latest_snapshot(errors: List[str], notes: List[str]) -> None:
    """Ensure search_index entity counts align to latest provider snapshot roster."""
    snap = _latest_provider_snapshot_file()
    search_index_path = REPO_ROOT / "search_index.json"
    if snap is None:
        notes.append("Skipped entity-count check: no provider_info snapshot found.")
        return
    if not search_index_path.exists():
        errors.append("search_index.json missing (cannot validate entity counts).")
        return
    try:
        import pandas as pd  # pylint: disable=import-error
    except Exception:
        notes.append("Skipped entity-count check: pandas unavailable in validator runtime.")
        return

    try:
        df = pd.read_csv(snap, dtype=str, low_memory=False)
    except Exception as exc:
        errors.append(f"could not read latest provider snapshot {snap.name}: {exc}")
        return
    chain_col = "Chain ID" if "Chain ID" in df.columns else ("chain_id" if "chain_id" in df.columns else None)
    ccn_col = (
        "CMS Certification Number (CCN)"
        if "CMS Certification Number (CCN)" in df.columns
        else ("ccn" if "ccn" in df.columns else None)
    )
    if not chain_col or not ccn_col:
        errors.append(f"latest provider snapshot missing Chain ID / CCN columns: {snap.name}")
        return

    # chain_id -> unique ccn count
    ccns_by_chain: Dict[int, set] = {}
    for _, row in df.iterrows():
        raw_chain = str(row.get(chain_col) or "").strip()
        raw_ccn = str(row.get(ccn_col) or "").strip()
        if not raw_chain or not raw_ccn:
            continue
        try:
            chain_id = int(float(raw_chain))
        except Exception:
            continue
        ccn = raw_ccn.split(".")[0].zfill(6)
        ccns_by_chain.setdefault(chain_id, set()).add(ccn)
    expected = {k: len(v) for k, v in ccns_by_chain.items()}

    try:
        with search_index_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        entities = payload.get("e") or []
    except Exception as exc:
        errors.append(f"could not parse search_index.json: {exc}")
        return

    # Validate canonical entries only (no linkId alias rows).
    mismatches = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        if ent.get("linkId") is not None:
            continue
        eid = ent.get("id")
        fc = ent.get("fc")
        try:
            eid_i = int(eid)
            fc_i = int(fc)
        except Exception:
            continue
        exp = expected.get(eid_i)
        if exp is None:
            continue
        if fc_i != exp:
            mismatches.append((eid_i, fc_i, exp))
    if mismatches:
        sample = ", ".join([f"{eid}:index={idx} expected={exp}" for eid, idx, exp in mismatches[:8]])
        errors.append(f"search_index entity count mismatch vs latest provider snapshot ({snap.name}): {sample}")
    else:
        notes.append(f"Entity counts in search_index align to latest provider snapshot ({snap.name}).")


def _check_owners_autocomplete_health(errors: List[str], notes: List[str]) -> None:
    """Smoke-check owners autocomplete endpoint via main app test client."""
    import app as app_module  # pylint: disable=import-error

    client = app_module.app.test_client()
    resp = client.get("/owners/api/autocomplete?q=Ben&type=all")
    if resp.status_code != 200:
        errors.append(f"/owners/api/autocomplete returned status {resp.status_code}")
        return
    payload = resp.get_json(silent=True) or {}
    if "suggestions" not in payload or not isinstance(payload.get("suggestions"), list):
        errors.append("/owners/api/autocomplete payload missing suggestions list")
    else:
        notes.append(f"/owners/api/autocomplete ok ({len(payload.get('suggestions', []))} suggestions).")


def _check_staged_large_non_lfs(errors: List[str], notes: List[str]) -> None:
    try:
        staged = [p for p in _run_git(["diff", "--cached", "--name-only"]).splitlines() if p.strip()]
    except subprocess.CalledProcessError as exc:
        errors.append(f"could not inspect staged files: {exc}")
        return
    if not staged:
        notes.append("No staged files found for non-LFS size check.")
        return

    offenders = []
    for rel in staged:
        abs_path = REPO_ROOT / rel
        if not abs_path.exists() or not abs_path.is_file():
            continue
        size = abs_path.stat().st_size
        if size <= MAX_NON_LFS_BYTES:
            continue
        try:
            attr = _run_git(["check-attr", "filter", "--", rel])
        except subprocess.CalledProcessError:
            attr = ""
        # Example output: "file.csv: filter: lfs"
        if ": filter: lfs" not in attr:
            offenders.append((rel, size))
    if offenders:
        for rel, size in offenders:
            errors.append(f"staged file >100MB without LFS: {rel} ({size:,} bytes)")
    else:
        notes.append("Staged large-file check passed (no >100MB non-LFS staged files).")


def _check_required_lfs_configuration(errors: List[str], notes: List[str]) -> None:
    configured = []
    for rel in REQUIRED_LFS_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        try:
            attr = _run_git(["check-attr", "filter", "--", rel])
        except subprocess.CalledProcessError:
            attr = ""
        if ": filter: lfs" not in attr:
            errors.append(f"required LFS file is not LFS-configured: {rel}")
        else:
            configured.append(rel)
    if configured:
        notes.append(f"LFS configured for: {', '.join(configured)}")


def main() -> int:
    os.chdir(REPO_ROOT)
    errors: List[str] = []
    notes: List[str] = []

    try:
        _check_displayed_source_months(errors, notes)
        _check_api_dates_consistency(errors, notes)
        _check_entity_counts_against_latest_snapshot(errors, notes)
        _check_owners_autocomplete_health(errors, notes)
        _check_required_lfs_configuration(errors, notes)
        _check_staged_large_non_lfs(errors, notes)
    except Exception as exc:  # broad on purpose for guardrail script
        errors.append(f"validator crashed: {exc}")

    print("=== Release Guardrail Report ===")
    for n in notes:
        print(f"[INFO] {n}")
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1
    print("[PASS] All release guardrail checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
