"""
State-level CMS ownership index pages (/owners/ny, /owners/ct).

Verified from: ownership/beta_gate.OWNERSHIP_PUBLIC_STATES, state_owner_index.json.gz (build).
"""
from __future__ import annotations

import calendar
import gzip
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES, ownership_public_enabled_for_state
from ownership.display_format import format_org_display
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

# Canonical URL slugs (lowercase) for public state index pages.
PUBLIC_OWNER_INDEX_SLUGS: dict[str, str] = {
    "ny": "NY",
    "ct": "CT",
}

_STATE_INDEX_H1_SUFFIX = " Nursing Home Ownership Search"


def state_index_subtitle(state_name: str) -> str:
    """Hero subhead for all public state ownership index pages."""
    name = (state_name or "").strip()
    return (
        f"Explore {name} nursing home ownership groups, facility portfolios, "
        "and staffing patterns using public CMS data."
    )


def state_index_h1(state_name: str) -> str:
    """H1 text; HTML may split before 'Ownership Search' on mobile."""
    name = (state_name or "").strip()
    return f"{name}{_STATE_INDEX_H1_SUFFIX}"


STATE_INDEX_META: dict[str, dict[str, str]] = {
    "NY": {
        "name": "New York",
        "slug": "ny",
        "state_page_slug": "new-york",
        "h1": state_index_h1("New York"),
        "subtitle": state_index_subtitle("New York"),
        "title": "New York Nursing Home Ownership Search | PBJ320",
        "meta_description": (
            "Search New York nursing home owners, PAC IDs, affiliated facilities, "
            "and staffing context using public CMS ownership and PBJ staffing data."
        ),
        "hub_link_label": "New York nursing home ownership search",
    },
    "CT": {
        "name": "Connecticut",
        "slug": "ct",
        "state_page_slug": "connecticut",
        "h1": state_index_h1("Connecticut"),
        "subtitle": state_index_subtitle("Connecticut"),
        "title": "Connecticut Nursing Home Ownership Search | PBJ320",
        "meta_description": (
            "Search Connecticut nursing home owners, PAC IDs, affiliated facilities, "
            "and staffing context using public CMS ownership and PBJ staffing data."
        ),
        "hub_link_label": "Connecticut nursing home ownership search",
    },
}


def state_index_layout_meta(state_code: str) -> dict[str, str]:
    """SEO layout fields for a public state ownership index page."""
    st = (state_code or "").strip().upper()[:2]
    meta = STATE_INDEX_META.get(st) or {}
    state_name = meta.get("name") or st
    slug = meta.get("slug") or st.lower()
    return {
        "page_title": meta.get("title") or f"{state_name} Nursing Home Ownership Search | PBJ320",
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
    if st not in STATE_INDEX_META:
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
    """Map /owners/<slug> to NY or CT when slug is a public index route."""
    s = (slug or "").strip().lower()
    return PUBLIC_OWNER_INDEX_SLUGS.get(s)


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
    if st not in OWNERSHIP_PUBLIC_STATES:
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
    from ownership.owner_profile import _norm_org_key, normalize_associate_id

    st = (state_code or "").strip().upper()[:2]
    if not ownership_public_enabled_for_state(st):
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
    if len(qnorm) < 2:
        return []

    scored: list[tuple[int, int, str, dict[str, Any]]] = []
    for row in rows:
        name = str(row.get("name") or "")
        key = _norm_org_key(name)
        pac = str(row.get("associate_id") or "")
        if qnorm not in key and qnorm not in pac:
            continue
        if key.startswith(qnorm):
            rank = 0
        elif qnorm in key[: max(len(qnorm) + 4, 8)]:
            rank = 1
        else:
            rank = 2
        scored.append((rank, -int(row.get("facility_count") or 0), name.lower(), row))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [row for *_rest, row in scored[:cap]]


def format_index_owner_name(raw: str) -> str:
    return format_org_display(str(raw or "—"))


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


def locked_state_index_message(state_name: str = "") -> str:
    label = (state_name or "that state").strip()
    return (
        f"Ownership index pages are currently available for New York and Connecticut only "
        f"({label} is not published on this path yet)."
    )
