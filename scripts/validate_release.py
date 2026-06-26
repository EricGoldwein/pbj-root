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
REQUIRED_DEPLOY_DATA_FILES = (
    "facility_quarterly_metrics.csv.gz",
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
    from utils.date_utils import (  # pylint: disable=import-error
        _latest_two_provider_info_months,
        newest_provider_snapshot_path,
    )

    latest, previous = _latest_two_provider_info_months(REPO_ROOT)
    latest_path = newest_provider_snapshot_path(REPO_ROOT)
    return latest, previous, latest_path


def _latest_provider_snapshot_file() -> Optional[Path]:
    from utils.date_utils import newest_provider_snapshot_path  # pylint: disable=import-error

    return newest_provider_snapshot_path(REPO_ROOT)


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
            "owner dashboard provider snapshot path is not latest by mtime: "
            f"selected={selected_provider_file.name}, latest={inferred_provider_file.name}"
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
        notes.append("Skipped entity-count check: no NH_ProviderInfo snapshot found.")
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
    if "Chain ID" not in df.columns or "CMS Certification Number (CCN)" not in df.columns:
        errors.append(f"latest provider snapshot missing expected columns: {snap.name}")
        return

    # chain_id -> unique ccn count
    ccns_by_chain: Dict[int, set] = {}
    for _, row in df.iterrows():
        raw_chain = str(row.get("Chain ID") or "").strip()
        raw_ccn = str(row.get("CMS Certification Number (CCN)") or "").strip()
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


def _check_required_deploy_data(errors: List[str], notes: List[str]) -> None:
    present = []
    for rel in REQUIRED_DEPLOY_DATA_FILES:
        p = REPO_ROOT / rel
        if not p.is_file():
            errors.append(f"required deploy data missing: {rel}")
            continue
        try:
            head = p.read_bytes()[:80]
        except OSError:
            errors.append(f"cannot read deploy data: {rel}")
            continue
        if head.startswith(b"version https://git-lfs.github.com/spec/v1"):
            errors.append(f"deploy data is still an LFS pointer (commit real file): {rel}")
        else:
            present.append(rel)
    if present:
        notes.append(f"Deploy data present: {', '.join(present)}")


STATE_MEDIAN_COLUMNS = (
    "Total_Nurse_HPRD_Median",
    "RN_HPRD_Median",
    "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD_Median",
    "LPN_HPRD_Median",
    "LPN_Care_HPRD_Median",
    "Nurse_Assistant_HPRD_Median",
    "Contract_Percentage_Median",
)

STATE_LPN_COLUMNS = ("LPN_HPRD", "LPN_Care_HPRD")


def _check_state_quarterly_median_columns(errors: List[str], notes: List[str]) -> None:
    """Hard-fail if state_quarterly_metrics.csv is missing report map median columns."""
    path = REPO_ROOT / "state_quarterly_metrics.csv"
    if not path.is_file():
        errors.append("state_quarterly_metrics.csv missing (required for /report medians).")
        return
    try:
        import pandas as pd  # pylint: disable=import-error
    except Exception:
        notes.append("Skipped state median column check: pandas unavailable.")
        return
    try:
        head = pd.read_csv(path, nrows=0)
    except Exception as exc:
        errors.append(f"could not read state_quarterly_metrics.csv header: {exc}")
        return
    cols = set(head.columns)
    missing = [c for c in STATE_MEDIAN_COLUMNS if c not in cols]
    if missing:
        errors.append(
            "state_quarterly_metrics.csv missing median columns for /report map: "
            + ", ".join(missing)
            + " — run: python scripts/patch_state_quarterly_medians.py"
        )
        return
    notes.append(
        "state_quarterly_metrics.csv includes *_Median columns (/report map median mode)."
    )


def _check_state_quarterly_lpn_columns(errors: List[str], notes: List[str]) -> None:
    path = REPO_ROOT / "state_quarterly_metrics.csv"
    if not path.is_file():
        return
    try:
        import pandas as pd  # pylint: disable=import-error

        head = pd.read_csv(path, nrows=0)
    except Exception as exc:
        errors.append(f"could not read state_quarterly_metrics.csv header for LPN check: {exc}")
        return
    cols = set(head.columns)
    missing = [c for c in STATE_LPN_COLUMNS if c not in cols]
    if missing:
        errors.append(
            "state_quarterly_metrics.csv missing LPN columns: "
            + ", ".join(missing)
            + " — run: python scripts/patch_state_quarterly_lpn.py"
        )
        return
    notes.append("state_quarterly_metrics.csv includes LPN_HPRD and LPN_Care_HPRD.")


def _pdf_release_tag(filename: str) -> Optional[str]:
    """YYYY-MM tag from an SFF posting PDF filename."""
    try:
        from sff_paths import extract_pdf_release_parts  # pylint: disable=import-error

        parts = extract_pdf_release_parts(filename)
        if not parts:
            return None
        year, month_num, _ = parts
        return f"{year:04d}-{month_num:02d}"
    except Exception:
        return None


def _check_wrapped_quarterly_json(errors: List[str], notes: List[str]) -> None:
    """Wrapped SFF uses facility_*_q2.json — CY_Qtr must match latest_quarter_data.json."""
    q_path = REPO_ROOT / "latest_quarter_data.json"
    if not q_path.exists():
        return
    with q_path.open("r", encoding="utf-8") as handle:
        latest = json.load(handle)
    expected = str(latest.get("quarter") or "").strip().upper().replace(" ", "")
    if not expected:
        return

    manifest_path = REPO_ROOT / "pbj-wrapped" / "public" / "data" / "json" / "quarter_manifest.json"
    if manifest_path.is_file():
        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest_q2 = str(manifest.get("q2_quarter") or "").strip().upper().replace(" ", "")
            if manifest_q2 and manifest_q2 != expected:
                errors.append(
                    "quarter_manifest.json q2_quarter mismatch: "
                    f"manifest={manifest_q2} latest_quarter_data={expected}"
                )
        except Exception as exc:
            errors.append(f"could not parse quarter_manifest.json: {exc}")

    national_q2 = REPO_ROOT / "pbj-wrapped" / "public" / "data" / "json" / "quarterly" / "national" / "national_q2.json"
    if not national_q2.is_file():
        notes.append("wrapped national_q2.json missing (preprocess not run yet)")
        return
    try:
        with national_q2.open("r", encoding="utf-8") as handle:
            national = json.load(handle)
        actual = str(national.get("CY_Qtr") or "").strip().upper().replace(" ", "")
    except Exception as exc:
        errors.append(f"could not parse national_q2.json: {exc}")
        return
    if actual and actual != expected:
        errors.append(
            "wrapped quarterly JSON stale: national_q2.json CY_Qtr="
            f"{actual} but latest_quarter_data.json quarter={expected} "
            "(run: cd pbj-wrapped && npm run preprocess)"
        )
    else:
        notes.append(f"wrapped national_q2 CY_Qtr={actual or 'n/a'} matches latest_quarter_data")

    manifest_counts: dict = {}
    if manifest_path.is_file():
        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest_counts = json.load(handle)
        except Exception:
            manifest_counts = {}

    facility_q2 = REPO_ROOT / "pbj-wrapped" / "public" / "data" / "json" / "quarterly" / "facility" / "facility_q2.json"
    provider_q2 = REPO_ROOT / "pbj-wrapped" / "public" / "data" / "json" / "quarterly" / "provider" / "provider_q2.json"
    for label, path, manifest_key in (
        ("facility_q2", facility_q2, "facility_q2_row_count"),
        ("provider_q2", provider_q2, "provider_q2_row_count"),
    ):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                rows = json.load(handle)
            actual_count = len(rows) if isinstance(rows, list) else 0
        except Exception as exc:
            errors.append(f"could not parse {label}.json for row count: {exc}")
            continue
        expected_count = manifest_counts.get(manifest_key)
        if isinstance(expected_count, int) and expected_count > 0 and actual_count != expected_count:
            errors.append(
                f"wrapped {label}.json row count mismatch: file={actual_count} "
                f"quarter_manifest.{manifest_key}={expected_count} "
                "(run: cd pbj-wrapped && npm run preprocess)"
            )
        elif isinstance(expected_count, int) and expected_count > 0:
            notes.append(f"wrapped {label}.json row count={actual_count} matches quarter_manifest")


def _check_sff_public_artifacts(errors: List[str], notes: List[str]) -> None:
    """Public SFF JSON must match newest raw PDF and fill months_as_sff for SFF rows."""
    try:
        from sff_paths import (  # pylint: disable=import-error
            SFF_FACILITIES_JSON,
            SFF_PUBLIC_JSON,
            find_latest_raw_pdf,
        )
    except Exception as exc:
        errors.append(f"SFF path helpers unavailable: {exc}")
        return

    if not SFF_PUBLIC_JSON.is_file():
        errors.append("pbj-wrapped/public/sff-facilities.json missing (run scripts/sff/publish_sff_artifacts.py)")
        return

    try:
        with SFF_PUBLIC_JSON.open("r", encoding="utf-8") as handle:
            public_data = json.load(handle)
    except Exception as exc:
        errors.append(f"could not parse {SFF_PUBLIC_JSON.name}: {exc}")
        return

    doc = public_data.get("document_date") or {}
    public_release = str(doc.get("source_release") or "").strip()
    latest_pdf = find_latest_raw_pdf()
    if latest_pdf is None:
        errors.append("no raw SFF PDF found under data_sources/cms/sff/raw")
    else:
        expected_release = _pdf_release_tag(latest_pdf.name)
        if expected_release and public_release != expected_release:
            errors.append(
                "SFF public JSON source_release mismatch: "
                f"public={public_release or 'n/a'} newest_pdf={expected_release} ({latest_pdf.name})"
            )

    facilities = public_data.get("facilities") or []
    sff_rows = [row for row in facilities if isinstance(row, dict) and row.get("category") == "SFF"]
    with_months = 0
    if not sff_rows:
        errors.append("public sff-facilities.json has no SFF category rows")
    else:
        with_months = sum(1 for row in sff_rows if row.get("months_as_sff") is not None)
        if with_months < len(sff_rows):
            errors.append(
                f"months_as_sff missing for {len(sff_rows) - with_months}/{len(sff_rows)} public SFF rows"
            )

    if SFF_FACILITIES_JSON.is_file():
        try:
            with SFF_FACILITIES_JSON.open("r", encoding="utf-8") as handle:
                derived_data = json.load(handle)
            derived_release = str((derived_data.get("document_date") or {}).get("source_release") or "").strip()
            if public_release and derived_release and public_release != derived_release:
                errors.append(
                    f"SFF derived vs public source_release mismatch: derived={derived_release} public={public_release}"
                )
        except Exception as exc:
            errors.append(f"could not parse derived SFF JSON: {exc}")

    notes.append(
        "SFF public artifact: "
        f"release={public_release or 'n/a'}, sff_rows={len(sff_rows)}, "
        f"months_as_sff={with_months}/{len(sff_rows)}"
    )


def _parse_chain_performance_month(path_obj: Path) -> Optional[Tuple[int, int]]:
    """Parse Month_Year from Nursing_Home_Chain_Performance_Measures_May_2026.csv."""
    m_word = re.search(
        r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|"
        r"sep|sept|september|oct|october|nov|november|dec|december)[_-](\d{4})",
        path_obj.stem,
        re.IGNORECASE,
    )
    if not m_word:
        return None
    month = MONTH_LOOKUP.get(m_word.group(1).lower())
    if not month:
        return None
    return int(m_word.group(2)), month


def _latest_chain_performance_csv() -> Optional[Path]:
    ownership_dir = REPO_ROOT / "ownership"
    files = list(ownership_dir.glob("Nursing_Home_Chain_Performance_Measures_*.csv"))
    dated: List[Tuple[Tuple[int, int], Path]] = []
    for path in files:
        parsed = _parse_chain_performance_month(path)
        if parsed:
            dated.append((parsed, path))
    if not dated:
        return None
    dated.sort(key=lambda item: item[0], reverse=True)
    return dated[0][1]


def _check_chain_csv_freshness(errors: List[str], notes: List[str]) -> None:
    """Newest chain CSV must be tracked in git and include spot entity 885 (Baptist Home)."""
    latest = _latest_chain_performance_csv()
    if latest is None:
        errors.append("no Nursing_Home_Chain_Performance_Measures_*.csv found in ownership/")
        return

    rel = latest.relative_to(REPO_ROOT).as_posix()
    try:
        tracked = {line.strip().replace("\\", "/") for line in _run_git(["ls-files"]).splitlines()}
    except subprocess.CalledProcessError as exc:
        errors.append(f"could not inspect git-tracked chain CSVs: {exc}")
        tracked = set()
    if tracked and rel not in tracked:
        errors.append(
            f"newest chain performance CSV is not git-tracked (prod will miss entity takeaway data): {rel}"
        )

    parsed = _parse_chain_performance_month(latest)
    month_label = _format_month_year(parsed[0], parsed[1]) if parsed else latest.name

    try:
        import pandas as pd  # pylint: disable=import-error
    except Exception:
        notes.append("Skipped chain spot-check: pandas unavailable.")
        return

    try:
        df = pd.read_csv(latest, dtype=str, low_memory=False)
    except Exception as exc:
        errors.append(f"could not read chain CSV {latest.name}: {exc}")
        return

    id_col = next((c for c in df.columns if str(c).strip().lower() in ("chain id", "chain_id")), None)
    name_col = next((c for c in df.columns if str(c).strip().lower() == "chain"), None)
    if not id_col:
        errors.append(f"chain CSV missing Chain ID column: {latest.name}")
        return

    spot_id = "885"
    hit = df[df[id_col].astype(str).str.strip().str.split(".").str[0] == spot_id]
    if hit.empty:
        errors.append(f"chain spot entity {spot_id} missing from newest chain CSV ({latest.name})")
        return

    chain_name = ""
    if name_col and not hit.empty:
        chain_name = str(hit.iloc[0].get(name_col) or "").strip()
    if "BAPTIST" not in chain_name.upper():
        errors.append(
            f"chain spot entity {spot_id} name unexpected in {latest.name}: {chain_name or 'n/a'}"
        )

    notes.append(
        f"Chain CSV fresh: {latest.name} ({month_label}), spot entity {spot_id}={chain_name or 'ok'}"
    )


def _check_public_case_mix_export(errors: List[str], notes: List[str]) -> None:
    """Unit tests for public case-mix export rule (no full app data load)."""
    script = REPO_ROOT / "scripts" / "check_public_case_mix_export.py"
    if not script.is_file():
        notes.append("Public case-mix export check skipped (script missing).")
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--unit-only"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        errors.append(f"public case-mix export check failed to run: {exc}")
        return
    if proc.returncode != 0:
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-8:]
        errors.append(
            "public case-mix export unit checks failed: " + " | ".join(tail) or proc.returncode
        )
        return
    notes.append("Public case-mix export unit checks passed.")


