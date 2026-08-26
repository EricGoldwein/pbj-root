"""
Portfolio-level metrics for /owners/<pac> owner/control profiles.

Lightweight analogue to PBJapp ownership/build_owner_facility_metrics.py summaries,
using provider_info_combined.csv + search_index (no full ETL required).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent

_NORM_FILENAME_RE = re.compile(r"ProviderInfoNorm_(\d{4})_(\d{2})", re.IGNORECASE)

# CMS Five-Star / Care Compare Technical Users' Guide (July 2026): for full-quarter
# total nurse staffing, exclude zero HPRD and values greater than 12 HPRD.
# The historical <1.5 HPRD exclusion applied only before January 2022 and is NOT used.
PORTFOLIO_HPRD_EXCLUDE_AT_OR_BELOW = 0.0
PORTFOLIO_HPRD_MAX = 12.0
PORTFOLIO_OVERALL_RATING_MIN = 1.0
PORTFOLIO_OVERALL_RATING_MAX = 5.0
# Min verified facilities with star ratings before portfolio bar charts render.
PORTFOLIO_STAR_DIST_MIN = 5

PORTFOLIO_METHODOLOGY_SUMMARY = (
    "Portfolio HPRD is a descriptive linked-facility statistic (not owner-attributable "
    "staffing responsibility). Means use PBJ-verified facilities whose CMS relationship "
    "to the profile began on or before the PBJ quarter start (any role category), with "
    "usable HPRD and a census or certified-beds weight. Each CCN counts once. Missing "
    "HPRD or star ratings are omitted from means but the facility remains in the table. "
    "Total nurse HPRD values ≤ "
    f"{PORTFOLIO_HPRD_EXCLUDE_AT_OR_BELOW:g} or above "
    f"{PORTFOLIO_HPRD_MAX:g} HPRD are excluded (current CMS full-quarter total-nurse "
    "exclusions; the pre-2022 <1.5 floor is not applied). Overall star ratings outside "
    f"{PORTFOLIO_OVERALL_RATING_MIN:g}–{PORTFOLIO_OVERALL_RATING_MAX:g} are excluded."
)

# Exact help body for the owner-profile Portfolio HPRD card (?).
PORTFOLIO_HPRD_CARD_HELP = (
    "Resident-weighted average nurse HPRD across CMS-linked facilities whose relationship "
    "to this profile was in place by the start of the reporting quarter. Each facility is "
    "counted once. Facilities with uncertain timing, an unverified PBJ match, or unusable "
    "staffing data are excluded. This describes associated facilities and does not establish "
    "responsibility for staffing."
)

# Mutually exclusive terminal buckets for Portfolio HPRD reconciliation.
PORTFOLIO_HPRD_TERMINAL_BUCKETS = (
    "timing_excluded_or_uncertain",
    "pbj_match_excluded",
    "missing_hprd",
    "hprd_le_zero",
    "hprd_gt_12",
    "missing_invalid_weight",
    "included",
)


def is_plausible_portfolio_hprd(hprd: float) -> bool:
    """
    True when total nurse HPRD may enter Portfolio HPRD means.

    Current CMS full-quarter total-nurse rule: exclude ≤ 0 and > 12.
    Does not apply the obsolete pre-2022 <1.5 floor.
    """
    return hprd > PORTFOLIO_HPRD_EXCLUDE_AT_OR_BELOW and hprd <= PORTFOLIO_HPRD_MAX


def portfolio_hprd_value_exclusion_reason(hprd: float | None) -> str | None:
    """Return a value-level exclusion reason, or None when the HPRD value is usable."""
    if hprd is None:
        return "missing_hprd"
    if hprd <= PORTFOLIO_HPRD_EXCLUDE_AT_OR_BELOW:
        return "hprd_le_zero"
    if hprd > PORTFOLIO_HPRD_MAX:
        return "hprd_gt_12"
    return None


def classify_portfolio_hprd_terminal_bucket(facility: dict[str, Any]) -> str:
    """
    Assign one mutually exclusive Portfolio HPRD terminal category.

    Priority:
      1. timing excluded/uncertain (portfolio inclusion not supported)
      2. PBJ-match excluded
      3. missing HPRD
      4. HPRD ≤ 0
      5. HPRD > 12
      6. missing/invalid weight
      7. included
    """
    status = str(facility.get("hprd_portfolio_inclusion_status") or "").strip()
    if status != "supported":
        return "timing_excluded_or_uncertain"
    if not facility.get("pbj_matched"):
        return "pbj_match_excluded"
    h = _parse_float(facility.get("hprd"))
    reason = portfolio_hprd_value_exclusion_reason(h)
    if reason is not None:
        return reason
    weight = _portfolio_metric_weight(facility)
    if weight is None or weight <= 0:
        return "missing_invalid_weight"
    return "included"


def reconcile_portfolio_hprd_buckets(
    facilities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Count mutually exclusive terminal buckets; must sum to len(facilities)."""
    counts = {k: 0 for k in PORTFOLIO_HPRD_TERMINAL_BUCKETS}
    obsolete_below_1_5_now_included = 0
    for f in facilities:
        bucket = classify_portfolio_hprd_terminal_bucket(f)
        counts[bucket] = counts.get(bucket, 0) + 1
        if bucket == "included":
            h = _parse_float(f.get("hprd"))
            if h is not None and 0.0 < h < 1.5:
                obsolete_below_1_5_now_included += 1
    total = len(facilities)
    return {
        "total_unique_ccns": total,
        "buckets": counts,
        "bucket_sum": sum(counts.values()),
        "reconcile_ok": sum(counts.values()) == total,
        "obsolete_below_1_5_now_included": obsolete_below_1_5_now_included,
    }


