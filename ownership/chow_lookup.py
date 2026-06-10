"""
Lightweight CHOW index lookups for provider/state/entity pages and PBJ AI context.

Reads chow_index.json (built by scripts/build_chow_index.py). Cached in-process.
"""
from __future__ import annotations

import calendar
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
CHOW_INDEX_PATH = _REPO / "chow_index.json"


@lru_cache(maxsize=1)
def _load_index() -> dict[str, Any]:
    if not CHOW_INDEX_PATH.is_file():
        return {"meta": {}, "summary": {}, "records": [], "by_ccn": {}, "state_counts": {}}
    try:
        data = json.loads(CHOW_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"meta": {}, "summary": {}, "records": [], "by_ccn": {}, "state_counts": {}}
    if "by_ccn" not in data or "state_counts" not in data or "by_associate_id" not in data:
        data = _ensure_indexes(data)
    return data


def _ensure_indexes(data: dict[str, Any]) -> dict[str, Any]:
    """Build by_ccn, by_associate_id, and state_counts if missing (older index files)."""
    from ownership.owner_profile import normalize_associate_id

    by_ccn: dict[str, list[dict[str, Any]]] = {}
    by_associate_id: dict[str, list[dict[str, Any]]] = {}
    state_counts: dict[str, int] = {}
    for rec in data.get("records") or []:
        ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
        if ccn:
            by_ccn.setdefault(ccn, []).append(rec)
        st = str(rec.get("state") or "").strip().upper()[:2]
        if st:
            state_counts[st] = state_counts.get(st, 0) + 1
        for pac_key in ("buyer_associate_id", "seller_associate_id"):
            pac = normalize_associate_id(rec.get(pac_key))
            if len(pac) == 10:
                by_associate_id.setdefault(pac, []).append(rec)
    for ccn in by_ccn:
        by_ccn[ccn].sort(key=lambda r: r.get("effective_date") or "", reverse=True)
    for pac in by_associate_id:
        by_associate_id[pac].sort(key=lambda r: r.get("effective_date") or "", reverse=True)
    data["by_ccn"] = by_ccn
    data["by_associate_id"] = by_associate_id
    data["state_counts"] = state_counts
    return data


def chow_records_for_ccn(ccn: str, limit: int = 5) -> list[dict[str, Any]]:
    ccn_norm = str(ccn or "").strip().zfill(6)[-6:]
    if not ccn_norm:
        return []
    idx = _load_index()
    rows = (idx.get("by_ccn") or {}).get(ccn_norm) or []
    if limit is None or limit <= 0:
        return rows
    return rows[:limit]


def chow_records_for_state(state_code: str, *, limit: int = 0) -> list[dict[str, Any]]:
    """CHOW rows for one state, newest effective date first."""
    st = str(state_code or "").strip().upper()[:2]
    if not st:
        return []
    rows = [
        r
        for r in _load_index().get("records") or []
        if str(r.get("state") or "").strip().upper()[:2] == st
    ]
    rows.sort(key=lambda r: str(r.get("effective_date") or ""), reverse=True)
    if limit and limit > 0:
        return rows[:limit]
    return rows


def chow_record_by_id(chow_id: str, *, state_code: str | None = None) -> dict[str, Any] | None:
    """Single CHOW row by stable chow_id (optional state guard)."""
    cid = str(chow_id or "").strip()
    if not cid:
        return None
    st_filter = str(state_code or "").strip().upper()[:2] if state_code else ""
    for rec in _load_index().get("records") or []:
        if str(rec.get("chow_id") or "").strip() != cid:
            continue
        if st_filter and str(rec.get("state") or "").strip().upper()[:2] != st_filter:
            continue
        return rec
    return None


def chow_count_for_state(state_code: str) -> int:
    st = str(state_code or "").strip().upper()[:2]
    if not st:
        return 0
    idx = _load_index()
    return int((idx.get("state_counts") or {}).get(st) or 0)


def chow_total_count() -> int:
    idx = _load_index()
    summary = idx.get("summary") or {}
    return int(summary.get("total_records") or len(idx.get("records") or []))


def chow_facility_place_label(rec: dict[str, Any]) -> str:
    """Compact city or county for a CHOW row (from provider index by CCN)."""
    from ownership.display_format import format_org_display

    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    if not ccn.isdigit():
        return ""
    try:
        from ownership.owner_portfolio_metrics import _ccn_provider_lookup

        pi = _ccn_provider_lookup().get(ccn) or {}
    except Exception:
        pi = {}
    city = format_org_display(str(pi.get("city") or ""))
    st = str(rec.get("state") or pi.get("state") or "").strip().upper()[:2]
    if city and len(st) == 2:
        return f"{city}, {st}"
    county = format_org_display(str(pi.get("county") or ""))
    co = county
    if co.lower().endswith(" county"):
        co = co[: -len(" county")].strip()
    if co and len(st) == 2:
        return f"{co} Co., {st}"
    return st if len(st) == 2 else co


