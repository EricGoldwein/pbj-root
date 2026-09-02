"""
State-level CMS ownership index pages (/owners/<st> for each U.S. state + D.C.).

Published: all states in ownership/beta_gate.OWNERSHIP_PUBLIC_STATES (hub, sitemap, CHOW feed).
Optional draft slugs: ownership/state_owner_index_draft.py (preview-only, noindex).
"""
from __future__ import annotations

import calendar
import gzip
import html
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES
from ownership.display_format import format_org_display
from ownership.us_states import (
    US_STATE_CODE_TO_NAME,
    US_STATE_CODES,
    owner_index_slug,
    public_owner_states_coverage_phrase,
    state_page_slug,
)
from ownership.chow_lookup import CHOW_INDEX_PATH, _load_index as _load_chow_index
from ownership.owner_profile import (
    associate_profile_url,
    snf_owners_csv_path,
    snf_owners_release_month_year,
    snf_owners_source_citation,
    top_owner_organizations_for_state,
)

_OWNERSHIP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _OWNERSHIP_DIR.parent
_STATE_OWNER_INDEX_GZ = _OWNERSHIP_DIR / "state_owner_index.json.gz"
_LATEST_QUARTER_JSON = _REPO_ROOT / "latest_quarter_data.json"
_STATE_METRICS_CSV = _REPO_ROOT / "state_quarterly_metrics.csv"
_PROVIDER_INFO_CSV = _REPO_ROOT / "provider_info_combined_latest.csv"

# Canonical URL slugs (two-letter lowercase) for published state index pages.
PUBLIC_OWNER_INDEX_SLUGS: dict[str, str] = {
    owner_index_slug(code): code for code in sorted(OWNERSHIP_PUBLIC_STATES)
}

# Draft state indexes (preview-only): see state_owner_index_draft.py when used.
try:
    from ownership.state_owner_index_draft import (  # noqa: PLC0415
        DRAFT_OWNER_INDEX_SLUGS,
        STATE_OWNER_INDEX_DRAFT_STATES,
    )
except ImportError:
    STATE_OWNER_INDEX_DRAFT_STATES = frozenset()
    DRAFT_OWNER_INDEX_SLUGS: dict[str, str] = {}

# All routable /owners/<slug> state index pages (public + draft).
STATE_OWNER_INDEX_SLUGS: dict[str, str] = {
    **PUBLIC_OWNER_INDEX_SLUGS,
    **DRAFT_OWNER_INDEX_SLUGS,
}

STATE_OWNER_INDEX_STATES: frozenset[str] = OWNERSHIP_PUBLIC_STATES | STATE_OWNER_INDEX_DRAFT_STATES

_STATE_INDEX_H1_SUFFIX = " nursing home ownership & control"


def state_index_subtitle(state_name: str) -> str:
    """Hero subhead for all public state ownership index pages."""
    name = (state_name or "").strip()
    return (
        f"Explore {name} nursing home ownership groups, facility portfolios, "
        "and staffing patterns using public CMS data."
    )


def state_index_h1(state_name: str) -> str:
    """Visible H1 — no trailing “search” (search UI is immediately below)."""
    name = (state_name or "").strip()
    return f"{name}{_STATE_INDEX_H1_SUFFIX}"


def _build_state_index_meta_entry(state_code: str, state_name: str) -> dict[str, str]:
    return {
        "name": state_name,
        "slug": owner_index_slug(state_code),
        "state_page_slug": state_page_slug(state_code, state_name),
        "h1": state_index_h1(state_name),
        "subtitle": state_index_subtitle(state_name),
        "title": f"{state_name} Nursing Home Ownership & Control | PBJ320",
        "meta_description": (
            f"Search {state_name} nursing home owners, PAC IDs, affiliated facilities, "
            "and staffing context using public CMS ownership and PBJ staffing data."
        ),
        "hub_link_label": f"{state_name} nursing home ownership & control",
    }


# SEO + hub metadata for every published U.S. state / D.C. index page.
STATE_INDEX_META: dict[str, dict[str, str]] = {
    code: _build_state_index_meta_entry(code, US_STATE_CODE_TO_NAME[code])
    for code in sorted(US_STATE_CODES)
}