def is_plausible_overall_rating(rating: float) -> bool:
    """True when value is a valid CMS overall star rating."""
    return PORTFOLIO_OVERALL_RATING_MIN <= rating <= PORTFOLIO_OVERALL_RATING_MAX


def _portfolio_metric_weight(facility: dict[str, Any]) -> float | None:
    """Census preferred; certified beds as fallback. None if neither is available."""
    return _parse_float(facility.get("census")) or _parse_float(facility.get("beds"))


def _parse_float(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_abuse_flag(val: Any) -> bool:
    s = str(val or "").strip().upper()
    return s in ("Y", "YES", "1", "TRUE")


def _parse_pct_max(pcts: list[str]) -> float | None:
    best: float | None = None
    for p in pcts:
        v = _parse_float(p)
        if v is not None:
            best = v if best is None else max(best, v)
    return best


def _provider_info_csv_paths() -> list[Path]:
    paths: list[Path] = []
    provider_dir = _REPO / "provider_info"
    if provider_dir.is_dir():
        paths.extend(sorted(provider_dir.glob("ProviderInfoNorm_*.csv"), reverse=True))
    paths.extend(
        [
            _REPO / "provider_info_combined_latest.csv",
            _REPO / "provider_info_norm.csv",
        ]
    )
    return paths


def _is_historical_provider_info_dump(path: Path) -> bool:
    """True for the multi-quarter provider_info_combined.csv (often ~800MB+)."""
    return path.name.lower() == "provider_info_combined.csv"


def provider_info_source_sort_key(path: Path) -> tuple:
    """
    Recency key for provider-info snapshots.

    Newest ProviderInfoNorm_YYYY_MM wins over combined_latest / undated files.
    Historical provider_info_combined.csv is never preferred on the hot path.
    """
    name = path.name
    if _is_historical_provider_info_dump(path):
        return (0, 0, 0, name)
    m = _NORM_FILENAME_RE.search(name)
    if m:
        return (2, int(m.group(1)), int(m.group(2)), name)
    low = name.lower()
    if low == "provider_info_combined_latest.csv":
        return (1, 0, 0, name)
    if low == "provider_info_norm.csv":
        return (1, 0, 0, name)
    return (0, 0, 0, name)


def newest_provider_info_norm_path() -> Path | None:
    provider_dir = _REPO / "provider_info"
    if not provider_dir.is_dir():
        return None
    norms = sorted(
        provider_dir.glob("ProviderInfoNorm_*.csv"),
        key=provider_info_source_sort_key,
        reverse=True,
    )
    return norms[0] if norms else None


def ownership_provider_info_paths() -> list[Path]:
    """
    Provider-info files for ownership enrichment / CCN crosswalks (hot path).

    Canonical source is the newest ``ProviderInfoNorm_*.csv`` (by filename date).
    ``provider_info_combined_latest.csv`` may follow only as a blank-fill fallback
    when Norm is missing columns. Historical ``provider_info_combined.csv`` is
    never on the hot path.
    """
    seen: set[Path] = set()
    seen_sig: set[tuple[int, int]] = set()
    ordered: list[Path] = []

    def _add(path: Path) -> None:
        if not path.is_file() or path in seen or _is_historical_provider_info_dump(path):
            return
        try:
            st = path.stat()
            sig = (int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
        except OSError:
            return
        # Skip byte-identical copies (common: Norm copied to combined_latest).
        if sig in seen_sig:
            return
        ordered.append(path)
        seen.add(path)
        seen_sig.add(sig)

    # Policy-configured Norm first when present and on disk.
    try:
        from ownership.ownership_release_policy import (
            active_release_date,
            load_policy,
            resolve_release_entry,
        )

        pol = load_policy(_REPO)
        entry = resolve_release_entry(pol, active_release_date(pol))
        if entry.provider_info_source_filename:
            configured = _REPO / "provider_info" / entry.provider_info_source_filename
            if not configured.is_file():
                configured = _REPO / entry.provider_info_source_filename
            _add(configured)
    except Exception:
        pass

    newest_norm = newest_provider_info_norm_path()
    if newest_norm is not None:
        _add(newest_norm)

    # Slim fallbacks only (blank-fill). Do not scan older Norm months or historical dump.
    for path in (
        _REPO / "provider_info_combined_latest.csv",
        _REPO / "provider_info_norm.csv",
    ):
        _add(path)

    return ordered


def provider_info_crosswalk_paths() -> list[Path]:
    """
    Provider files for ownership CCN / legal-name crosswalks.

    Prefer newest Norm over combined_latest (Norm is canonical for July release).
    """
    return ownership_provider_info_paths()


def _provider_info_col_map(header: list[str]) -> dict[str, str | None]:
    return {
        "ccn": next((c for c in header if c.lower() in ("ccn", "provnum")), None),
        "state": next((c for c in header if c.lower() == "state"), None),
        "county": next((c for c in header if c.lower() == "county"), None),
        "city": next((c for c in header if c.lower() == "city"), None),
        "beds": next((c for c in header if "certified" in c.lower() and "bed" in c.lower()), None),
        "census": next((c for c in header if "avg_residents" in c.lower()), None),
        "hprd": next(
            (c for c in header if c in ("reported_total_nurse_hrs_per_resident_per_day", "Total_Nurse_HPRD")),
            None,
        ),
        "overall": next((c for c in header if c.lower() == "overall_rating"), None),
        "staffing": next((c for c in header if c.lower() == "staffing_rating"), None),
        "health_inspection": next(
            (
                c
                for c in header
                if c.lower()
                in (
                    "health_inspection_rating",
                    "health_inspection",
                    "health inspection rating",
                )
            ),
            None,
        ),
        "qm": next((c for c in header if c.lower() == "qm_rating"), None),
        "sff": next(
            (
                c
                for c in header
                if c.lower() in ("sff_status", "special_focus_status")
                or "special focus" in c.lower()
            ),
            None,
        ),
        "abuse": next(
            (c for c in header if c.lower() in ("abuse_icon", "has_abuse_icon")),
            None,
        ),
        "provider_name": next(
            (c for c in header if c.lower() in ("provider_name", "provider name")),
            None,
        ),
        "provider_address": next(
            (c for c in header if c.lower() in ("provider_address", "provider address")),
            None,
        ),
        "zip_code": next(
            (c for c in header if c.lower() in ("zip_code", "zip", "zipcode")),
            None,
        ),
        "latitude": next((c for c in header if c.lower() == "latitude"), None),
        "longitude": next((c for c in header if c.lower() == "longitude"), None),
        "processing_date": next(
            (c for c in header if c.lower() in ("processing_date", "processing date")),
            None,
        ),
        "quarter": next((c for c in header if c.lower() == "quarter"), None),
    }


def _provider_info_row_dict(row: pd.Series, col_map: dict[str, str | None]) -> dict[str, str]:
    def _cell(key: str) -> str:
        col = col_map.get(key)
        if not col:
            return ""
        val = row.get(col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        s = str(val).strip()
        if s.lower() in ("nan", "none"):
            return ""
        return s

    state = _cell("state").upper()[:2]
    return {
        "state": state,
        "county": _cell("county"),
        "city": _cell("city"),
        "beds": _cell("beds"),
        "census": _cell("census"),
        "hprd": _cell("hprd"),
        "overall_rating": _cell("overall"),
        "staffing_rating": _cell("staffing"),
        "health_inspection_rating": _cell("health_inspection"),
        "qm_rating": _cell("qm"),
        "sff": _cell("sff"),
        "sff_status": _cell("sff"),
        "abuse_icon": _cell("abuse"),
        "provider_name": _cell("provider_name"),
        "provider_address": _cell("provider_address"),
        "zip_code": _cell("zip_code"),
        "latitude": _cell("latitude"),
        "longitude": _cell("longitude"),
        "processing_date": _cell("processing_date"),
        "quarter": _cell("quarter"),
    }


def _merge_provider_lookup_row(
    primary: dict[str, str], secondary: dict[str, str]
) -> dict[str, str]:
    """
    Prefer primary (newer) values; fill only blank keys from secondary (older).

    Prevents an older combined snapshot from overwriting newer Norm fields.
    """
    merged = dict(primary)
    for key, val in secondary.items():
        if val and not merged.get(key):
            merged[key] = val
    return merged


def _provider_info_rows_from_path(
    path: Path,
    *,
    needed_ccns: frozenset[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Load provider-info rows keyed by CCN.

    Optional ``needed_ccns`` keeps only those CCNs (still streams the full CSV once).
    Uses vectorized parse — avoids per-row ``DataFrame.iterrows`` on the hot path.
    """
    header = pd.read_csv(path, nrows=0).columns.tolist()
    col_map = _provider_info_col_map(header)
    usecols_tuple: tuple[str, ...] = tuple(c for c in col_map.values() if c)
    ccn_col = col_map.get("ccn")
    if not ccn_col:
        return {}

    qcol = "CY_Qtr" if "CY_Qtr" in header else ("quarter" if "quarter" in header else None)
    read_cols: list[str] = list(usecols_tuple)
    if qcol and qcol not in read_cols:
        read_cols.append(qcol)

    df = pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
        encoding="latin-1",
        usecols=read_cols,
    )
    if df.empty:
        return {}

    ccn_raw = df[ccn_col].fillna("").astype(str).str.strip().str.split(".").str[0]
    mask = ccn_raw.str.isdigit()
    if not bool(mask.any()):
        return {}
    df = df.loc[mask].copy()
    df["_ccn"] = ccn_raw.loc[mask].str.zfill(6).str[-6:]
    if needed_ccns is not None:
        df = df[df["_ccn"].isin(needed_ccns)]
        if df.empty:
            return {}
    if qcol and qcol in df.columns:
        df = df.sort_values(qcol).groupby("_ccn", as_index=False).last()

    def _cell(rec: dict[str, Any], key: str) -> str:
        col = col_map.get(key)
        if not col:
            return ""
        val = rec.get(col)
        if val is None:
            return ""
        s = str(val).strip()
        if s.lower() in ("nan", "none"):
            return ""
        return s

    out: dict[str, dict[str, str]] = {}
    for rec in df.to_dict("records"):
        ccn = str(rec.get("_ccn") or "")
        if not ccn:
            continue
        state = _cell(rec, "state").upper()[:2]
        parsed = {
            "state": state,
            "county": _cell(rec, "county"),
            "city": _cell(rec, "city"),
            "beds": _cell(rec, "beds"),
            "census": _cell(rec, "census"),
            "hprd": _cell(rec, "hprd"),
            "overall_rating": _cell(rec, "overall"),
            "staffing_rating": _cell(rec, "staffing"),
            "health_inspection_rating": _cell(rec, "health_inspection"),
            "qm_rating": _cell(rec, "qm"),
            "sff": _cell(rec, "sff"),
            "sff_status": _cell(rec, "sff"),
            "abuse_icon": _cell(rec, "abuse"),
            "provider_name": _cell(rec, "provider_name"),
            "provider_address": _cell(rec, "provider_address"),
            "zip_code": _cell(rec, "zip_code"),
            "latitude": _cell(rec, "latitude"),
            "longitude": _cell(rec, "longitude"),
            "processing_date": _cell(rec, "processing_date"),
            "quarter": _cell(rec, "quarter"),
        }
        if ccn in out:
            out[ccn] = _merge_provider_lookup_row(out[ccn], parsed)
        else:
            out[ccn] = parsed
    return out


@lru_cache(maxsize=1)
def _canonical_metric_period() -> tuple:
    """
    Metric period bounds from the canonical Norm snapshot (quarter / processing_date).

    Returns (metric_start, metric_end, quarter_label, source_filename) or Nones.
    """
    from ownership.relationship_period import parse_pbj_quarter_bounds, parse_association_start

    paths = ownership_provider_info_paths()
    if not paths:
        return (None, None, "", "")
    canonical = paths[0]
    # Prefer policy pbj_period when present.
    quarter_label = ""
    try:
        from ownership.ownership_release_policy import (
            active_release_date,
            load_policy,
            resolve_release_entry,
        )

        entry = resolve_release_entry(load_policy(_REPO), active_release_date(load_policy(_REPO)))
        quarter_label = entry.pbj_period or ""
    except Exception:
        quarter_label = ""

    bounds = parse_pbj_quarter_bounds(quarter_label) if quarter_label else None
    if bounds is None:
        # Sample quarter from the canonical file.
        try:
            header = pd.read_csv(canonical, nrows=0).columns.tolist()
            qcol = next((c for c in header if c.lower() == "quarter"), None)
            pcol = next(
                (c for c in header if c.lower() in ("processing_date", "processing date")),
                None,
            )
            usecols = [c for c in (qcol, pcol) if c]
            if usecols:
                sample = pd.read_csv(
                    canonical, usecols=usecols, dtype=str, nrows=200, encoding="latin-1"
                )
                if qcol:
                    for raw in sample[qcol].dropna().astype(str):
                        bounds = parse_pbj_quarter_bounds(raw)
                        if bounds:
                            quarter_label = str(raw).strip()
                            break
                if bounds is None and pcol:
                    dates = []
                    for raw in sample[pcol].dropna().astype(str):
                        d = parse_association_start(raw)
                        if d:
                            dates.append(d)
                    if dates:
                        # processing_date alone is release stamp; treat as single-day uncertain end.
                        end = max(dates)
                        bounds = (end, end)
        except Exception:
            bounds = None
    if not bounds:
        return (None, None, quarter_label, canonical.name)
    return (bounds[0], bounds[1], quarter_label, canonical.name)


@lru_cache(maxsize=1)
def _ccn_provider_lookup() -> dict[str, dict[str, str]]:
    """
    Provider-info row per CCN for ownership portfolio enrichment.

    Uses ``ownership_provider_info_paths()`` (newest Norm first). Paths are
    newest→oldest; older files only fill blanks. Historical
    ``provider_info_combined.csv`` is never scanned on this hot path.
    """
    paths = ownership_provider_info_paths()
    if not paths:
        return {}

    merged: dict[str, dict[str, str]] = {}
    loaded_sizes: set[int] = set()
    # Newest first: establish Norm values, then fill blanks from older slim sources.
    for path in paths:
        try:
            size = int(path.stat().st_size)
        except OSError:
            size = -1
        # Skip byte-identical copies of an already-loaded snapshot (same size).
        if size > 0 and size in loaded_sizes and merged:
            continue
        for ccn, row in _provider_info_rows_from_path(path).items():
            if ccn in merged:
                merged[ccn] = _merge_provider_lookup_row(merged[ccn], row)
            else:
                merged[ccn] = row
        if size > 0:
            loaded_sizes.add(size)
    return merged


def enrich_facility_row(fac: dict[str, Any]) -> dict[str, Any]:
    """Add provider info when CCN is known; PBJ metrics for verified matches."""
    lookup = _ccn_provider_lookup()
    out = dict(fac)
    ccn = str(out.get("ccn") or "").strip().zfill(6)[-6:]
    method = str(out.get("ccn_match_method") or "").strip()
    pi = lookup.get(ccn) or {}
    if pi.get("provider_name"):
        out["provider_name"] = pi["provider_name"]
    if ccn and pi:
        for k in ("provider_address", "zip_code", "city", "latitude", "longitude"):
            if pi.get(k) and not out.get(k):
                out[k] = pi[k]
    if method in ("legal_exact", "enrollment_exact") and ccn and pi:
        if not out.get("state") and pi.get("state"):
            out["state"] = pi["state"]
        if not out.get("city") and pi.get("city"):
            out["city"] = pi["city"]
        if pi.get("county"):
            out["county"] = pi["county"]
        for k in (
            "beds",
            "census",
            "hprd",
            "overall_rating",
            "staffing_rating",
            "health_inspection_rating",
            "qm_rating",
            "sff",
            "sff_status",
            "abuse_icon",
        ):
            if pi.get(k):
                out[k] = pi[k]
        if pi.get("sff_status") and not out.get("sff"):
            out["sff"] = pi["sff_status"]
        out["has_abuse"] = _parse_abuse_flag(pi.get("abuse_icon"))
        out["pbj_matched"] = True
        if pi.get("quarter"):
            out.setdefault("metric_quarter", pi["quarter"])
        if pi.get("processing_date"):
            out.setdefault("metric_processing_date", pi["processing_date"])
    elif method in ("name_exact", "fuzzy") and ccn:
        out["pbj_suggested"] = True

    # Portfolio HPRD: timing-only linked-facility inclusion vs PBJ quarter.
    # Care Compare stars remain facility context only (not period performance).
    from ownership.relationship_period import (
        portfolio_inclusion_status_for_facility,
        rating_metric_context_status,
        parse_pbj_quarter_bounds,
    )

    q_label = str(out.get("metric_quarter") or "").strip()
    bounds = parse_pbj_quarter_bounds(q_label) if q_label else None
    if bounds is None:
        metric_start, metric_end, q_label, _src = _canonical_metric_period()
    else:
        metric_start, metric_end = bounds
    out["pbj_metric_quarter"] = q_label
    out["hprd_portfolio_inclusion_status"] = portfolio_inclusion_status_for_facility(
        out,
        metric_start=metric_start,
        metric_end=metric_end,
        metric_kind="pbj_hprd",
    )
    # Ratings are facility-context only — not ownership/period attribution.
    out["rating_metric_context_status"] = rating_metric_context_status(
        metric_kind="overall_rating"
    )
    return out


def enrich_facilities(facilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich all facility rows using one process-cached CCN→provider bulk lookup."""
    if not facilities:
        return []
    # Ensure process-wide lookup is warm; row enrichment is O(n) dict gets.
    _ccn_provider_lookup()
    return [enrich_facility_row(f) for f in facilities]


def _cell_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return None
    return s


def entity_facility_for_portfolio(
    fac: dict[str, Any], provider_info: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Map entity roster row + preloaded provider_info to portfolio rollup shape."""
    ccn = str(fac.get("ccn") or "").strip().zfill(6)[-6:]
    pi = provider_info.get(ccn) or {}
    row: dict[str, Any] = {
        "ccn": ccn,
        "state": str(fac.get("state") or pi.get("state") or "").strip().upper()[:2],
        "county": str(pi.get("county") or "").strip(),
        "pbj_matched": bool(ccn),
    }
    census = _cell_str(pi.get("avg_residents_per_day")) or _cell_str(
        fac.get("avg_daily_census")
    )
    if census:
        row["census"] = census
    beds = _cell_str(pi.get("certified_beds")) or _cell_str(pi.get("beds"))
    if beds:
        row["beds"] = beds
    tn = fac.get("Total_Nurse_HPRD")
    hprd = None
    if tn is not None and not (isinstance(tn, float) and pd.isna(tn)):
        hprd = _cell_str(tn)
    if not hprd:
        hprd = _cell_str(
            pi.get("reported_total_nurse_hrs_per_resident_per_day")
        ) or _cell_str(pi.get("Total_Nurse_HPRD"))
    if hprd:
        row["hprd"] = hprd
    for dst, src in (
        ("overall_rating", "overall_rating"),
        ("staffing_rating", "staffing_rating"),
        ("health_inspection_rating", "health_inspection_rating"),
        ("qm_rating", "qm_rating"),
    ):
        v = _cell_str(pi.get(src))
        if v:
            row[dst] = v
    sff = _cell_str(pi.get("sff_status")) or _cell_str(pi.get("sff"))
    if sff:
        row["sff"] = sff
        row["sff_status"] = sff
    row["has_abuse"] = _parse_abuse_flag(
        pi.get("abuse_icon") or pi.get("has_abuse_icon")
    )
    return row


def build_entity_portfolio_summary(
    facilities: list[dict[str, Any]],
    provider_info: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Portfolio rollup for /entity/<id> using roster CCNs + scoped provider_info (no CSV re-scan)."""
    if not facilities:
        return {}
    rows = [entity_facility_for_portfolio(f, provider_info) for f in facilities]
    # Entity pages are facility-roster context (not PAC relationship timing).
    for row in rows:
        if row.get("pbj_matched") and not str(
            row.get("hprd_portfolio_inclusion_status") or ""
        ).strip():
            row["hprd_portfolio_inclusion_status"] = "supported"
    return _rollup_portfolio_metrics(rows, context="entity")


def _rollup_portfolio_metrics(
    enriched: list[dict[str, Any]],
    *,
    context: str = "owner",
) -> dict[str, Any]:
    """Shared portfolio means, star buckets, and state counts."""
    if not enriched:
        return {}

    n = len(enriched)
    states = sorted({str(f.get("state") or "").upper() for f in enriched if f.get("state")})
    counties = sorted({str(f.get("county") or "") for f in enriched if f.get("county")})

    hprd_unweighted: list[float] = []
    hprd_weighted: list[tuple[float, float]] = []
    overall_unweighted: list[float] = []
    overall_weighted: list[tuple[float, float]] = []
    staffing_unweighted: list[float] = []
    staffing_weighted: list[tuple[float, float]] = []
    overall_star_counts: dict[int, int] = {i: 0 for i in range(1, 6)}
    staffing_star_counts: dict[int, int] = {i: 0 for i in range(1, 6)}
    beds_total = 0.0
    census_total = 0.0
    sff_count = 0
    low_staff = 0
    pbj_matched = 0
    pbj_suggested = 0
    n_missing_hprd = 0
    n_missing_overall_rating = 0
    n_hprd_outlier_excluded = 0
    n_rating_outlier_excluded = 0
    n_missing_resident_weight = 0
    n_timing_excluded = 0
    n_timing_uncertain = 0
    n_hprd_le_zero_excluded = 0
    n_hprd_gt_12_excluded = 0
    n_hprd_weight_excluded = 0
    n_obsolete_below_1_5_included = 0
    hprd_weight_sum = 0.0
    hprd_numerator = 0.0
    terminal_bucket_counts = {k: 0 for k in PORTFOLIO_HPRD_TERMINAL_BUCKETS}
    for f in enriched:
        if f.get("pbj_matched"):
            pbj_matched += 1
        elif f.get("pbj_suggested"):
            pbj_suggested += 1
        b = _parse_float(f.get("beds"))
        if b:
            beds_total += b
        c = _parse_float(f.get("census"))
        if c:
            census_total += c
        sff = str(f.get("sff") or "").upper()
        if "SFF" in sff and "CANDIDATE" not in sff:
            sff_count += 1
        sr = _parse_float(f.get("staffing_rating"))
        if sr is not None and sr <= 2:
            low_staff += 1

        # Mutually exclusive Portfolio HPRD terminal classification (every CCN once).
        bucket = classify_portfolio_hprd_terminal_bucket(f)
        terminal_bucket_counts[bucket] = terminal_bucket_counts.get(bucket, 0) + 1

        if bucket == "timing_excluded_or_uncertain":
            status = str(f.get("hprd_portfolio_inclusion_status") or "").strip()
            if status == "exclude":
                n_timing_excluded += 1
            else:
                n_timing_uncertain += 1
            if f.get("pbj_matched") and _parse_float(f.get("hprd")) is None:
                n_missing_hprd += 1
        elif bucket == "pbj_match_excluded":
            pass
        elif bucket == "missing_hprd":
            n_missing_hprd += 1
            n_hprd_weight_excluded += 1
        elif bucket == "hprd_le_zero":
            n_hprd_le_zero_excluded += 1
            n_hprd_outlier_excluded += 1
            n_hprd_weight_excluded += 1
        elif bucket == "hprd_gt_12":
            n_hprd_gt_12_excluded += 1
            n_hprd_outlier_excluded += 1
            n_hprd_weight_excluded += 1
        elif bucket == "missing_invalid_weight":
            n_missing_resident_weight += 1
            n_hprd_weight_excluded += 1
        elif bucket == "included":
            h = _parse_float(f.get("hprd"))
            weight = _portfolio_metric_weight(f)
            assert h is not None and weight is not None
            hprd_unweighted.append(h)
            hprd_weighted.append((h, weight))
            hprd_numerator += h * weight
            hprd_weight_sum += weight
            if 0.0 < h < 1.5:
                n_obsolete_below_1_5_included += 1

        if not f.get("pbj_matched"):
            # Ratings / distributions only for PBJ-matched facilities.
            continue

        # Ratings: facility-context distributions only (not period means).
        ovr = _parse_float(f.get("overall_rating"))
        if ovr is None:
            n_missing_overall_rating += 1
        elif not is_plausible_overall_rating(ovr):
            n_rating_outlier_excluded += 1
        else:
            star_bucket = int(round(ovr))
            if 1 <= star_bucket <= 5:
                overall_star_counts[star_bucket] = overall_star_counts.get(star_bucket, 0) + 1
            if context == "entity":
                overall_unweighted.append(ovr)
                weight = _portfolio_metric_weight(f)
                if weight is not None:
                    overall_weighted.append((ovr, weight))

        stf = _parse_float(f.get("staffing_rating"))
        if stf is not None and is_plausible_overall_rating(stf):
            stf_bucket = int(round(stf))
            if 1 <= stf_bucket <= 5:
                staffing_star_counts[stf_bucket] = staffing_star_counts.get(stf_bucket, 0) + 1
            if context == "entity":
                staffing_unweighted.append(stf)
                weight = _portfolio_metric_weight(f)
                if weight is not None:
                    staffing_weighted.append((stf, weight))

    wmean_hprd = None
    umean_hprd = None
    if hprd_weighted and hprd_weight_sum > 0:
        wmean_hprd = hprd_numerator / hprd_weight_sum
    if hprd_unweighted:
        umean_hprd = sum(hprd_unweighted) / len(hprd_unweighted)

    by_state: dict[str, int] = {}
    for f in enriched:
        st = str(f.get("state") or "").strip().upper()
        if st:
            by_state[st] = by_state.get(st, 0) + 1

    mean_overall = None
    umean_overall = None
    if overall_weighted:
        tw = sum(w for _, w in overall_weighted)
        if tw > 0:
            mean_overall = round(sum(o * w for o, w in overall_weighted) / tw, 2)
    if overall_unweighted:
        umean_overall = round(sum(overall_unweighted) / len(overall_unweighted), 2)

    mean_staffing = None
    umean_staffing = None
    if staffing_weighted:
        tw = sum(w for _, w in staffing_weighted)
        if tw > 0:
            mean_staffing = round(sum(s * w for s, w in staffing_weighted) / tw, 2)
    if staffing_unweighted:
        umean_staffing = round(sum(staffing_unweighted) / len(staffing_unweighted), 2)

    pct_low_staffing = None
    if pbj_matched > 0 and low_staff > 0:
        pct_low_staffing = int(round(100.0 * low_staff / pbj_matched))

    return {
        "n_facilities": n,
        "n_pbj_matched": pbj_matched,
        "n_pbj_suggested": pbj_suggested,
        "n_states": len(states),
        "states": states,
        "n_counties": len(counties),
        "beds_total": int(beds_total) if beds_total else None,
        "census_total": int(census_total) if census_total else None,
        "wmean_hprd": round(wmean_hprd, 3) if wmean_hprd is not None else None,
        "umean_hprd": round(umean_hprd, 3) if umean_hprd is not None else None,
        "mean_overall_rating": mean_overall,
        "umean_overall_rating": umean_overall,
        "n_missing_hprd": n_missing_hprd,
        "n_missing_overall_rating": n_missing_overall_rating,
        "n_hprd_outlier_excluded": n_hprd_outlier_excluded,
        "n_hprd_le_zero_excluded": n_hprd_le_zero_excluded,
        "n_hprd_gt_12_excluded": n_hprd_gt_12_excluded,
        "n_rating_outlier_excluded": n_rating_outlier_excluded,
        "n_missing_resident_weight": n_missing_resident_weight,
        "n_timing_excluded": n_timing_excluded,
        "n_timing_uncertain": n_timing_uncertain,
        "n_timing_excluded_or_uncertain": n_timing_excluded + n_timing_uncertain,
        "n_hprd_weight_excluded": n_hprd_weight_excluded,
        "n_obsolete_below_1_5_included": n_obsolete_below_1_5_included,
        "hprd_terminal_buckets": terminal_bucket_counts,
        "hprd_numerator": round(hprd_numerator, 6) if hprd_weighted else None,
        "hprd_weight_denominator": round(hprd_weight_sum, 6) if hprd_weighted else None,
        "sff_count": sff_count,
        "low_staffing_rating_count": low_staff,
        "pct_low_staffing_rating": pct_low_staffing,
        # Owner pages omit Care Compare means as period performance.
        # Entity pages keep facility-roster means (still facility context).
        "mean_overall_rating": mean_overall if context == "entity" else None,
        "umean_overall_rating": umean_overall if context == "entity" else None,
        "mean_staffing_rating": mean_staffing if context == "entity" else None,
        "umean_staffing_rating": umean_staffing if context == "entity" else None,
        "ratings_metric_scope": "facility_context_only",
        "hprd_metric_scope": (
            "entity_facility_roster"
            if context == "entity"
            else "portfolio_linked_facility_timing"
        ),
        # n = CCNs contributing to the weighted mean (require weight + usable HPRD).
        "n_hprd_supported_facilities": len(hprd_weighted),
        "n_hprd_portfolio_facilities": len(hprd_weighted),
        "hprd_eligible_label": (
            f"Portfolio HPRD across {len(hprd_weighted)} facilit"
            f"{'y' if len(hprd_weighted) == 1 else 'ies'}"
            + (
                " on this entity roster"
                if context == "entity"
                else " with a CMS relationship in place by the PBJ quarter start"
            )
            if hprd_weighted
            else (
                "No PBJ HPRD values on this entity roster"
                if context == "entity"
                else "No linked facilities with quarter-active timing and usable PBJ HPRD"
            )
        ),
        "overall_star_counts": overall_star_counts,
        "staffing_star_counts": staffing_star_counts,
        "n_with_overall_for_dist": sum(overall_star_counts.values()),
        "n_with_staffing_for_dist": sum(staffing_star_counts.values()),
        "by_state": sorted(by_state.items(), key=lambda x: (-x[1], x[0])),
    }


def build_portfolio_summary(facilities: list[dict[str, Any]]) -> dict[str, Any]:
    """Portfolio rollup for owner/control facility list (PBJapp-style headline metrics)."""
    if not facilities:
        return {}
    return _rollup_portfolio_metrics(enrich_facilities(facilities))


def summarize_control_parties(control_parties: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(control_parties)
    orgs = [p for p in control_parties if (p.get("party_type") or "").lower().startswith("org")]
    inds = [p for p in control_parties if p not in orgs]
    return {
        "total": n,
        "organizations": len(orgs),
        "individuals": len(inds),
    }


def sort_control_parties_for_display(parties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ownership.role_classification import sort_control_parties

    return sort_control_parties(parties)
