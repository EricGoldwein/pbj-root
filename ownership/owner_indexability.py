"""Owner profile indexability: index / noindex_follow / suppress + sitemap cache."""
from __future__ import annotations

import csv
import gzip
import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES, profile_is_visible

OwnerIndexClass = Literal["index", "noindex_follow", "suppress"]

_OWNER_INDEX_CACHE_GZ = Path(__file__).resolve().parent / "owner_indexability_cache.json.gz"
_AUDIT_DEFAULT_CSV = Path(__file__).resolve().parent / "owner_indexability_audit.csv"

_PLACEHOLDER_NAME_RE = re.compile(
    r"^(unknown|organization|org|n/?a|none|null|test|tbd|—|-|\.)$",
    re.IGNORECASE,
)
_CHOW_RECENT_YEARS = 3
_CCN_ALLOWED_RE = re.compile(r"^[A-Z0-9]{1,6}$")


def _clean_name(val: Any) -> str:
    return re.sub(r"\s+", " ", str(val or "").strip())


def is_suppress_owner_name(name: str) -> bool:
    """True when display name is blank, placeholder, or too ambiguous to publish."""
    s = _clean_name(name)
    if not s or len(s) < 2:
        return True
    if _PLACEHOLDER_NAME_RE.match(s):
        return True
    if re.fullmatch(r"[\W\d_]+", s):
        return True
    # Single token under 4 chars (e.g. "A B" ok, "X" not)
    parts = [p for p in re.split(r"\s+", s) if p]
    if len(parts) == 1 and len(parts[0]) < 3:
        return True
    return False


@lru_cache(maxsize=1)
def _active_provider_ccns() -> frozenset[str]:
    """CCNs on the latest public provider roster (search_index.json)."""
    repo = Path(__file__).resolve().parent.parent
    path = repo / "search_index.json"
    if not path.is_file():
        return frozenset()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return frozenset()
    out: set[str] = set()
    for fac in data.get("f") or []:
        raw = _norm_ccn(fac.get("c"))
        if raw:
            out.add(raw)
    return frozenset(out)


def _norm_ccn(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if "." in s:
        s = s.split(".")[0]
    if not s or not _CCN_ALLOWED_RE.fullmatch(s):
        return ""
    return s.zfill(6)


def count_active_facilities(profile: dict[str, Any]) -> int:
    """Facilities linked to an active CCN on the public provider roster (or PBJ-verified)."""
    active_ccns = _active_provider_ccns()
    seen: set[str] = set()
    n = 0
    for fac in profile.get("facilities") or []:
        ccn = _norm_ccn(fac.get("ccn"))
        if not ccn or ccn in seen:
            continue
        if ccn in active_ccns or fac.get("pbj_matched"):
            seen.add(ccn)
            n += 1
    return n


def _parse_chow_date(raw: Any) -> datetime | None:
    s = str(raw or "").strip()[:10]
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def meaningful_context_flags(profile: dict[str, Any]) -> list[str]:
    """Signals that make a single-facility owner page worth indexing."""
    flags: list[str] = []
    facilities = profile.get("facilities") or []

    for fac in facilities:
        if fac.get("has_abuse"):
            flags.append("abuse")
            break

    for fac in facilities:
        sff = str(fac.get("sff_status") or fac.get("sff") or "").strip().upper()
        if sff == "SFF" or "SPECIAL FOCUS" in sff:
            flags.append("sff")
            break
        if "CANDIDATE" in sff:
            flags.append("sffc")
            break

    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * _CHOW_RECENT_YEARS)
    for rec in profile.get("chow_transactions") or []:
        dt = _parse_chow_date(rec.get("effective_date"))
        if dt and dt >= cutoff:
            flags.append("recent_chow")
            break

    states = {str(s or "").strip().upper()[:2] for s in (profile.get("states") or []) if s}
    ps = profile.get("portfolio_summary") or {}
    if len(states) >= 2 or int(ps.get("n_states") or 0) >= 2:
        flags.append("multi_state")

    if int(ps.get("n_facilities") or len(facilities) or 0) >= 2:
        flags.append("portfolio")

    if profile.get("related_associates"):
        flags.append("network")

    if profile.get("control_parties"):
        flags.append("affiliated")

    kind = str(profile.get("profile_kind") or "")
    if kind in ("both", "enrollment"):
        flags.append("operator_grouping")

    if profile.get("enforcement_context") or profile.get("has_enforcement"):
        flags.append("enforcement")

    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def classify_owner_profile(profile: dict[str, Any] | None) -> tuple[OwnerIndexClass, str, dict[str, Any]]:
    """
    Classify an owner profile for crawl/index policy.

    Returns (classification, reason_code, metadata dict).
    """
    meta: dict[str, Any] = {
        "owner_name": "",
        "associate_id": "",
        "facility_count": 0,
        "active_facility_count": 0,
        "flags": [],
    }
    if not profile:
        return "suppress", "missing_profile", meta

    pac = str(profile.get("associate_id") or "").strip()
    name = _clean_name(profile.get("display_name") or "")
    meta["owner_name"] = name
    meta["associate_id"] = pac
    facilities = profile.get("facilities") or []
    meta["facility_count"] = len(facilities)

    if not profile_is_visible(profile):
        return "suppress", "not_visible_state", meta

    if is_suppress_owner_name(name):
        return "suppress", "bad_or_blank_name", meta

    if len(pac) != 10 or not pac.isdigit():
        return "suppress", "malformed_pac", meta

    active_n = count_active_facilities(profile)
    meta["active_facility_count"] = active_n
    flags = meaningful_context_flags(profile)
    meta["flags"] = flags

    if active_n >= 2:
        return "index", "two_or_more_active_facilities", meta

    if active_n == 1:
        if flags:
            return "index", f"single_facility_with_context:{','.join(flags[:3])}", meta
        return "noindex_follow", "single_facility_no_context", meta

    # No active roster facilities
    if profile.get("chow_transactions") and not is_suppress_owner_name(name):
        return "noindex_follow", "chow_only_no_active_facilities", meta

    return "suppress", "no_active_facilities", meta


