"""Public facility query helpers for MCP / JSON (no HTML rendering)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESULT_DEFAULT = 20
RESULT_HARD_MAX = 60


def _load_search_index() -> dict[str, Any]:
    path = os.path.join(APP_ROOT, "search_index.json")
    if not os.path.isfile(path):
        return {"f": [], "e": [], "s": []}
    return json.loads(open(path, encoding="utf-8").read())


def _ccn_match_score(ccn: str, q: str) -> int:
    c = (ccn or "").lower()
    query = (q or "").strip().lower()
    if not c or not query:
        return 0
    if c == query:
        return 200
    if c.startswith(query):
        return 160
    if query.isdigit():
        return 0
    if query in c:
        return 40
    return 0


def _facility_base_score(row: dict, q: str) -> int:
    score = _ccn_match_score(str(row.get("c") or ""), q)
    ql = q.lower()
    if ql in str(row.get("n") or "").lower():
        score += 100
    if ql in str(row.get("y") or "").lower():
        score += 35
    if ql in str(row.get("s") or "").lower():
        score += 20
    return score


def _clamp_limit(limit: int | None) -> int:
    try:
        n = int(limit if limit is not None else RESULT_DEFAULT)
    except (TypeError, ValueError):
        n = RESULT_DEFAULT
    return max(1, min(n, RESULT_HARD_MAX))


def normalize_ccn_input(raw: str | None) -> str:
    from app import normalize_ccn

    return normalize_ccn(raw)


def search_facilities(
    *,
    query: str = "",
    ccn: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    owner_pac: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Search facilities using search_index.json ranking (mirrors public-search.js)."""
    from canonical_urls import get_facility_name_from_search_index, provider_url
    from ownership.owner_profile import normalize_associate_id

    lim = _clamp_limit(limit)
    data = _load_search_index()
    rows = data.get("f") or []

    ccn_q = normalize_ccn_input(ccn) if ccn else ""
    city_q = (city or "").strip().lower()
    state_q = (state or "").strip().upper()[:2]
    zip_q = (zip_code or "").strip()
    pac_q = normalize_associate_id(owner_pac or "")
    text_q = (query or "").strip()

    hits: list[tuple[int, dict]] = []
    for row in rows:
        if not row or not row.get("c"):
            continue
        prov = normalize_ccn_input(str(row.get("c")))
        if ccn_q and prov != ccn_q:
            continue
        if state_q and str(row.get("s") or "").upper()[:2] != state_q:
            continue
        if city_q and city_q not in str(row.get("y") or "").lower():
            continue
        if zip_q and zip_q not in str(row.get("h") or ""):
            continue
        base = _facility_base_score(row, text_q or ccn_q or pac_q)
        if text_q or ccn_q:
            if not base and not (ccn_q and prov == ccn_q):
                if not text_q:
                    continue
        elif city_q or state_q or zip_q:
            base = 1
        else:
            continue
        hits.append((base, row))

    hits.sort(key=lambda x: (-x[0], str(x[1].get("n") or "")))
    selected = hits[:lim]

    from app import get_canonical_latest_quarter

    quarter = get_canonical_latest_quarter()
    out_rows: list[dict[str, Any]] = []
    for _, row in selected:
        prov = normalize_ccn_input(str(row.get("c")))
        name = str(row.get("n") or get_facility_name_from_search_index(prov) or "")
        item: dict[str, Any] = {
            "ccn": prov,
            "name": name,
            "city": str(row.get("y") or ""),
            "state": str(row.get("s") or ""),
            "canonical_url": provider_url(prov, name),
        }
        try:
            import facility_provider_indexes as fpi

            latest = (fpi.load_latest_hprd_by_ccn(str(quarter or "")) or {}).get(prov)
            if latest:
                item["staffing"] = {
                    "total_nurse_hprd": latest.get("total_nurse_hprd"),
                    "rn_hprd": latest.get("rn_hprd"),
                    "quarter": quarter,
                }
        except Exception:
            pass
        out_rows.append(item)

    if pac_q and len(pac_q) == 10:
        from ownership.owner_profile import load_owner_profile_resolved

        profile = load_owner_profile_resolved(pac_q)
        if profile:
            ccn_set = {
                normalize_ccn_input(str(f.get("ccn") or ""))
                for f in (profile.get("facilities") or [])
                if f.get("ccn")
            }
            if ccn_set:
                filtered = [r for r in out_rows if r["ccn"] in ccn_set]
                if filtered:
                    out_rows = filtered[:lim]

    return {
        "query": {
            "text": text_q,
            "ccn": ccn_q,
            "city": city_q,
            "state": state_q,
            "zip": zip_q,
            "owner_pac": pac_q,
        },
        "limit": lim,
        "count": len(out_rows),
        "facilities": out_rows,
        "period": {"quarter": quarter},
    }