def state_index_layout_meta(state_code: str) -> dict[str, str]:
    """SEO layout fields for a public state ownership index page."""
    st = (state_code or "").strip().upper()[:2]
    meta = STATE_INDEX_META.get(st) or {}
    state_name = meta.get("name") or st
    slug = meta.get("slug") or st.lower()
    return {
        "page_title": meta.get("title") or f"{state_name} Nursing Home Ownership & Control | PBJ320",
        "meta_description": meta.get("meta_description")
        or (
            f"Search {state_name} nursing home owners, PAC IDs, affiliated facilities, "
            "and staffing context using public CMS ownership and PBJ staffing data."
        ),
        "canonical_path": state_index_canonical_path(st),
        "h1": meta.get("h1") or state_index_h1(state_name),
        "subtitle": meta.get("subtitle") or state_index_subtitle(state_name),
        "state_name": state_name,
        "state_code": st,
        "state_slug": slug,
        "breadcrumb_name": state_name,
    }


def state_index_lastmod_iso(state_code: str) -> str:
    """YYYY-MM-DD for sitemap lastmod (index artifact mtime)."""
    st = (state_code or "").strip().upper()[:2]
    if st not in US_STATE_CODES and st not in STATE_OWNER_INDEX_DRAFT_STATES:
        return ""
    if not _STATE_OWNER_INDEX_GZ.is_file():
        return ""
    try:
        mtime = datetime.fromtimestamp(_STATE_OWNER_INDEX_GZ.stat().st_mtime, tz=timezone.utc)
        return mtime.strftime("%Y-%m-%d")
    except OSError:
        return ""


def public_owner_index_sitemap_paths() -> list[tuple[str, str, str, str]]:
    """
    Sitemap rows for published state ownership indexes: (path, priority, changefreq, lastmod_iso).
    Verified from: PUBLIC_OWNER_INDEX_SLUGS, STATE_INDEX_META.
    """
    rows: list[tuple[str, str, str, str]] = []
    for slug in sorted(PUBLIC_OWNER_INDEX_SLUGS.keys()):
        code = PUBLIC_OWNER_INDEX_SLUGS[slug]
        if code not in STATE_INDEX_META:
            continue
        path = state_index_canonical_path(code)
        lastmod = state_index_lastmod_iso(code) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows.append((path, "0.7", "weekly", lastmod))
    return rows


def resolve_public_owner_index_slug(slug: str | None) -> str | None:
    """Map /owners/<slug> to a published state code when slug is a public index route."""
    s = (slug or "").strip().lower()
    return PUBLIC_OWNER_INDEX_SLUGS.get(s)


def resolve_state_owner_index_slug(slug: str | None) -> str | None:
    """Map /owners/<slug> to a state code for any published or draft index route."""
    s = (slug or "").strip().lower()
    return STATE_OWNER_INDEX_SLUGS.get(s)


def state_owner_index_is_draft(state_code: str | None) -> bool:
    st = (state_code or "").strip().upper()[:2]
    return st in STATE_OWNER_INDEX_DRAFT_STATES


def state_owner_index_enabled_for_state(state_code: str | None) -> bool:
    """Whether /owners/<slug> index data and search should load for this state."""
    st = (state_code or "").strip().upper()[:2]
    return st in STATE_OWNER_INDEX_STATES


def state_index_canonical_path(state_code: str) -> str:
    st = (state_code or "").strip().upper()[:2]
    meta = STATE_INDEX_META.get(st) or {}
    slug = meta.get("slug") or st.lower()
    return f"/owners/{slug}"