def owner_robots_meta(classification: OwnerIndexClass) -> str | None:
    if classification == "index":
        return None
    if classification == "noindex_follow":
        return "noindex, follow"
    return "noindex, nofollow"


def load_owner_indexability_cache() -> dict[str, dict[str, Any]]:
    """PAC -> {classification, reason, owner_name, ...} from deploy-built cache."""
    if not _OWNER_INDEX_CACHE_GZ.is_file():
        return {}
    try:
        with gzip.open(_OWNER_INDEX_CACHE_GZ, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and isinstance(raw.get("by_pac"), dict):
            return {str(k): v for k, v in raw["by_pac"].items() if isinstance(v, dict)}
        if isinstance(raw, dict):
            return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    except Exception:
        pass
    return {}


def _write_owner_indexability_cache(rows: list[dict[str, Any]]) -> None:
    by_pac = {str(r["associate_id"]): r for r in rows if r.get("associate_id")}
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by_pac": by_pac,
    }
    _OWNER_INDEX_CACHE_GZ.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(_OWNER_INDEX_CACHE_GZ, "wt", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


def summarize_owner_indexability_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"index": 0, "noindex_follow": 0, "suppress": 0}
    for row in rows:
        cl = str(row.get("classification") or "")
        if cl in counts:
            counts[cl] += 1
    return counts


def write_owner_indexability_audit_csv(
    rows: list[dict[str, Any]], path: Path | None = None
) -> Path:
    out_path = path or _AUDIT_DEFAULT_CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "owner_name",
        "associate_id",
        "facility_count",
        "active_facility_count",
        "flags",
        "classification",
        "reason",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(
                {
                    "owner_name": row.get("owner_name") or "",
                    "associate_id": row.get("associate_id") or "",
                    "facility_count": row.get("facility_count") or 0,
                    "active_facility_count": row.get("active_facility_count") or 0,
                    "flags": ",".join(row.get("flags") or []),
                    "classification": row.get("classification") or "",
                    "reason": row.get("reason") or "",
                }
            )
    return out_path


def log_owner_indexability_summary(
    owner_rows: list[dict[str, Any]],
    *,
    provider_included: int = 0,
    provider_excluded: int = 0,
) -> dict[str, int]:
    """Print summary counts; return owner classification totals."""
    owner_counts = summarize_owner_indexability_rows(owner_rows)
    print(
        "[owner_indexability] "
        f"indexed={owner_counts['index']} "
        f"noindex_follow={owner_counts['noindex_follow']} "
        f"suppressed={owner_counts['suppress']} "
        f"| providers_in_sitemap={provider_included} "
        f"providers_excluded={provider_excluded}",
        flush=True,
    )
    return owner_counts