def get_facility_record(ccn: str) -> dict[str, Any] | None:
    from app import get_canonical_latest_quarter, get_latest_provider_info_for_ccn, load_facility_quarterly_for_provider
    from canonical_urls import get_facility_name_from_search_index, provider_url
    from ownership.owner_profile import lookup_cms_ownership_for_provider

    prov = normalize_ccn_input(ccn)
    if not prov:
        return None

    df = load_facility_quarterly_for_provider(prov)
    if df is None or getattr(df, "empty", True):
        return None

    quarter = get_canonical_latest_quarter()
    latest = df[df["CY_Qtr"].astype(str) == str(quarter)] if quarter else df.iloc[[-1]]
    if latest.empty:
        latest = df.sort_values("CY_Qtr").iloc[[-1]]
    row = latest.iloc[0]
    raw_q = str(row.get("CY_Qtr") or quarter or "")

    name = str(row.get("PROVNAME") or get_facility_name_from_search_index(prov) or "")
    state = str(row.get("STATE") or "").upper()[:2]
    pi_raw = get_latest_provider_info_for_ccn(prov)
    if isinstance(pi_raw, tuple) and len(pi_raw) == 2:
        _pi_quarter, pi = pi_raw
        pi = pi if isinstance(pi, dict) else {}
    elif isinstance(pi_raw, dict):
        pi = pi_raw
    else:
        pi = {}

    ownership = lookup_cms_ownership_for_provider(pi, provider_name=name, ccn=prov)

    staffing = {
        "total_nurse_hprd": _num(row.get("Total_Nurse_HPRD")),
        "rn_hprd": _num(row.get("RN_HPRD")),
        "nurse_aide_hprd": _num(row.get("Nurse_Assistant_HPRD")),
        "lpn_hprd": _num(row.get("LPN_HPRD")),
        "contract_pct": _num(row.get("Contract_Percentage")),
        "census": _num(row.get("avg_daily_census")),
    }

    cms_ratings = {}
    for key, src in (
        ("overall", "overall_rating"),
        ("staffing", "staffing_rating"),
        ("health_inspection", "health_inspection_rating"),
    ):
        val = pi.get(src)
        if val is not None and str(val).strip() not in ("", "nan", "None"):
            cms_ratings[key] = val

    from app import get_facility_state_percentile

    pct_total, pct_rn = get_facility_state_percentile(
        prov,
        state,
        raw_q,
        staffing.get("total_nurse_hprd"),
        staffing.get("rn_hprd"),
    )

    payload: dict[str, Any] = {
        "facility": {
            "ccn": prov,
            "name": name,
            "state": state,
            "city": str(pi.get("city") or pi.get("City") or ""),
            "county": str(pi.get("county") or pi.get("County") or ""),
            "address": str(pi.get("address") or pi.get("Provider Address") or ""),
        },
        "staffing": staffing,
        "period": {"quarter": raw_q},
        "state_percentiles": {
            "total_nurse_hprd": pct_total,
            "rn_hprd": pct_rn,
            "cohort": f"{state} facilities in {raw_q}" if state and raw_q else None,
        },
        "cms_ratings": cms_ratings or None,
        "ownership_summary": (
            {
                "enrollment_pac": ownership.get("enrollment_pac"),
                "display_name": ownership.get("display_name"),
            }
            if ownership
            else None
        ),
        "canonical_url": provider_url(prov, name),
        "analysis": {
            "publisher": "PBJ320",
            "derived_metrics": [
                "total_nurse_hprd",
                "rn_hprd",
                "nurse_aide_hprd",
                "state_percentiles",
            ],
            "methodology_url": "/data-sources#methodology",
        },
    }
    return payload


def compare_facilities(
    ccns: list[str],
    *,
    include_state_percentiles: bool = True,
) -> dict[str, Any]:
    from app import get_canonical_latest_quarter

    uniq: list[str] = []
    seen: set[str] = set()
    for raw in ccns:
        prov = normalize_ccn_input(raw)
        if prov and prov not in seen:
            seen.add(prov)
            uniq.append(prov)
        if len(uniq) >= 10:
            break

    quarter = get_canonical_latest_quarter()
    records: list[dict[str, Any]] = []
    for prov in uniq:
        rec = get_facility_record(prov)
        if rec:
            records.append(rec)

    cohort_note = (
        "Explicit CCN comparison using canonical quarterly staffing for each facility. "
        "Optional state_percentiles use within-state cohort for the reporting quarter (existing PBJ320 methodology)."
    )

    return {
        "comparison_type": "explicit_ccns",
        "period": {"quarter": quarter},
        "cohort_definition": cohort_note if include_state_percentiles else "Explicit CCNs only",
        "facilities": records,
        "count": len(records),
    }


def _num(val: Any) -> float | None:
    try:
        if val is None or (isinstance(val, float) and val != val):
            return None
        return round(float(val), 4)
    except (TypeError, ValueError):
        return None
