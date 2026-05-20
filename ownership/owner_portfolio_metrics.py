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


@lru_cache(maxsize=1)
def _ccn_provider_lookup() -> dict[str, dict[str, str]]:
    """Latest provider-info row per CCN (state, county, city, beds, HPRD, ratings)."""
    path = next((p for p in _provider_info_csv_paths() if p.is_file()), None)
    if not path:
        return {}

    header = pd.read_csv(path, nrows=0).columns.tolist()
    col_map = {
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
    }
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
            out[ccn] = {
                "state": str(row.get(col_map["state"]) or "").strip().upper()[:2] if col_map["state"] else "",
                "county": str(row.get(col_map["county"]) or "").strip() if col_map["county"] else "",
                "city": str(row.get(col_map["city"]) or "").strip() if col_map["city"] else "",
                "beds": str(row.get(col_map["beds"]) or "").strip() if col_map["beds"] else "",
                "census": str(row.get(col_map["census"]) or "").strip() if col_map["census"] else "",
                "hprd": str(row.get(col_map["hprd"]) or "").strip() if col_map["hprd"] else "",
                "overall_rating": str(row.get(col_map["overall"]) or "").strip() if col_map["overall"] else "",
                "staffing_rating": str(row.get(col_map["staffing"]) or "").strip() if col_map["staffing"] else "",
                "qm_rating": str(row.get(col_map["qm"]) or "").strip() if col_map["qm"] else "",
                "sff": str(row.get(col_map["sff"]) or "").strip() if col_map["sff"] else "",
                "sff_status": str(row.get(col_map["sff"]) or "").strip() if col_map["sff"] else "",
                "abuse_icon": str(row.get(col_map["abuse"]) or "").strip() if col_map["abuse"] else "",
                "provider_name": str(row.get(col_map["provider_name"]) or "").strip()
                if col_map["provider_name"]
                else "",
            }
    return out


def enrich_facility_row(fac: dict[str, Any]) -> dict[str, Any]:
    """Add provider info when CCN is known; PBJ metrics only for legal_exact matches."""
    lookup = _ccn_provider_lookup()
    out = dict(fac)
    ccn = str(out.get("ccn") or "").strip().zfill(6)[-6:]
    method = str(out.get("ccn_match_method") or "").strip()
    pi = lookup.get(ccn) or {}
    if pi.get("provider_name"):
        out["provider_name"] = pi["provider_name"]
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

    hprd_vals: list[tuple[float, float]] = []
    overall_vals: list[tuple[float, float]] = []
    beds_total = 0.0
    census_total = 0.0
    sff_count = 0
    low_staff = 0
    pbj_matched = 0
    pbj_suggested = 0
    for f in enriched:
        if f.get("pbj_matched"):
            pbj_matched += 1
        elif f.get("pbj_suggested"):
            pbj_suggested += 1
        h = _parse_float(f.get("hprd"))
        census = _parse_float(f.get("census")) or _parse_float(f.get("beds")) or 1.0
        if h is not None:
            hprd_vals.append((h, census))
        ovr = _parse_float(f.get("overall_rating"))
        if ovr is not None:
            w = _parse_float(f.get("census")) or _parse_float(f.get("beds")) or 1.0
            overall_vals.append((ovr, w))
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

    wmean_hprd = None
    umean_hprd = None
    if hprd_vals:
        tw = sum(w for _, w in hprd_vals)
        if tw > 0:
            wmean_hprd = sum(h * w for h, w in hprd_vals) / tw
        umean_hprd = sum(h for h, _ in hprd_vals) / len(hprd_vals)

    by_state: dict[str, int] = {}
    for f in enriched:
        st = str(f.get("state") or "").strip().upper()
        if st:
            by_state[st] = by_state.get(st, 0) + 1

    mean_overall = None
    umean_overall = None
    if overall_vals:
        tw = sum(w for _, w in overall_vals)
        if tw > 0:
            mean_overall = round(sum(o * w for o, w in overall_vals) / tw, 2)
        umean_overall = round(sum(o for o, _ in overall_vals) / len(overall_vals), 2)

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
        "sff_count": sff_count,
        "low_staffing_rating_count": low_staff,
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
