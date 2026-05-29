"""
Portfolio-level metrics for /owners/<pac> owner/control profiles.

Lightweight analogue to PBJapp ownership/build_owner_facility_metrics.py summaries,
using provider_info_combined.csv + search_index (no full ETL required).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator
from typing import Any, cast

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent

# CMS PBJ quarterly aberrant-staffing limits (facility-quarter aggregate). See
# PBJPedia methodology / ownership/PORTFOLIO_METRICS.md.
PORTFOLIO_HPRD_MIN = 1.5
PORTFOLIO_HPRD_MAX = 12.0
PORTFOLIO_OVERALL_RATING_MIN = 1.0
PORTFOLIO_OVERALL_RATING_MAX = 5.0
# Min verified facilities with star ratings before portfolio bar charts render.
PORTFOLIO_STAR_DIST_MIN = 5

PORTFOLIO_METHODOLOGY_SUMMARY = (
    "Portfolio means use only PBJ-verified facilities (CMS enrollment legal name matches "
    "provider-info legal name). Missing HPRD or star ratings are omitted from means but the "
    "facility remains in the table. Weighted means use average daily census when published, "
    "otherwise certified beds; facilities with neither are included in the simple facility "
    "average only, not the census-weighted mean. Total nurse HPRD values below "
    f"{PORTFOLIO_HPRD_MIN:g} or above {PORTFOLIO_HPRD_MAX:g} HPRD are excluded as implausible "
    "(aligned with CMS PBJ public-use quarterly exclusion rules). Overall star ratings outside "
    f"{PORTFOLIO_OVERALL_RATING_MIN:g}–{PORTFOLIO_OVERALL_RATING_MAX:g} are excluded."
)


def is_plausible_portfolio_hprd(hprd: float) -> bool:
    """True when HPRD is in the CMS PBJ quarterly plausible range for total nurse staffing."""
    return PORTFOLIO_HPRD_MIN <= hprd <= PORTFOLIO_HPRD_MAX


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
            _REPO / "provider_info_combined.csv",
        ]
    )
    return paths


def provider_info_crosswalk_paths() -> list[Path]:
    """
    Provider files for ownership CCN / legal-name crosswalks.

    Combined snapshots are first: monthly ProviderInfoNorm exports (e.g. from PBJapp)
    may omit legal_business_name even when the column exists.
    """
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in _provider_info_csv_paths():
        if "combined" in path.name.lower() and path.is_file() and path not in seen:
            ordered.append(path)
            seen.add(path)
    for path in _provider_info_csv_paths():
        if path.is_file() and path not in seen:
            ordered.append(path)
            seen.add(path)
    return ordered


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
    }


def _merge_provider_lookup_row(
    base: dict[str, str], incoming: dict[str, str]
) -> dict[str, str]:
    """Merge two provider-info rows; non-empty incoming values win."""
    merged = dict(base)
    for key, val in incoming.items():
        if val:
            merged[key] = val
    return merged


def _provider_info_rows_from_path(path: Path) -> dict[str, dict[str, str]]:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    col_map = _provider_info_col_map(header)
    usecols_tuple: tuple[str, ...] = tuple(c for c in col_map.values() if c)
    if not col_map["ccn"]:
        return {}

    out: dict[str, dict[str, str]] = {}
    qcol = "CY_Qtr" if "CY_Qtr" in header else ("quarter" if "quarter" in header else None)
    read_cols: tuple[str, ...] = usecols_tuple
    if qcol and qcol not in read_cols:
        read_cols = read_cols + (qcol,)

    csv_kwargs: dict[str, Any] = {
        "filepath_or_buffer": path,
        "dtype": str,
        "chunksize": 100_000,
        "low_memory": False,
        "encoding": "latin-1",
        "usecols": read_cols,
    }
    for chunk in cast(Iterator[pd.DataFrame], pd.read_csv(**csv_kwargs)):
        if qcol and qcol in chunk.columns:
            chunk = chunk.sort_values(qcol).groupby(col_map["ccn"], as_index=False).last()
        for _, row in chunk.iterrows():
            raw_ccn = str(row.get(col_map["ccn"]) or "").strip()
            if "." in raw_ccn:
                raw_ccn = raw_ccn.split(".")[0]
            ccn = raw_ccn.zfill(6)[-6:] if raw_ccn.isdigit() else ""
            if not ccn:
                continue
            parsed = _provider_info_row_dict(row, col_map)
            if ccn in out:
                out[ccn] = _merge_provider_lookup_row(out[ccn], parsed)
            else:
                out[ccn] = parsed
    return out


@lru_cache(maxsize=1)
def _ccn_provider_lookup() -> dict[str, dict[str, str]]:
    """
    Provider-info row per CCN merged across snapshots.

    Monthly ProviderInfoNorm exports are read last (fresh names/ratings) but may omit
    mailing address; older combined snapshots backfill street/zip when newer rows are blank.
    Verified from: ProviderInfoNorm_2026_05.csv vs provider_info_combined_latest.csv (CCN 365394).
    """
    paths = [p for p in _provider_info_csv_paths() if p.is_file()]
    if not paths:
        return {}

    merged: dict[str, dict[str, str]] = {}
    for path in reversed(paths):
        for ccn, row in _provider_info_rows_from_path(path).items():
            if ccn in merged:
                merged[ccn] = _merge_provider_lookup_row(merged[ccn], row)
            else:
                merged[ccn] = row
    return merged


def enrich_facility_row(fac: dict[str, Any]) -> dict[str, Any]:
    """Add provider info when CCN is known; PBJ metrics only for legal_exact matches."""
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
    if method == "legal_exact" and ccn and pi:
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
    elif method in ("name_exact", "fuzzy") and ccn:
        out["pbj_suggested"] = True
    return out


def enrich_facilities(facilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_facility_row(f) for f in facilities]


def build_portfolio_summary(facilities: list[dict[str, Any]]) -> dict[str, Any]:
    """Portfolio rollup for owner/control facility list (PBJapp-style headline metrics)."""
    if not facilities:
        return {}

    enriched = enrich_facilities(facilities)
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

        if not f.get("pbj_matched"):
            continue

        weight = _portfolio_metric_weight(f)
        if weight is None:
            n_missing_resident_weight += 1

        h = _parse_float(f.get("hprd"))
        if h is None:
            n_missing_hprd += 1
        elif not is_plausible_portfolio_hprd(h):
            n_hprd_outlier_excluded += 1
        else:
            hprd_unweighted.append(h)
            if weight is not None:
                hprd_weighted.append((h, weight))

        ovr = _parse_float(f.get("overall_rating"))
        if ovr is None:
            n_missing_overall_rating += 1
        elif not is_plausible_overall_rating(ovr):
            n_rating_outlier_excluded += 1
        else:
            overall_unweighted.append(ovr)
            if weight is not None:
                overall_weighted.append((ovr, weight))
            star_bucket = int(round(ovr))
            if 1 <= star_bucket <= 5:
                overall_star_counts[star_bucket] = overall_star_counts.get(star_bucket, 0) + 1

        stf = _parse_float(f.get("staffing_rating"))
        if stf is not None and is_plausible_overall_rating(stf):
            staffing_unweighted.append(stf)
            if weight is not None:
                staffing_weighted.append((stf, weight))
            stf_bucket = int(round(stf))
            if 1 <= stf_bucket <= 5:
                staffing_star_counts[stf_bucket] = staffing_star_counts.get(stf_bucket, 0) + 1

    wmean_hprd = None
    umean_hprd = None
    if hprd_weighted:
        tw = sum(w for _, w in hprd_weighted)
        if tw > 0:
            wmean_hprd = sum(h * w for h, w in hprd_weighted) / tw
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
        "n_rating_outlier_excluded": n_rating_outlier_excluded,
        "n_missing_resident_weight": n_missing_resident_weight,
        "sff_count": sff_count,
        "low_staffing_rating_count": low_staff,
        "pct_low_staffing_rating": pct_low_staffing,
        "mean_staffing_rating": mean_staffing,
        "umean_staffing_rating": umean_staffing,
        "overall_star_counts": overall_star_counts,
        "staffing_star_counts": staffing_star_counts,
        "n_with_overall_for_dist": sum(overall_star_counts.values()),
        "n_with_staffing_for_dist": sum(staffing_star_counts.values()),
        "by_state": sorted(by_state.items(), key=lambda x: (-x[1], x[0])),
    }


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
    def key(p: dict[str, Any]) -> tuple:
        is_org = 0 if (p.get("party_type") or "").lower().startswith("org") else 1
        pct = _parse_pct_max(p.get("pcts") or []) or -1
        return (is_org, -pct, p.get("name") or "")

    return sorted(parties, key=key)