def chow_facility_label(rec: dict[str, Any]) -> str:
    """Provider name for a CHOW row; prefer PBJ provider name over buyer/seller labels."""
    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    buyer_org = str(rec.get("buyer_org_name") or "").strip()
    buyer_dba = str(rec.get("buyer_dba_name") or "").strip()
    fd = str(rec.get("facility_display_name") or "").strip()
    if fd and fd not in (buyer_org, buyer_dba):
        return fd
    if ccn.isdigit():
        try:
            from ownership.owner_portfolio_metrics import _ccn_provider_lookup

            prov_name = str((_ccn_provider_lookup().get(ccn) or {}).get("provider_name") or "").strip()
            if prov_name:
                return prov_name
        except Exception:
            pass
    if fd:
        return fd
    if ccn.isdigit():
        return f"CCN {ccn}"
    return "—"


def format_chow_date(iso: str) -> str:
    if not iso or len(iso) < 10:
        return iso or "—"
    p = iso.split("-")
    if len(p) == 3:
        return f"{p[1]}/{p[2]}/{p[0]}"
    return iso


def format_chow_date_dashed(iso: str) -> str:
    """US display date MM-DD-YYYY from ISO (source date unchanged in data)."""
    if not iso or len(iso) < 10:
        return iso or "—"
    p = iso.split("-")
    if len(p) == 3:
        return f"{p[1]}-{p[2]}-{p[0]}"
    return iso


def format_chow_date_compact(iso: str) -> str:
    """Short list date MM/DD from ISO."""
    if not iso or len(iso) < 10:
        return iso or "—"
    p = iso.split("-")
    if len(p) == 3:
        return f"{p[1]}/{p[2]}"
    return iso


def format_chow_date_short_label(iso: str) -> str:
    """Compact list label e.g. Jun 01 from ISO."""
    if not iso or len(iso) < 10:
        return iso or "—"
    p = iso.split("-")
    if len(p) != 3:
        return iso
    try:
        mo = int(p[1])
        day = int(p[2])
    except ValueError:
        return iso
    if not 1 <= mo <= 12:
        return iso
    return f"{calendar.month_abbr[mo]} {day:02d}"


def format_chow_date_feed_label(iso: str) -> str:
    """Compact ownership-feed date M/D/YY (no leading zeros on month/day)."""
    if not iso or len(iso) < 10:
        return iso or "—"
    p = iso.split("-")
    if len(p) != 3:
        return iso
    try:
        year = int(p[0])
        mo = int(p[1])
        day = int(p[2])
    except ValueError:
        return iso
    if not 1 <= mo <= 12 or day < 1:
        return iso
    return f"{mo}/{day}/{year % 100:02d}"


def chow_index_date_range_label() -> str:
    """Human-readable effective-date span for the current CHOW index."""
    summary = _load_index().get("summary") or {}
    dmin = str(summary.get("date_min") or "").strip()
    dmax = str(summary.get("date_max") or "").strip()
    if dmin and dmax:
        return f"{format_chow_date(dmin)} – {format_chow_date(dmax)}"
    if dmax:
        return f"through {format_chow_date(dmax)}"
    return ""