def refresh_owner_indexability_cache(
    *,
    audit_csv: Path | None = None,
    log: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Scan public CT/NY catalog PACs, classify each resolved profile, write cache + CSV.
    """
    from ownership.owner_profile import (
        load_owner_profile_resolved,
        normalize_associate_id,
        _build_public_owner_search_catalog_entries,
    )

    catalog = _build_public_owner_search_catalog_entries()
    pacs = sorted(
        {
            normalize_associate_id(str(row.get("associate_id") or ""))
            for row in catalog
            if normalize_associate_id(str(row.get("associate_id") or ""))
        }
    )

    rows: list[dict[str, Any]] = []
    for pac in pacs:
        if len(pac) != 10:
            continue
        try:
            profile = load_owner_profile_resolved(pac)
        except Exception:
            profile = None
        classification, reason, meta = classify_owner_profile(profile)
        rows.append(
            {
                "associate_id": pac,
                "owner_name": meta.get("owner_name") or "",
                "facility_count": meta.get("facility_count") or 0,
                "active_facility_count": meta.get("active_facility_count") or 0,
                "flags": meta.get("flags") or [],
                "classification": classification,
                "reason": reason,
            }
        )

    _write_owner_indexability_cache(rows)
    csv_path = write_owner_indexability_audit_csv(rows, audit_csv)
    if log:
        log_owner_indexability_summary(rows)
        print(f"[owner_indexability] audit CSV: {csv_path}", flush=True)
    return rows, summarize_owner_indexability_rows(rows)


def public_owner_associate_ids_for_sitemap() -> list[str]:
    """10-digit PACs classified as index (falls back to live classify if cache missing)."""
    cache = load_owner_indexability_cache()
    if cache:
        return sorted(
            pac
            for pac, row in cache.items()
            if str(row.get("classification") or "") == "index" and len(pac) == 10
        )

    from ownership.owner_profile import (
        load_owner_profile_resolved,
        normalize_associate_id,
        _build_public_owner_search_catalog_entries,
    )

    out: list[str] = []
    for row in _build_public_owner_search_catalog_entries():
        pac = normalize_associate_id(str(row.get("associate_id") or ""))
        if len(pac) != 10:
            continue
        try:
            profile = load_owner_profile_resolved(pac)
        except Exception:
            profile = None
        cl, _reason, _meta = classify_owner_profile(profile)
        if cl == "index":
            out.append(pac)
    return sorted(out)


def classification_for_pac(pac: str, profile: dict[str, Any] | None) -> tuple[OwnerIndexClass, str, dict[str, Any]]:
    """Use deploy cache when present; otherwise classify from profile."""
    pac_n = str(pac or "").strip()
    cache = load_owner_indexability_cache()
    if pac_n in cache:
        row = cache[pac_n]
        cl = str(row.get("classification") or "suppress")
        if cl not in ("index", "noindex_follow", "suppress"):
            cl = "suppress"
        reason = str(row.get("reason") or "")
        meta = {
            "owner_name": row.get("owner_name") or "",
            "associate_id": pac_n,
            "facility_count": row.get("facility_count") or 0,
            "active_facility_count": row.get("active_facility_count") or 0,
            "flags": row.get("flags") or [],
        }
        return cl, reason, meta  # type: ignore[return-value]
    return classify_owner_profile(profile)


def provider_ccns_for_sitemap() -> tuple[list[str], int, int]:
    """
    Active provider CCNs for sitemap (search_index roster).

    Returns (ccn_list, included_count, excluded_count_from_combined_roster).
    """
    included = sorted(_active_provider_ccns())
    excluded = 0
    try:
        import pandas as pd

        repo = Path(__file__).resolve().parent.parent
        for name in ("provider_info_combined_latest.csv", "provider_info_combined.csv"):
            path = repo / name
            if not path.is_file():
                continue
            header = list(pd.read_csv(path, nrows=0).columns)
            ccn_col = next((c for c in header if c.lower() in ("ccn", "provnum")), None)
            if not ccn_col:
                continue
            active = _active_provider_ccns()
            all_ccns: set[str] = set()
            for chunk in pd.read_csv(path, usecols=[ccn_col], dtype=str, low_memory=False, chunksize=100_000):
                for raw in chunk[ccn_col].dropna().astype(str):
                    ccn = _norm_ccn(raw)
                    if ccn:
                        all_ccns.add(ccn)
            if all_ccns:
                excluded = len(all_ccns - active)
            break
    except Exception:
        excluded = 0

    historic_raw = __import__("os").environ.get("PBJ_SITEMAP_HISTORIC_PROVIDER_CCNS", "")
    if historic_raw.strip():
        extra = {_norm_ccn(p.strip()) for p in historic_raw.split(",") if p.strip()}
        included = sorted(set(included) | {c for c in extra if c})
    return included, len(included), excluded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build owner indexability cache and audit CSV")
    parser.add_argument("--audit-csv", type=Path, default=_AUDIT_DEFAULT_CSV)
    args = parser.parse_args()
    refresh_owner_indexability_cache(audit_csv=args.audit_csv)