def _check_provider_release_handoff(errors: List[str], notes: List[str]) -> None:
    """Ensure newest Norm has paired NH locally and passes norm validate (PBJapp parity)."""
    script = REPO_ROOT / "scripts" / "verify_provider_release_handoff.py"
    if not script.is_file():
        notes.append("Skipped provider handoff check: verify_provider_release_handoff.py missing.")
        return
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    for line in (proc.stdout or "").splitlines():
        if line.startswith("[INFO] "):
            notes.append(f"provider handoff: {line[7:]}")
        elif line.startswith("[FAIL] "):
            errors.append(line[7:])
    if proc.returncode != 0 and not any("provider handoff" in e for e in errors):
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        errors.append(f"provider release handoff check failed: {tail[-1] if tail else proc.returncode}")


def main() -> int:
    os.chdir(REPO_ROOT)
    errors: List[str] = []
    notes: List[str] = []

    try:
        _check_displayed_source_months(errors, notes)
        _check_api_dates_consistency(errors, notes)
        _check_entity_counts_against_latest_snapshot(errors, notes)
        _check_owners_autocomplete_health(errors, notes)
        _check_required_deploy_data(errors, notes)
        _check_state_quarterly_median_columns(errors, notes)
        _check_state_quarterly_lpn_columns(errors, notes)
        _check_staged_large_non_lfs(errors, notes)
        _check_sff_public_artifacts(errors, notes)
        _check_wrapped_quarterly_json(errors, notes)
        _check_chain_csv_freshness(errors, notes)
        _check_public_case_mix_export(errors, notes)
        _check_provider_release_handoff(errors, notes)
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