@lru_cache(maxsize=1)
def _load_state_owner_index_artifact() -> dict[str, list[dict[str, Any]]] | None:
    if not _STATE_OWNER_INDEX_GZ.is_file():
        return None
    try:
        with gzip.open(_STATE_OWNER_INDEX_GZ, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return None
        out: dict[str, list[dict[str, Any]]] = {}
        for k, v in raw.items():
            if isinstance(v, list):
                out[str(k).upper()[:2]] = list(v)
        return out
    except Exception:
        return None


def list_state_owner_index_rows(
    state_code: str,
    *,
    limit: int | None = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Rows for state index table; returns (slice, total_count)."""
    st = (state_code or "").strip().upper()[:2]
    if not state_owner_index_enabled_for_state(st):
        return [], 0

    artifact = _load_state_owner_index_artifact()
    rows: list[dict[str, Any]]
    if artifact is not None and st in artifact:
        rows = list(artifact.get(st) or [])
    else:
        rows = top_owner_organizations_for_state(st, limit=10_000)

    total = len(rows)
    start = max(0, int(offset))
    if limit is None:
        return rows[start:], total
    end = start + max(1, int(limit))
    return rows[start:end], total


def search_state_owner_index(
    query: str,
    state_code: str,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Name/PAC search within one state's CMS-linked owner index (facility counts are in-state)."""
    from ownership.name_search import name_search_rank, normalize_search_tokens
    from ownership.owner_profile import _norm_org_key, normalize_associate_id

    st = (state_code or "").strip().upper()[:2]
    if not state_owner_index_enabled_for_state(st):
        return []
    q = (query or "").strip()
    if not q:
        return []

    rows, _total = list_state_owner_index_rows(st, limit=None)
    if not rows:
        return []

    cap = max(1, int(limit))
    pac_q = normalize_associate_id(q)
    if len(pac_q) == 10 and pac_q.isdigit():
        for row in rows:
            if str(row.get("associate_id") or "") == pac_q:
                return [row]
        return []

    qnorm = _norm_org_key(q)
    if len(qnorm) < 2 and len(normalize_search_tokens(q)) < 1:
        return []

    scored: list[tuple[int, int, str, dict[str, Any]]] = []
    for row in rows:
        name = str(row.get("name") or "")
        pac = str(row.get("associate_id") or "")
        if pac == qnorm:
            rank = 0
        else:
            rank = name_search_rank(q, name)
            if rank is None:
                continue
        scored.append((rank, -int(row.get("facility_count") or 0), name.lower(), row))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [row for *_rest, row in scored[:cap]]


def state_owner_index_search_suggestions(
    query: str,
    state_code: str,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Autocomplete payloads for /owners/api/cms-search on state index pages."""
    rows = search_state_owner_index(query, state_code, limit=limit)
    suggestions: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {
            "associate_id": str(row.get("associate_id") or ""),
            "name": str(row.get("name") or ""),
            "profile_url": str(row.get("profile_url") or ""),
            "facility_count": int(row.get("facility_count") or 0),
        }
        total_raw = row.get("facility_count_total")
        if total_raw is not None:
            item["facility_count_total"] = int(total_raw)
        suggestions.append(item)
    return suggestions


def format_index_owner_name(raw: str) -> str:
    return format_org_display(str(raw or "—"))


def format_portfolio_facility_count(state_code: str, row: dict[str, Any]) -> str:
    """Compact ranking count with an explicit “facilities” label.

    National scope: "273 facilities".
    State scope: primary in-state count as "53 facilities" (tooltip carries nationwide detail).
    """
    st = (state_code or "").strip().upper()[:2]
    in_n = int(row.get("facility_count") or 0)
    total_raw = row.get("facility_count_total")
    total_n = int(total_raw) if total_raw is not None else in_n
    n = (total_n or in_n) if not st else in_n
    return f"{n} facilit{'y' if n == 1 else 'ies'}"


@lru_cache(maxsize=1)
def _national_top_owner_rows_cached() -> tuple[tuple[Any, ...], ...]:
    """Dedupe state-index rows by PAC using nationwide facility_count_total."""
    artifact = _load_state_owner_index_artifact()
    if not artifact:
        return tuple()
    best: dict[str, dict[str, Any]] = {}
    for rows in artifact.values():
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            pac = str(row.get("associate_id") or "").strip()
            if len(pac) != 10 or not pac.isdigit():
                continue
            total = int(row.get("facility_count_total") or row.get("facility_count") or 0)
            prev = best.get(pac)
            prev_total = (
                int(prev.get("facility_count_total") or prev.get("facility_count") or 0)
                if prev
                else -1
            )
            if prev is None or total > prev_total:
                merged = dict(row)
                merged["facility_count"] = total
                merged["facility_count_total"] = total
                best[pac] = merged
    ranked = sorted(
        best.values(),
        key=lambda r: (-int(r.get("facility_count_total") or 0), str(r.get("name") or "").lower()),
    )
    return tuple(tuple(sorted(r.items())) for r in ranked)


def list_national_top_owner_rows(*, limit: int | None = 5) -> list[dict[str, Any]]:
    """Largest ownership portfolios nationwide (from state_owner_index totals)."""
    cached = _national_top_owner_rows_cached()
    rows = [dict(item) for item in cached]
    if limit is None:
        return rows
    return rows[: max(1, int(limit))]


def _parse_iso_date_label(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
    except ValueError:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{calendar.month_abbr[mo]} {day}, {y}"
    return s


def _month_year_label(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"{calendar.month_name[month]} {year}"
    return str(year)


@lru_cache(maxsize=1)
def _latest_pbj_quarter_ids() -> tuple[str, str]:
    """(CY_Qtr id, display label) from latest_quarter_data.json."""
    if not _LATEST_QUARTER_JSON.is_file():
        return "", ""
    try:
        raw = json.loads(_LATEST_QUARTER_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    qid = str(raw.get("quarter") or "").strip()
    qdisp = str(raw.get("quarter_display") or "").strip()
    if not qdisp and qid:
        try:
            from pbj_format import format_quarter_display

            qdisp = format_quarter_display(qid) or qid
        except Exception:
            qdisp = qid
    return qid, qdisp


@lru_cache(maxsize=8)
def _state_pbj_quarter_row(state_code: str, quarter_id: str) -> dict[str, Any]:
    st = (state_code or "").strip().upper()[:2]
    q = (quarter_id or "").strip()
    if not st or not q or not _STATE_METRICS_CSV.is_file():
        return {}
    try:
        import pandas as pd

        df = pd.read_csv(_STATE_METRICS_CSV)
        m = df[(df["STATE"].astype(str).str.upper() == st) & (df["CY_Qtr"].astype(str) == q)]
        if m.empty:
            return {}
        row = m.iloc[0]
        out: dict[str, Any] = {}
        for key in (
            "Total_Nurse_HPRD",
            "RN_HPRD",
            "Contract_Percentage",
            "facility_count",
        ):
            val = row.get(key)
            if val is None or (isinstance(val, float) and val != val):
                continue
            try:
                out[key] = float(val)
            except (TypeError, ValueError):
                pass
        return out
    except Exception:
        return {}


@lru_cache(maxsize=4)
def _state_cms_star_averages(state_code: str) -> dict[str, Any]:
    st = (state_code or "").strip().upper()[:2]
    if not st or not _PROVIDER_INFO_CSV.is_file():
        return {}
    try:
        import pandas as pd

        df = pd.read_csv(
            _PROVIDER_INFO_CSV,
            usecols=["state", "overall_rating", "staffing_rating"],
            low_memory=False,
        )
        sub = df[df["state"].astype(str).str.upper() == st].copy()
        if sub.empty:
            return {}
        for col in ("overall_rating", "staffing_rating"):
            sub[col] = pd.to_numeric(sub[col], errors="coerce")
        ovr = sub["overall_rating"].dropna()
        stf = sub["staffing_rating"].dropna()
        out: dict[str, Any] = {"n_facilities_rated": int(len(sub))}
        if len(ovr):
            out["mean_overall_rating"] = round(float(ovr.mean()), 1)
        if len(stf):
            out["mean_staffing_rating"] = round(float(stf.mean()), 1)
        return out
    except Exception:
        return {}


def state_owner_page_context(state_code: str) -> dict[str, Any]:
    """Source lines + PBJ staffing snapshot for state ownership index pages."""
    st = (state_code or "").strip().upper()[:2]
    meta = STATE_INDEX_META.get(st) or {}
    state_name = meta.get("name") or st

    _owners_path = snf_owners_csv_path()
    owners_citation = snf_owners_source_citation(_owners_path)
    owners_ym = snf_owners_release_month_year(_owners_path)
    owners_updated = _month_year_label(*owners_ym) if owners_ym else ""

    chow_meta = (_load_chow_index().get("meta") or {}) if CHOW_INDEX_PATH.is_file() else {}
    chow_source = str(chow_meta.get("source_label") or "CMS SNF Change of Ownership").strip()
    chow_updated = _parse_iso_date_label(str(chow_meta.get("generated_at") or ""))

    index_updated = ""
    if _STATE_OWNER_INDEX_GZ.is_file():
        try:
            mtime = datetime.fromtimestamp(
                _STATE_OWNER_INDEX_GZ.stat().st_mtime, tz=timezone.utc
            )
            index_updated = f"{mtime.strftime('%b')} {mtime.day}, {mtime.year}"
        except OSError:
            index_updated = ""

    qid, qdisp = _latest_pbj_quarter_ids()
    pbj_row = _state_pbj_quarter_row(st, qid) if qid else {}
    stars = _state_cms_star_averages(st)

    _, index_total = list_state_owner_index_rows(st, limit=1)

    from ownership.chow_lookup import chow_count_for_state

    return {
        "state_code": st,
        "state_name": state_name,
        "state_page_slug": meta.get("state_page_slug") or st.lower(),
        "index_entity_count": index_total,
        "owners_source": owners_citation,
        "owners_updated": owners_updated,
        "chow_source": chow_source,
        "chow_updated": chow_updated,
        "index_updated": index_updated,
        "pbj_quarter_id": qid,
        "pbj_quarter_display": qdisp,
        "pbj": pbj_row,
        "cms_stars": stars,
        "chow_events_in_state": chow_count_for_state(st),
    }


def public_owner_index_hub_entries() -> list[dict[str, str]]:
    """Sorted hub cards / prose entries for published state ownership indexes."""
    rows: list[dict[str, str]] = []
    for slug, code in PUBLIC_OWNER_INDEX_SLUGS.items():
        meta = STATE_INDEX_META.get(code) or {}
        name = str(meta.get("name") or code).strip()
        rows.append(
            {
                "state_code": code,
                "slug": slug,
                "name": name,
                "path": state_index_canonical_path(code),
                "hub_link_label": str(meta.get("hub_link_label") or f"{name} nursing home ownership search"),
            }
        )
    rows.sort(key=lambda row: row["name"])
    return rows


def format_public_owner_states_prose(*, conjunction: str = "and") -> str:
    """Human-readable coverage phrase for hub/SEO (not a 51-state name list)."""
    _ = conjunction
    return public_owner_states_coverage_phrase()


def format_public_owner_states_links_html(*, class_name: str = "") -> str:
    """Comma-separated anchor list for published state ownership indexes."""
    cls = f' class="{class_name}"' if class_name else ""
    parts = [
        f'<a href="{html.escape(row["path"])}"{cls}>{html.escape(row["name"])}</a>'
        for row in public_owner_index_hub_entries()
    ]
    return ", ".join(parts)


def owners_hub_page_context() -> dict[str, str]:
    """National /owners hub metadata (search catalog + CMS ownership freshness)."""
    from ownership.owner_profile import snf_owners_csv_path, snf_owners_release_month_year

    _owners_path = snf_owners_csv_path()
    owners_ym = snf_owners_release_month_year(_owners_path)
    owners_updated = _month_year_label(*owners_ym) if owners_ym else ""
    catalog_n = 0
    try:
        from ownership.owner_profile import _public_owner_search_catalog  # noqa: PLC0415

        catalog_n = len(_public_owner_search_catalog())
    except Exception:
        catalog_n = 0
    state_counts: list[str] = []
    artifact = _load_state_owner_index_artifact()
    if artifact:
        for row in public_owner_index_hub_entries():
            code = row["state_code"]
            state_counts.append(f"{code} {len(artifact.get(code) or []):,}")
    return {
        "owners_updated": owners_updated,
        "catalog_entity_count": str(catalog_n),
        "state_index_counts": ", ".join(state_counts),
        "public_states_prose": format_public_owner_states_prose(),
    }


def locked_state_index_message(state_name: str = "") -> str:
    label = (state_name or "that state").strip()
    coverage = format_public_owner_states_prose()
    return (
        f"Ownership index pages are available for {coverage}. "
        f"{label} is not covered on this path."
    )