def chow_records_for_party(
    normalized: str,
    side: str,
    state_code: str | None = None,
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """CHOW rows for a buyer or seller organization (by normalized name)."""
    norm = str(normalized or "").strip()
    if not norm:
        return []
    norm_key = f"{side}_normalized"
    st = str(state_code or "").strip().upper()[:2] if state_code else ""
    out: list[dict[str, Any]] = []
    for rec in _load_index().get("records") or []:
        if str(rec.get(norm_key) or "").strip() != norm:
            continue
        if st and str(rec.get("state") or "").strip().upper()[:2] != st:
            continue
        out.append(rec)
    out.sort(key=lambda r: r.get("effective_date") or "", reverse=True)
    return out[: max(1, limit)] if limit else out


def chow_summary_line_for_ccn(ccn: str) -> str:
    """Plain-text summary for PBJ AI context (no HTML)."""
    rows = chow_records_for_ccn(ccn, limit=3)
    if not rows:
        return (
            "CMS CHOW (change of ownership) records on PBJ320: none matched this CCN in the "
            "current index. See the ownership block on this facility page when available."
        )
    parts = []
    for r in rows:
        parts.append(
            f"{format_chow_date(r.get('effective_date') or '')} — buyer "
            f"{r.get('buyer_org_name') or r.get('buyer_dba_name') or '—'}; seller "
            f"{r.get('seller_org_name') or '—'}"
        )
    ccn_norm = str(ccn).strip().zfill(6)[-6:]
    more = len((_load_index().get("by_ccn") or {}).get(ccn_norm, [])) - len(rows)
    extra = f" (+{more} more)" if more > 0 else ""
    return (
        f"CMS CHOW records for this CCN ({len(rows)} shown{extra}): "
        + "; ".join(parts)
        + ". See ownership / CHOW context on this facility page."
    )


def _party_list_from_records(
    records: list[dict[str, Any]],
    side: str,
    limit: int,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    meta: dict[str, dict[str, str]] = {}
    ccns_by_norm: dict[str, set[str]] = {}
    norm_key = f"{side}_normalized"
    for r in records:
        norm = str(r.get(norm_key) or "").strip()
        if not norm:
            continue
        counts[norm] += 1
        ccn = str(r.get("ccn") or "").strip().zfill(6)[-6:]
        if ccn:
            ccns_by_norm.setdefault(norm, set()).add(ccn)
        if norm not in meta:
            meta[norm] = {
                "name": str(r.get(f"{side}_org_name") or norm),
                "associate_id": str(r.get(f"{side}_associate_id") or ""),
                "owner_url": str(r.get(f"{side}_owner_url") or ""),
                "normalized": norm,
            }
    out: list[dict[str, Any]] = []
    for norm, cnt in counts.most_common(limit):
        m = meta[norm]
        out.append(
            {
                "name": m["name"],
                "count": cnt,
                "facility_count": len(ccns_by_norm.get(norm) or ()),
                "associate_id": m["associate_id"],
                "owner_url": m["owner_url"],
                "normalized": norm,
            }
        )
    return out


def chow_state_stats(state_code: str) -> dict[str, int]:
    """Aggregate CHOW counts for a state (events, unique parties, facilities)."""
    st = str(state_code or "").strip().upper()[:2]
    if not st:
        return {}
    rows = [r for r in _load_index().get("records") or [] if str(r.get("state") or "").upper()[:2] == st]
    buyers = {str(r.get("buyer_normalized") or "").strip() for r in rows if r.get("buyer_normalized")}
    sellers = {str(r.get("seller_normalized") or "").strip() for r in rows if r.get("seller_normalized")}
    ccns = {str(r.get("ccn") or "").strip().zfill(6)[-6:] for r in rows if r.get("ccn")}
    buyers.discard("")
    sellers.discard("")
    ccns.discard("")
    return {
        "events": len(rows),
        "unique_buyers": len(buyers),
        "unique_sellers": len(sellers),
        "unique_facilities": len(ccns),
    }


@lru_cache(maxsize=1)
def _top_parties_index() -> dict[str, Any]:
    idx = _load_index()
    summary = idx.get("summary") or {}
    if summary.get("top_buyers") is not None and summary.get("top_sellers") is not None:
        return {
            "national": {
                "buyers": summary.get("top_buyers") or [],
                "sellers": summary.get("top_sellers") or [],
            },
            "by_state": summary.get("top_by_state") or {},
        }
    records = idx.get("records") or []
    national_buyers = _party_list_from_records(records, "buyer", 8)
    national_sellers = _party_list_from_records(records, "seller", 8)
    states = sorted({r.get("state") for r in records if r.get("state")})
    by_state: dict[str, dict[str, list]] = {}
    for st in states:
        st_rows = [r for r in records if r.get("state") == st]
        by_state[str(st)] = {
            "buyers": _party_list_from_records(st_rows, "buyer", 6),
            "sellers": _party_list_from_records(st_rows, "seller", 6),
        }
    return {
        "national": {"buyers": national_buyers, "sellers": national_sellers},
        "by_state": by_state,
    }


def top_chow_parties(state_code: str | None = None, limit: int | None = None) -> dict[str, list[dict[str, Any]]]:
    """Featured top buyers/sellers by CHOW count (national or per state)."""
    data = _top_parties_index()
    if state_code:
        st = str(state_code).strip().upper()[:2]
        block = (data.get("by_state") or {}).get(st) or {"buyers": [], "sellers": []}
        lim = limit or 6
    else:
        block = data.get("national") or {"buyers": [], "sellers": []}
        lim = limit or 8
    return {
        "buyers": list(block.get("buyers") or [])[:lim],
        "sellers": list(block.get("sellers") or [])[:lim],
    }


def chow_records_for_associate_id(associate_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """CHOW rows where buyer or seller PAC matches (enrollment associate ID)."""
    from ownership.owner_profile import normalize_associate_id

    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return []
    rows = list((_load_index().get("by_associate_id") or {}).get(pac) or [])
    out: list[dict[str, Any]] = []
    for rec in rows:
        buyer = normalize_associate_id(rec.get("buyer_associate_id"))
        row = dict(rec)
        row["chow_role"] = "buyer" if pac == buyer else "seller"
        out.append(row)
    if limit is None or limit <= 0:
        return out
    return out[:limit]


def chow_party_label_for_associate_id(associate_id: str) -> dict[str, str] | None:
    """Best-effort org name and role from first CHOW match for this PAC."""
    rows = chow_records_for_associate_id(associate_id, limit=1)
    if not rows:
        return None
    rec = rows[0]
    role = rec.get("chow_role") or "party"
    if role == "buyer":
        return {
            "display_name": rec.get("buyer_org_name") or rec.get("buyer_dba_name") or "Unknown",
            "role": "buyer",
        }
    return {
        "display_name": rec.get("seller_org_name") or rec.get("seller_dba_name") or "Unknown",
        "role": "seller",
    }


def chow_summary_line_for_state(state_code: str, state_name: str = "") -> str:
    cnt = chow_count_for_state(state_code)
    if cnt <= 0:
        return ""
    label = state_name or state_code
    return (
        f"CMS CHOW records in {label}: {cnt} reported ownership-change events in the current "
        f"PBJ320 index. See CHOW context on the {label} state page when available."
    )
