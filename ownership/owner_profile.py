"""
CMS SNF All Owners profiles for /owners/<10-digit-associate-id>.

CMS uses two associate ID fields:
  - ASSOCIATE ID — provider / enrollment PAC (facility enrollment entity)
  - ASSOCIATE ID - OWNER — owner / control-party PAC

CHOW buyer/seller PACs are usually enrollment PACs. This module resolves the correct profile.
"""
from __future__ import annotations

import calendar
import gzip
import json
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator, Sequence
from typing import Any, cast

import pandas as pd

from ownership.display_format import format_org_display, format_role_text
from ownership.owner_portfolio_metrics import _provider_info_csv_paths, provider_info_crosswalk_paths

_REPO = Path(__file__).resolve().parent.parent
_OWNERSHIP_DIR = _REPO / "ownership"
_SNF_OWNERS_GLOB = "SNF_All_Owners*.csv"
_OWNERS_LOOKUP_DB = _OWNERSHIP_DIR / "snf_owners_lookup.sqlite"
_ORG_INDEX_GZ = _OWNERSHIP_DIR / "snf_owners_org_index.json.gz"
_CCN_ENROLLMENT_INDEX_GZ = _OWNERSHIP_DIR / "snf_owners_ccn_index.json.gz"
_OWNERS_TABLE = "snf_owners"

_CCN_MATCH_METHOD_RANK = {"legal_exact": 3, "name_exact": 2, "fuzzy": 1, "": 0}

ENROLLMENT_PAC_COL = "ASSOCIATE ID"
OWNER_PAC_COL = "ASSOCIATE ID - OWNER"

_MONTH_FROM_NAME = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_associate_id(val: str | None) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val != val:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    # Strip leading letter O only when entire token is O + digits (legacy quirk)
    if re.match(r"^[Oo]\d+$", s):
        s = s[1:]
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) == 10:
        return digits
    if len(digits) == 9:
        return digits.zfill(10)
    if len(digits) == 11:
        return digits[-10:]
    return ""


def _parse_snf_owners_filename(path: Path) -> tuple[int, int, int] | None:
    """Parse (year, month, day) from SNF_All_Owners*.csv filename for ordering."""
    lower = path.stem.lower()
    m_iso = re.search(r"(\d{4})[._-](\d{1,2})(?:[._-](\d{1,2}))?", lower)
    if m_iso:
        y, mo = int(m_iso.group(1)), int(m_iso.group(2))
        day = int(m_iso.group(3)) if m_iso.group(3) else 1
        if 1 <= mo <= 12:
            return y, mo, day
    m_word = re.search(r"owners[_-]?([a-z]+)[_-]?(\d{4})", lower)
    if m_word:
        mo = _MONTH_FROM_NAME.get(m_word.group(1))
        if mo:
            return int(m_word.group(2)), mo, 1
    return None


@lru_cache(maxsize=1)
def snf_owners_csv_path() -> Path | None:
    """Newest SNF_All_Owners*.csv in ownership/ (by date in filename)."""
    if not _OWNERSHIP_DIR.is_dir():
        return None
    candidates: list[tuple[tuple[int, int, int], Path]] = []
    for path in _OWNERSHIP_DIR.glob(_SNF_OWNERS_GLOB):
        if not path.is_file():
            continue
        key = _parse_snf_owners_filename(path)
        if key:
            candidates.append((key, path))
    if not candidates:
        return None
    return sorted(candidates, reverse=True)[0][1]


def snf_owners_release_month_year(path: Path | None = None) -> tuple[int, int] | None:
    """(year, month) parsed from the active SNF All Owners snapshot filename."""
    p = path or snf_owners_csv_path()
    if not p:
        return None
    parsed = _parse_snf_owners_filename(p)
    if not parsed:
        return None
    return parsed[0], parsed[1]


def _ownership_source_fields(path: Path | None) -> dict[str, str]:
    return {
        "source_file": path.name if path else "",
        "ownership_source": snf_owners_source_citation(path),
    }


_SQLITE_THREAD_LOCAL = threading.local()


def _sqlite_conn() -> sqlite3.Connection | None:
    """Per-thread read-only connection (gunicorn gthread workers share a process)."""
    if not _OWNERS_LOOKUP_DB.is_file():
        return None
    conn = getattr(_SQLITE_THREAD_LOCAL, "conn", None)
    if conn is None:
        conn = sqlite3.connect(
            f"file:{_OWNERS_LOOKUP_DB}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        _SQLITE_THREAD_LOCAL.conn = conn
    return conn


def _sqlite_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {str(k): row[k] for k in row.keys()}


def _sqlite_pac_in_column(pac: str, column: str) -> bool:
    conn = _sqlite_conn()
    if not conn:
        return False
    row = conn.execute(
        f'SELECT 1 FROM "{_OWNERS_TABLE}" WHERE "{column}" = ? LIMIT 1',
        (pac,),
    ).fetchone()
    return row is not None


def snf_owners_source_citation(path: Path | None = None) -> str:
    """Human-readable CMS source line (release month only — no filename in UI copy)."""
    p = path or snf_owners_csv_path()
    if not p:
        return "CMS owner data"
    ym = snf_owners_release_month_year(p)
    if ym:
        month = calendar.month_name[ym[1]]
        return f"CMS owner data ({month} {ym[0]} snapshot)"
    return "CMS owner data"


def _clean(val: Any) -> str:
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "") else s


def _pct_from_row(row: dict[str, Any]) -> str:
    return _clean(row.get("PERCENTAGE OWNERSHIP")) or _clean(row.get("PERCENTAGE OF OWNERSHIP"))


def _norm_org_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().upper())


def _owner_display_name(row: dict[str, Any]) -> str:
    org = _clean(row.get("ORGANIZATION NAME - OWNER"))
    if org:
        return format_org_display(org)
    parts = [
        _clean(row.get("FIRST NAME - OWNER")),
        _clean(row.get("MIDDLE NAME - OWNER")),
        _clean(row.get("LAST NAME - OWNER")),
    ]
    name = " ".join(p for p in parts if p)
    if not name:
        return "Unknown party"
    if _owner_party_type(row) == "Individual" and len(name) > 2 and name.upper() == name:
        return " ".join(w.capitalize() for w in name.split())
    return name


def _owner_party_type(row: dict[str, Any]) -> str:
    t = _clean(row.get("TYPE - OWNER")).upper()
    if t == "I":
        return "Individual"
    if t == "O":
        return "Organization"
    if _clean(row.get("ORGANIZATION NAME - OWNER")):
        return "Organization"
    return "Individual"


def _row_to_dict(row: pd.Series) -> dict[str, Any]:
    return {str(k): row[k] for k in row.index}


def _norm_ccn_key(raw: str) -> str:
    ccn = str(raw or "").strip()
    if "." in ccn:
        ccn = ccn.split(".")[0]
    return ccn.zfill(6)[-6:] if ccn and ccn.replace(".", "").isdigit() else ""


def _iter_provider_info_chunks(path: Path, usecols: list[str]) -> Iterator[pd.DataFrame]:
    """Chunked read_csv wrapper for pyright-friendly kwargs."""
    csv_kwargs: dict[str, Any] = {
        "filepath_or_buffer": path,
        "dtype": str,
        "low_memory": False,
        "encoding": "latin-1",
        "usecols": usecols,
        "chunksize": 100_000,
    }
    return cast(Iterator[pd.DataFrame], pd.read_csv(**csv_kwargs))


@lru_cache(maxsize=1)
def _legal_business_name_to_ccn() -> dict[str, str]:
    """CMS enrollment legal name (ORGANIZATION NAME) -> CCN via provider_info legal_business_name."""
    out: dict[str, str] = {}
    for path in provider_info_crosswalk_paths():
        try:
            header = pd.read_csv(path, nrows=0).columns.tolist()
            ccn_col = next((c for c in header if c.lower() in ("ccn", "provnum")), None)
            legal_col = next((c for c in header if c.lower() == "legal_business_name"), None)
            if not ccn_col or not legal_col:
                continue
            for chunk in _iter_provider_info_chunks(path, [ccn_col, legal_col]):
                for _, row in chunk.iterrows():
                    ccn = _norm_ccn_key(str(row.get(ccn_col) or ""))
                    legal = _norm_org_key(str(row.get(legal_col) or ""))
                    if legal and ccn and legal not in out:
                        out[legal] = ccn
        except Exception:
            pass
    return out


@lru_cache(maxsize=1)
def _facility_name_to_ccn() -> dict[str, str]:
    def norm(s: str) -> str:
        return _norm_org_key(s)

    out: dict[str, str] = dict(_legal_business_name_to_ccn())
    idx_path = _REPO / "search_index.json"
    if idx_path.is_file():
        try:
            data = json.loads(idx_path.read_text(encoding="utf-8"))
            for fac in data.get("f") or []:
                name = norm(str(fac.get("n") or ""))
                ccn = _norm_ccn_key(str(fac.get("c") or ""))
                if name and ccn and name not in out:
                    out[name] = ccn
        except Exception:
            pass
    for path in provider_info_crosswalk_paths():
        try:
            header = pd.read_csv(path, nrows=0).columns.tolist()
            ccn_col = next((c for c in header if c.lower() in ("ccn", "provnum")), None)
            if not ccn_col:
                continue
            name_cols = [c for c in ("provider_name", "Provider Name", "legal_business_name") if c in header]
            if not name_cols:
                continue
            read_cols = list({ccn_col, *name_cols})
            for chunk in _iter_provider_info_chunks(path, read_cols):
                for _, row in chunk.iterrows():
                    ccn = _norm_ccn_key(str(row.get(ccn_col) or ""))
                    if not ccn:
                        continue
                    for col in name_cols:
                        k = norm(str(row.get(col) or ""))
                        if k and k not in out:
                            out[k] = ccn
        except Exception:
            pass
    return out


_NAME_STOP = frozenset(
    {
        "THE", "AND", "FOR", "INC", "LLC", "CORP", "LTD", "OF", "A", "AN",
        "WEST", "EAST", "NORTH", "SOUTH", "HEALTHCARE", "HEALTH", "CARE",
        "CENTER", "NURSING", "HOME", "REHABILITATION", "REHAB", "SNF", "FACILITY",
    }
)


@lru_cache(maxsize=1)
def _search_index_facility_rows() -> tuple[tuple[str, str, str, str], ...]:
    """(normalized_name, ccn, state, city/y) from search_index.json."""
    rows: list[tuple[str, str, str, str]] = []
    idx_path = _REPO / "search_index.json"
    if not idx_path.is_file():
        return tuple()
    try:
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        for fac in data.get("f") or []:
            name = re.sub(r"\s+", " ", str(fac.get("n") or "").strip().upper())
            ccn = str(fac.get("c") or "").strip().zfill(6)[-6:]
            state = str(fac.get("s") or "").strip().upper()[:2]
            city = str(fac.get("y") or "").strip()
            if name and ccn:
                rows.append((name, ccn, state, city))
    except Exception:
        pass
    return tuple(rows)


@lru_cache(maxsize=1)
def _ccn_to_state_from_search_index() -> dict[str, str]:
    """CCN -> USPS state from search_index.json (works on Render without provider_info CSV)."""
    out: dict[str, str] = {}
    for _name, ccn, state, _city in _search_index_facility_rows():
        if ccn and state and ccn not in out:
            out[ccn] = state
    return out


def _fuzzy_ccn_for_facility_name(fac_name: str) -> str:
    """Best-effort CCN when enrollment legal name != provider DBA."""
    from ownership.owner_portfolio_metrics import _ccn_provider_lookup

    norm_name = re.sub(r"\s+", " ", str(fac_name or "").strip().upper())
    if not norm_name:
        return ""
    tokens = [t for t in re.findall(r"[A-Z]{4,}", norm_name) if t not in _NAME_STOP]
    if not tokens:
        return ""

    county_hint = ""
    m_county = re.search(r"([A-Z]{4,})\s+COUNTY", norm_name)
    if m_county:
        county_hint = m_county.group(1)

    provider_lookup = _ccn_provider_lookup()
    candidates: list[tuple[int, str]] = []
    for name, ccn, state, city in _search_index_facility_rows():
        name_tokens = {t for t in re.findall(r"[A-Z]{4,}", name) if t not in _NAME_STOP}
        score = sum(2 if t in name_tokens else 0 for t in tokens)
        pi = provider_lookup.get(ccn) or {}
        pi_county = re.sub(r"[^A-Z]", "", str(pi.get("county") or "").upper())
        if county_hint:
            hint_norm = re.sub(r"[^A-Z]", "", county_hint)
            if hint_norm and hint_norm in pi_county:
                score += 8
            city_u = city.upper()
            if county_hint in city_u or county_hint in name:
                score += 2
        if score > 0:
            candidates.append((score, ccn))

    if not candidates:
        return ""
    candidates.sort(key=lambda x: (-x[0], x[1]))
    top_score = candidates[0][0]
    top_ccns = {ccn for sc, ccn in candidates if sc == top_score}
    if len(top_ccns) == 1:
        return next(iter(top_ccns))
    if top_score >= 4:
        return candidates[0][1]
    return ""


def _resolve_ccn_with_method(fac_name: str) -> tuple[str, str]:
    """
    Resolve CCN for CMS ORGANIZATION NAME (enrollment legal name).

    Returns (ccn, method) where method is:
      legal_exact — provider_info legal_business_name exact match (used for PBJ metrics)
      name_exact  — DBA / search-index exact name match (link only; not used for metrics)
      fuzzy       — token-based guess (link only; flagged in UI)
      ""          — no match
    """
    key = _norm_org_key(fac_name)
    if not key:
        return "", ""
    legal_map = _legal_business_name_to_ccn()
    if key in legal_map:
        return legal_map[key], "legal_exact"
    name_ccn = _facility_name_to_ccn()
    if key in name_ccn:
        return name_ccn[key], "name_exact"
    fuzzy = _fuzzy_ccn_for_facility_name(fac_name)
    if fuzzy:
        return fuzzy, "fuzzy"
    return "", ""


def _resolve_ccn(fac_name: str, name_ccn: dict[str, str]) -> str:
    """Backward-compatible CCN resolver (ignores match method)."""
    del name_ccn
    return _resolve_ccn_with_method(fac_name)[0]


def _read_owners_csv_chunks(
    *,
    usecols: tuple[str, ...] | None = None,
    chunksize: int = 150_000,
) -> Iterator[pd.DataFrame]:
    """Typed wrapper for chunked pandas read_csv on the SNF all-owners file."""
    path = snf_owners_csv_path()
    if not path:
        return iter(())
    kwargs: dict[str, Any] = {
        "filepath_or_buffer": str(path),
        "dtype": str,
        "encoding": "latin-1",
        "low_memory": False,
        "chunksize": chunksize,
    }
    if usecols is not None:
        kwargs["usecols"] = usecols
    return cast(Iterator[pd.DataFrame], pd.read_csv(**kwargs))


_CSV_USECOLS: tuple[str, ...] = (
    ENROLLMENT_PAC_COL,
    OWNER_PAC_COL,
    "ORGANIZATION NAME",
    "ENROLLMENT ID",
    "ORGANIZATION NAME - OWNER",
    "DOING BUSINESS AS NAME - OWNER",
    "FIRST NAME - OWNER",
    "MIDDLE NAME - OWNER",
    "LAST NAME - OWNER",
    "TYPE - OWNER",
    "ROLE TEXT - OWNER",
    "ASSOCIATION DATE - OWNER",
    "STATE - OWNER",
    "CITY - OWNER",
    "PERCENTAGE OWNERSHIP",
)


@lru_cache(maxsize=256)
def _fetch_rows_for_pac(pac: str) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Rows where pac is enrollment ASSOCIATE ID, and where pac is owner ASSOCIATE ID - OWNER."""
    if len(pac) != 10:
        return (), ()

    conn = _sqlite_conn()
    if conn:
        try:
            enrollment_rows = [
                _sqlite_row_to_dict(r)
                for r in conn.execute(
                    f'SELECT * FROM "{_OWNERS_TABLE}" WHERE "{ENROLLMENT_PAC_COL}" = ?',
                    (pac,),
                )
            ]
            owner_rows = [
                _sqlite_row_to_dict(r)
                for r in conn.execute(
                    f'SELECT * FROM "{_OWNERS_TABLE}" WHERE "{OWNER_PAC_COL}" = ?',
                    (pac,),
                )
            ]
            return tuple(enrollment_rows), tuple(owner_rows)
        except Exception:
            pass

    path = snf_owners_csv_path()
    if not path:
        return (), ()

    enrollment_rows: list[dict[str, Any]] = []
    owner_rows: list[dict[str, Any]] = []

    try:
        header = pd.read_csv(
            str(path), dtype=str, encoding="latin-1", low_memory=False, nrows=0
        ).columns.tolist()
        cols = tuple(c for c in _CSV_USECOLS if c in header)
        for chunk in _read_owners_csv_chunks(usecols=cols, chunksize=150_000):
            if ENROLLMENT_PAC_COL in chunk.columns:
                en_mask = chunk[ENROLLMENT_PAC_COL].astype(str).apply(normalize_associate_id) == pac
                if en_mask.any():
                    enrollment_rows.extend(_row_to_dict(r) for _, r in chunk.loc[en_mask].iterrows())
            if OWNER_PAC_COL in chunk.columns:
                ow_mask = chunk[OWNER_PAC_COL].astype(str).apply(normalize_associate_id) == pac
                if ow_mask.any():
                    owner_rows.extend(_row_to_dict(r) for _, r in chunk.loc[ow_mask].iterrows())
    except Exception:
        return (), ()

    return tuple(enrollment_rows), tuple(owner_rows)


def classify_associate_id(associate_id: str) -> str:
    """
    Return profile class: enrollment | owner_control | both | none.
    """
    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return "none"
    en_rows, ow_rows = _fetch_rows_for_pac(pac)
    if en_rows and ow_rows:
        return "both"
    if en_rows:
        return "enrollment"
    if ow_rows:
        return "owner_control"
    return "none"


def associate_profile_url(associate_id: str, org_name: str = "") -> str:
    """URL for a CMS associate ID (enrollment or owner/control profile at /owners/{pac})."""
    pac = normalize_associate_id(associate_id)
    if len(pac) == 10:
        return f"/owners/{pac}"
    if (org_name or "").strip() or (associate_id or "").strip():
        return "/owner"
    return ""


def _owner_pac_in_lookup(pac: str) -> bool:
    pac = normalize_associate_id(pac)
    if len(pac) != 10:
        return False
    if _sqlite_conn():
        return _sqlite_pac_in_column(pac, OWNER_PAC_COL)
    return pac in _owner_control_pac_set()


@lru_cache(maxsize=1)
def _enrollment_pac_set() -> frozenset[str]:
    path = snf_owners_csv_path()
    if not path:
        return frozenset()
    pacs: set[str] = set()
    try:
        for chunk in _read_owners_csv_chunks(usecols=(ENROLLMENT_PAC_COL,), chunksize=200_000):
            for v in chunk[ENROLLMENT_PAC_COL].astype(str):
                p = normalize_associate_id(v)
                if len(p) == 10:
                    pacs.add(p)
    except Exception:
        pass
    return frozenset(pacs)


@lru_cache(maxsize=1)
def _owner_control_pac_set() -> frozenset[str]:
    path = snf_owners_csv_path()
    if not path:
        return frozenset()
    pacs: set[str] = set()
    try:
        for chunk in _read_owners_csv_chunks(usecols=(OWNER_PAC_COL,), chunksize=200_000):
            for v in chunk[OWNER_PAC_COL].astype(str):
                p = normalize_associate_id(v)
                if len(p) == 10:
                    pacs.add(p)
    except Exception:
        pass
    return frozenset(pacs)


def associate_id_kind_label(associate_id: str) -> str:
    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return "unknown"
    if _sqlite_conn():
        in_en = _sqlite_pac_in_column(pac, ENROLLMENT_PAC_COL)
        in_ow = _sqlite_pac_in_column(pac, OWNER_PAC_COL)
    else:
        in_en = pac in _enrollment_pac_set()
        in_ow = pac in _owner_control_pac_set()
    if in_en and in_ow:
        return "both"
    if in_en:
        return "enrollment"
    if in_ow:
        return "owner_control"
    return "unknown"


def _build_control_parties(enrollment_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    parties: dict[str, dict[str, Any]] = {}
    for row in enrollment_rows:
        owner_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
        if not owner_pac:
            continue
        if owner_pac not in parties:
            parties[owner_pac] = {
                "owner_associate_id": owner_pac,
                "name": _owner_display_name(row),
                "party_type": _owner_party_type(row),
                "roles": [],
                "pcts": [],
                "association_dates": [],
                "profile_url": associate_profile_url(owner_pac),
                "is_owner_control_pac": _owner_pac_in_lookup(owner_pac),
            }
        role_raw = _clean(row.get("ROLE TEXT - OWNER"))
        role = format_role_text(role_raw) if role_raw else ""
        pct = _pct_from_row(row)
        adate = _clean(row.get("ASSOCIATION DATE - OWNER"))
        if role and role not in parties[owner_pac]["roles"]:
            parties[owner_pac]["roles"].append(role)
        if pct and pct not in parties[owner_pac]["pcts"]:
            parties[owner_pac]["pcts"].append(pct)
        if adate and adate not in parties[owner_pac]["association_dates"]:
            parties[owner_pac]["association_dates"].append(adate)

    out = list(parties.values())
    out.sort(key=lambda x: (-len(x.get("roles") or []), x.get("name") or ""))
    return out


@lru_cache(maxsize=1)
def _enrollment_org_to_pac() -> dict[str, str]:
    """Normalized enrollment ORGANIZATION NAME -> ASSOCIATE ID."""
    if _ORG_INDEX_GZ.is_file():
        try:
            with gzip.open(_ORG_INDEX_GZ, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
    path = snf_owners_csv_path()
    if not path:
        return {}
    out: dict[str, str] = {}
    try:
        for chunk in _read_owners_csv_chunks(
            usecols=(ENROLLMENT_PAC_COL, "ORGANIZATION NAME", "DOING BUSINESS AS NAME - OWNER"),
            chunksize=200_000,
        ):
            for _, row in chunk.iterrows():
                pac = normalize_associate_id(row.get(ENROLLMENT_PAC_COL))
                if len(pac) != 10:
                    continue
                for col in ("ORGANIZATION NAME", "DOING BUSINESS AS NAME - OWNER"):
                    key = _norm_org_key(str(row.get(col) or ""))
                    if key and key not in out:
                        out[key] = pac
    except Exception:
        pass
    return out


@lru_cache(maxsize=1)
def _ccn_to_enrollment_pac() -> dict[str, str]:
    """CCN -> CMS enrollment ASSOCIATE ID (built from SNF All Owners org names + provider crosswalk)."""
    if _CCN_ENROLLMENT_INDEX_GZ.is_file():
        try:
            with gzip.open(_CCN_ENROLLMENT_INDEX_GZ, "rt", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                out: dict[str, str] = {}
                for ccn, val in raw.items():
                    ccn_norm = _norm_ccn_key(str(ccn))
                    if not ccn_norm:
                        continue
                    if isinstance(val, dict):
                        pac = normalize_associate_id(str(val.get("pac") or val.get("associate_id") or ""))
                    else:
                        pac = normalize_associate_id(str(val))
                    if len(pac) == 10:
                        out[ccn_norm] = pac
                if out:
                    return out
        except Exception:
            pass
    return {}


def _enrollment_pac_for_ccn_sqlite(ccn_norm: str, provider_name: str = "") -> str:
    """Targeted SQLite match for one CCN (no full-table scan). Uses DBA tokens from search index."""
    conn = _sqlite_conn()
    if not conn or not ccn_norm:
        return ""
    label = re.sub(r"\s+", " ", str(provider_name or "").strip().upper())
    if not label:
        for name, ccn, _state, _city in _search_index_facility_rows():
            if ccn == ccn_norm:
                label = name
                break
    tokens = sorted(
        {t for t in re.findall(r"[A-Z]{4,}", label) if t not in _NAME_STOP},
        key=len,
        reverse=True,
    )
    if not tokens:
        return ""
    for token in tokens[:3]:
        try:
            rows = conn.execute(
                f'SELECT DISTINCT "{ENROLLMENT_PAC_COL}", "ORGANIZATION NAME" FROM "{_OWNERS_TABLE}" '
                f'WHERE UPPER("ORGANIZATION NAME") LIKE ? LIMIT 40',
                (f"%{token}%",),
            ).fetchall()
        except Exception:
            continue
        for pac_raw, org_name in rows:
            resolved, _method = _resolve_ccn_with_method(str(org_name or ""))
            if _norm_ccn_key(resolved) == ccn_norm:
                pac = normalize_associate_id(str(pac_raw or ""))
                if len(pac) == 10:
                    return pac
    return ""


def _ownership_lookup_from_enrollment_pac(
    pac: str,
    *,
    matched_via: str,
) -> dict[str, Any] | None:
    from ownership.owner_portfolio_metrics import sort_control_parties_for_display

    if len(pac) != 10:
        return None
    en_rows, _ = _fetch_rows_for_pac(pac)
    if not en_rows:
        return None
    enrollment_name = _clean(en_rows[0].get("ORGANIZATION NAME")) or matched_via
    parties = sort_control_parties_for_display(_build_control_parties(en_rows))
    path = snf_owners_csv_path()
    return {
        "enrollment_pac": pac,
        "enrollment_name": enrollment_name,
        "enrollment_profile_url": associate_profile_url(pac),
        "control_parties": parties,
        "matched_via": matched_via,
        **_ownership_source_fields(path),
    }


@lru_cache(maxsize=1)
def _ccn_to_legal_business_name() -> dict[str, str]:
    """CCN -> CMS legal business name (from provider_info snapshots)."""
    out: dict[str, str] = {}
    for legal, ccn in _legal_business_name_to_ccn().items():
        ccn_norm = _norm_ccn_key(ccn)
        if ccn_norm and legal and ccn_norm not in out:
            out[ccn_norm] = legal
    return out


def lookup_cms_ownership_for_provider(
    provider_info_row: dict[str, Any] | None = None,
    *,
    provider_name: str = "",
    legal_business_name: str = "",
    ccn: str = "",
) -> dict[str, Any] | None:
    """
    Match facility to CMS SNF All Owners enrollment via legal/DBA name or CCN crosswalk.
    Returns enrollment PAC, display name, and deduped control parties.
    """
    pi = provider_info_row or {}
    ccn_norm = _norm_ccn_key(ccn) or _norm_ccn_key(str(pi.get("ccn") or pi.get("PROVNUM") or ""))
    legal = _clean(legal_business_name) or _clean(pi.get("legal_business_name"))
    if not legal and ccn_norm:
        legal = _ccn_to_legal_business_name().get(ccn_norm) or ""
    dba = _clean(provider_name) or _clean(pi.get("provider_name"))
    index = _enrollment_org_to_pac()
    tried: set[str] = set()
    for matched_name in (legal, dba):
        if not matched_name:
            continue
        pac = index.get(_norm_org_key(matched_name))
        if not pac or pac in tried:
            continue
        tried.add(pac)
        hit = _ownership_lookup_from_enrollment_pac(pac, matched_via=matched_name)
        if hit:
            return hit
    if ccn_norm:
        pac = _ccn_to_enrollment_pac().get(ccn_norm) or _enrollment_pac_for_ccn_sqlite(ccn_norm, dba)
        if pac and pac not in tried:
            hit = _ownership_lookup_from_enrollment_pac(pac, matched_via=f"ccn:{ccn_norm}")
            if hit:
                return hit
    return None


def _portfolio_enrollment_pacs(profile: dict[str, Any]) -> set[str]:
    pacs: set[str] = set()
    for fac in profile.get("facilities") or []:
        ep = normalize_associate_id(str(fac.get("enrollment_pac") or ""))
        if ep:
            pacs.add(ep)
    ow = profile.get("owner_control_section")
    if isinstance(ow, dict):
        for fac in ow.get("facilities") or []:
            ep = normalize_associate_id(str(fac.get("enrollment_pac") or ""))
            if ep:
                pacs.add(ep)
    return pacs


def _snf_coowners_on_shared_enrollments(
    enrollment_pacs: set[str],
    *,
    exclude_pac: str,
) -> list[dict[str, Any]]:
    """Other owner PACs on the same facility enrollment PACs (SNF All Owners)."""
    if not enrollment_pacs:
        return []
    exclude = normalize_associate_id(exclude_pac)
    target_pacs = [normalize_associate_id(p) for p in enrollment_pacs if len(normalize_associate_id(p)) == 10]
    if not target_pacs:
        return []

    conn = _sqlite_conn()
    if conn:
        shared: dict[str, set[str]] = {}
        names: dict[str, str] = {}
        try:
            placeholders = ",".join("?" * len(target_pacs))
            sql = (
                f'SELECT * FROM "{_OWNERS_TABLE}" WHERE "{ENROLLMENT_PAC_COL}" IN ({placeholders})'
            )
            for row in conn.execute(sql, target_pacs):
                d = _sqlite_row_to_dict(row)
                en_pac = normalize_associate_id(d.get(ENROLLMENT_PAC_COL))
                ow_pac = normalize_associate_id(d.get(OWNER_PAC_COL))
                if len(en_pac) != 10 or len(ow_pac) != 10 or ow_pac == exclude:
                    continue
                shared.setdefault(ow_pac, set()).add(en_pac)
                if ow_pac not in names:
                    names[ow_pac] = _owner_display_name(d)
        except Exception:
            shared = {}
        if shared:
            coowners: list[dict[str, Any]] = []
            for ow_pac, en_set in shared.items():
                coowners.append(
                    {
                        "associate_id": ow_pac,
                        "name": names.get(ow_pac) or ow_pac,
                        "count": len(en_set),
                        "profile_url": associate_profile_url(ow_pac),
                    }
                )
            coowners.sort(key=lambda x: (-int(x.get("count") or 0), str(x.get("name") or "")))
            return coowners

    path = snf_owners_csv_path()
    if not path:
        return []
    shared = {}
    names = {}
    try:
        header = pd.read_csv(
            str(path), dtype=str, encoding="latin-1", low_memory=False, nrows=0
        ).columns.tolist()
        cols = tuple(
            c
            for c in (
                ENROLLMENT_PAC_COL,
                OWNER_PAC_COL,
                "ORGANIZATION NAME - OWNER",
                "FIRST NAME - OWNER",
                "MIDDLE NAME - OWNER",
                "LAST NAME - OWNER",
            )
            if c in header
        )
        if ENROLLMENT_PAC_COL not in cols or OWNER_PAC_COL not in cols:
            return []
        for chunk in _read_owners_csv_chunks(usecols=cols, chunksize=150_000):
            en_norm = chunk[ENROLLMENT_PAC_COL].astype(str).apply(normalize_associate_id)
            mask = en_norm.isin(target_pacs)
            if not bool(mask.any()):
                continue
            for _, row in chunk.loc[mask].iterrows():
                en_pac = normalize_associate_id(row.get(ENROLLMENT_PAC_COL))
                ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
                if len(en_pac) != 10 or len(ow_pac) != 10 or ow_pac == exclude:
                    continue
                shared.setdefault(ow_pac, set()).add(en_pac)
                if ow_pac not in names:
                    names[ow_pac] = _owner_display_name(_row_to_dict(row))
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for ow_pac, en_set in shared.items():
        out.append(
            {
                "associate_id": ow_pac,
                "name": names.get(ow_pac) or ow_pac,
                "count": len(en_set),
                "profile_url": associate_profile_url(ow_pac),
            }
        )
    out.sort(key=lambda x: (-int(x.get("count") or 0), str(x.get("name") or "")))
    return out


_SOURCE_CHOW = "chow"
_SOURCE_SNF = "snf"


def build_related_associates(profile: dict[str, Any], *, limit: int = 20) -> list[dict[str, Any]]:
    """
    Parties that repeatedly appear with this PAC in CMS SNF All Owners and/or CHOW filings.
    """
    from collections import defaultdict

    pac = normalize_associate_id(profile.get("associate_id"))
    if len(pac) != 10:
        return []

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "associate_id": "",
            "name": "",
            "count": 0,
            "snf_shared": 0,
            "chow_count": 0,
            "sources": set(),
            "profile_url": "",
        }
    )

    def _key(associate_id: str, name: str) -> str | None:
        oid = normalize_associate_id(associate_id)
        if len(oid) == 10 and oid != pac:
            return oid
        norm = str(name or "").strip().upper()
        if not norm or norm == str(profile.get("display_name") or "").strip().upper():
            return None
        return f"name:{norm}"

    def _add(
        associate_id: str,
        name: str,
        source: str,
        profile_url: str = "",
        *,
        weight: int = 1,
    ) -> None:
        key = _key(associate_id, name)
        if not key:
            return
        row = buckets[key]
        w = max(1, int(weight))
        row["count"] += w
        if source == _SOURCE_CHOW:
            row["chow_count"] += w
        elif source == _SOURCE_SNF:
            row["snf_shared"] += w
        row["sources"].add(source)
        oid = normalize_associate_id(associate_id)
        if len(oid) == 10:
            row["associate_id"] = oid
            row["profile_url"] = profile_url or associate_profile_url(oid)
        if name and (not row["name"] or len(str(name)) > len(str(row["name"]))):
            row["name"] = format_org_display(name)

    for rec in profile.get("chow_transactions") or []:
        role = str(rec.get("chow_role") or "")
        if role == "buyer":
            _add(
                str(rec.get("seller_associate_id") or ""),
                str(rec.get("seller_org_name") or rec.get("seller_normalized") or ""),
                _SOURCE_CHOW,
                str(rec.get("seller_owner_url") or ""),
            )
        else:
            _add(
                str(rec.get("buyer_associate_id") or ""),
                str(rec.get("buyer_org_name") or rec.get("buyer_normalized") or ""),
                _SOURCE_CHOW,
                str(rec.get("buyer_owner_url") or ""),
            )

    kind = str(profile.get("profile_kind") or "")
    # SNF co-owners on shared enrollments (owner/control portfolios); enrollment pages list control parties.
    if kind in ("owner_control", "both", "chow_only"):
        for co in _snf_coowners_on_shared_enrollments(
            _portfolio_enrollment_pacs(profile),
            exclude_pac=pac,
        ):
            _add(
                str(co.get("associate_id") or ""),
                str(co.get("name") or ""),
                _SOURCE_SNF,
                str(co.get("profile_url") or ""),
                weight=int(co.get("count") or 1),
            )
    if kind in ("owner_control", "chow_only"):
        for party in profile.get("control_parties") or []:
            _add(
                str(party.get("owner_associate_id") or ""),
                str(party.get("name") or ""),
                _SOURCE_SNF,
                str(party.get("profile_url") or ""),
            )

    out: list[dict[str, Any]] = []
    for row in buckets.values():
        if row["count"] < 1:
            continue
        sources = sorted(row["sources"])
        out.append(
            {
                "associate_id": row["associate_id"],
                "name": row["name"] or row["associate_id"] or "Unknown",
                "count": row["count"],
                "snf_shared": int(row.get("snf_shared") or 0),
                "chow_count": int(row.get("chow_count") or 0),
                "sources": sources,
                "source_label": " · ".join(sources),
                "profile_url": row["profile_url"],
            }
        )
    out.sort(
        key=lambda x: (
            -max(int(x.get("snf_shared") or 0), int(x.get("chow_count") or 0)),
            str(x.get("name") or ""),
        )
    )
    return out[: max(1, limit)]


def _attach_portfolio_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Enrich facilities with provider info; add portfolio + control-party summaries."""
    from ownership.owner_portfolio_metrics import (
        build_portfolio_summary,
        enrich_facilities,
        sort_control_parties_for_display,
        summarize_control_parties,
    )

    profile["related_associates"] = build_related_associates(profile)

    if profile.get("facilities"):
        profile["facilities"] = enrich_facilities(profile["facilities"])
        profile["portfolio_summary"] = build_portfolio_summary(profile["facilities"])
        profile["states"] = sorted(
            {str(f.get("state") or "").upper() for f in profile["facilities"] if f.get("state")}
        )
    if profile.get("control_parties"):
        profile["control_parties_summary"] = summarize_control_parties(profile["control_parties"])
        profile["control_parties"] = sort_control_parties_for_display(profile["control_parties"])
    ow = profile.get("owner_control_section")
    if isinstance(ow, dict) and ow.get("facilities"):
        ow["facilities"] = enrich_facilities(ow["facilities"])
        ow["portfolio_summary"] = build_portfolio_summary(ow["facilities"])
    from ownership.owner_facility_map import attach_facility_map_context

    return attach_facility_map_context(profile)


def _facility_state_for_row(row: dict[str, Any], ccn: str) -> str:
    """Prefer facility CCN state (provider_info or search_index); fall back to owner address state."""
    ccn_norm = _norm_ccn_key(ccn)
    if ccn_norm:
        try:
            from ownership.owner_portfolio_metrics import _ccn_provider_lookup

            prov = _ccn_provider_lookup().get(ccn_norm) or {}
            st = str(prov.get("state") or "").strip().upper()[:2]
            if st:
                return st
        except Exception:
            pass
        st = _ccn_to_state_from_search_index().get(ccn_norm) or ""
        if st:
            return st
    return _clean(row.get("STATE - OWNER")).upper()[:2]


_STATE_TOP_OWNERS_GZ = _OWNERSHIP_DIR / "state_top_owners.json.gz"


@lru_cache(maxsize=1)
def _load_state_top_owners_index() -> dict[str, list[dict[str, Any]]] | None:
    if not _STATE_TOP_OWNERS_GZ.is_file():
        return None
    try:
        with gzip.open(_STATE_TOP_OWNERS_GZ, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return None
        return {str(k).upper()[:2]: list(v) for k, v in raw.items() if isinstance(v, list)}
    except Exception:
        return None


@lru_cache(maxsize=16)
def top_owner_organizations_for_state(state_code: str, limit: int = 8) -> list[dict[str, Any]]:
    """Owner/control parties with the most linked nursing homes in a state (CMS SNF All Owners)."""
    st = (state_code or "").strip().upper()[:2]
    if not st:
        return []
    prebuilt = _load_state_top_owners_index()
    if prebuilt is not None:
        return list(prebuilt.get(st) or [])[: max(1, limit)]

    from ownership.owner_portfolio_metrics import _ccn_provider_lookup

    prov_lookup = _ccn_provider_lookup()
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()
    owner_ccns: dict[str, set[str]] = {}
    owner_meta: dict[str, dict[str, Any]] = {}

    def _ingest(row: dict[str, Any]) -> None:
        fac = _clean(row.get("ORGANIZATION NAME"))
        if not fac:
            return
        key = _norm_org_key(fac)
        ccn = legal_ccn.get(key) or name_ccn.get(key) or _resolve_ccn_with_method(fac)[0]
        if not ccn:
            return
        ccn_norm = _norm_ccn_key(ccn)
        prov = prov_lookup.get(ccn_norm) or {}
        fac_st = str(prov.get("state") or "").strip().upper()[:2]
        if not fac_st:
            fac_st = _ccn_to_state_from_search_index().get(ccn_norm) or ""
        if fac_st != st:
            return
        ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
        if len(ow_pac) != 10:
            return
        owner_ccns.setdefault(ow_pac, set()).add(ccn_norm)
        if ow_pac not in owner_meta:
            owner_meta[ow_pac] = {
                "associate_id": ow_pac,
                "name": _owner_display_name(row),
                "profile_url": associate_profile_url(ow_pac),
            }

    conn = _sqlite_conn()
    if conn:
        try:
            for sql_row in conn.execute(f'SELECT * FROM "{_OWNERS_TABLE}"'):
                _ingest(_sqlite_row_to_dict(sql_row))
        except Exception:
            pass
    else:
        cols = (
            ENROLLMENT_PAC_COL,
            OWNER_PAC_COL,
            "ORGANIZATION NAME",
            "ORGANIZATION NAME - OWNER",
            "FIRST NAME - OWNER",
            "MIDDLE NAME - OWNER",
            "LAST NAME - OWNER",
            "TYPE - OWNER",
        )
        try:
            for chunk in _read_owners_csv_chunks(usecols=cols, chunksize=200_000):
                for _, r in chunk.iterrows():
                    _ingest(_row_to_dict(r))
        except Exception:
            pass

    out: list[dict[str, Any]] = []
    for pac, ccns in owner_ccns.items():
        meta = owner_meta.get(pac) or {}
        out.append(
            {
                "associate_id": pac,
                "name": meta.get("name") or pac,
                "facility_count": len(ccns),
                "profile_url": meta.get("profile_url") or associate_profile_url(pac),
            }
        )
    out.sort(key=lambda x: (-int(x.get("facility_count") or 0), str(x.get("name") or "")))
    return out[: max(1, limit)]


def _build_enrollment_profile(pac: str, enrollment_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    path = snf_owners_csv_path()
    first = enrollment_rows[0]
    display_name = format_org_display(
        _clean(first.get("ORGANIZATION NAME")) or "Unknown enrollment organization"
    )
    enrollment_ids = sorted({_clean(r.get("ENROLLMENT ID")) for r in enrollment_rows if _clean(r.get("ENROLLMENT ID"))})
    facilities: list[dict[str, str]] = []
    seen_fac: set[str] = set()
    for row in enrollment_rows:
        fac_name = _clean(row.get("ORGANIZATION NAME"))
        if not fac_name:
            continue
        key = fac_name.upper()
        if key in seen_fac:
            continue
        seen_fac.add(key)
        ccn, match_method = _resolve_ccn_with_method(fac_name)
        facilities.append(
            {
                "facility_name": fac_name,
                "enrollment_id": _clean(row.get("ENROLLMENT ID")),
                "state": _facility_state_for_row(row, ccn or ""),
                "city": _clean(row.get("CITY - OWNER")),
                "ccn": ccn or "",
                "ccn_match_method": match_method,
            }
        )
    facilities.sort(key=lambda x: (x.get("state") or "", x.get("facility_name") or ""))

    control_parties = _build_control_parties(enrollment_rows)
    states = sorted({f["state"] for f in facilities if f.get("state")})

    from ownership.chow_lookup import chow_records_for_associate_id

    chow_rows = chow_records_for_associate_id(pac, limit=25)

    profile = {
        "associate_id": pac,
        "profile_kind": "enrollment",
        "display_name": display_name,
        "owner_type": "Provider / enrollment organization",
        "enrollment_pac_label": "Enrollment PAC",
        "owner_pac_label": "Owner PAC",
        "enrollment_ids": enrollment_ids,
        "facility_count": len(facilities),
        "facilities": facilities,
        "control_parties": control_parties,
        "states": states,
        **_ownership_source_fields(path),
        "is_chow_only": False,
        "chow_transactions": chow_rows,
    }
    return _attach_portfolio_metrics(profile)


def _build_owner_control_profile(pac: str, owner_rows: list[dict[str, Any]]) -> dict[str, Any]:
    path = snf_owners_csv_path()
    first = owner_rows[0]
    display_name = format_org_display(_owner_display_name(first))
    owner_type = _owner_party_type(first)
    facilities: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in owner_rows:
        fac_name = _clean(row.get("ORGANIZATION NAME"))
        if not fac_name:
            continue
        key = fac_name.upper()
        if key in seen:
            continue
        seen.add(key)
        ccn, match_method = _resolve_ccn_with_method(fac_name)
        facilities.append(
            {
                "facility_name": fac_name,
                "state": _facility_state_for_row(row, ccn or ""),
                "city": _clean(row.get("CITY - OWNER")),
                "role": format_role_text(_clean(row.get("ROLE TEXT - OWNER"))),
                "association_date": _clean(row.get("ASSOCIATION DATE - OWNER")),
                "pct": _pct_from_row(row),
                "enrollment_id": _clean(row.get("ENROLLMENT ID")),
                "enrollment_pac": normalize_associate_id(row.get(ENROLLMENT_PAC_COL)),
                "ccn": ccn or "",
                "ccn_match_method": match_method,
            }
        )
    facilities.sort(key=lambda x: (x.get("state") or "", x.get("facility_name") or ""))
    states = sorted({f["state"] for f in facilities if f.get("state")})

    from ownership.chow_lookup import chow_records_for_associate_id

    chow_rows = chow_records_for_associate_id(pac, limit=25)

    profile = {
        "associate_id": pac,
        "profile_kind": "owner_control",
        "display_name": display_name,
        "owner_type": owner_type,
        "enrollment_pac_label": "Enrollment PAC",
        "owner_pac_label": "Owner PAC",
        "facility_count": len(facilities),
        "facilities": facilities,
        "states": states,
        **_ownership_source_fields(path),
        "is_chow_only": False,
        "chow_transactions": chow_rows,
    }
    return _attach_portfolio_metrics(profile)


def _build_both_profile(
    pac: str,
    enrollment_rows: list[dict[str, Any]],
    owner_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    en_profile = _build_enrollment_profile(pac, enrollment_rows)
    ow_profile = _build_owner_control_profile(pac, owner_rows)
    en_profile["profile_kind"] = "both"
    en_profile["owner_control_section"] = ow_profile
    return _attach_portfolio_metrics(en_profile)


def load_owner_profile_chow_fallback(associate_id: str) -> dict[str, Any] | None:
    """CHOW-only when PAC is not in all-owners enrollment or owner/control columns."""
    from ownership.chow_lookup import chow_party_label_for_associate_id, chow_records_for_associate_id

    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return None

    chow_rows = chow_records_for_associate_id(pac, limit=50)
    if not chow_rows:
        return None

    party = chow_party_label_for_associate_id(pac) or {}
    display_name = format_org_display(party.get("display_name") or "Unknown organization")

    facilities: list[dict[str, str]] = []
    seen_ccn: set[str] = set()
    for rec in chow_rows:
        ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
        if ccn and ccn in seen_ccn:
            continue
        if ccn:
            seen_ccn.add(ccn)
        fac_name = (
            rec.get("facility_display_name")
            or rec.get("buyer_dba_name")
            or rec.get("buyer_org_name")
            or "—"
        )
        role = rec.get("chow_role") or "party"
        role_label = "Buyer (CHOW)" if role == "buyer" else "Seller (CHOW)"
        facilities.append(
            {
                "facility_name": str(fac_name),
                "state": str(rec.get("state") or "").strip(),
                "city": "",
                "role": role_label,
                "association_date": str(rec.get("effective_date") or "").strip(),
                "pct": "—",
                "enrollment_id": "",
                "ccn": ccn,
                "chow_type": str(rec.get("chow_type") or ""),
            }
        )

    facilities.sort(key=lambda x: (x.get("state") or "", x.get("facility_name") or ""))
    states = sorted({f["state"] for f in facilities if f.get("state")})

    profile = {
        "associate_id": pac,
        "profile_kind": "chow_only",
        "display_name": display_name,
        "owner_type": "CHOW enrollment party (not in current all-owners file)",
        "enrollment_pac_label": "Enrollment PAC",
        "owner_pac_label": "Owner PAC",
        "facility_count": len(facilities),
        "facilities": facilities,
        "states": states,
        "source_file": "CMS SNF Change of Ownership (CHOW)",
        "is_chow_only": True,
        "chow_transactions": chow_rows,
        "chow_party_role": party.get("role") or "",
    }
    return _attach_portfolio_metrics(profile)


def load_owner_profile_resolved(associate_id: str) -> dict[str, Any] | None:
    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return None

    enrollment_rows, owner_rows = _fetch_rows_for_pac(pac)
    en_list = list(enrollment_rows)
    ow_list = list(owner_rows)

    if en_list and ow_list:
        return _build_both_profile(pac, en_list, ow_list)
    if en_list:
        return _build_enrollment_profile(pac, en_list)
    if ow_list:
        return _build_owner_control_profile(pac, ow_list)
    return load_owner_profile_chow_fallback(pac)


# Back-compat alias
def load_owner_profile(associate_id: str) -> dict[str, Any] | None:
    pac = normalize_associate_id(associate_id)
    if len(pac) != 10:
        return None
    _, owner_rows = _fetch_rows_for_pac(pac)
    if not owner_rows:
        return None
    return _build_owner_control_profile(pac, list(owner_rows))


_CT_OWNER_SEARCH_GZ = _OWNERSHIP_DIR / "ct_owner_search_catalog.json.gz"


def _build_public_owner_search_catalog_entries() -> list[dict[str, str]]:
    """
    Searchable PACs for ownership profiles in public-launch states (Connecticut).
    Prefer ct_owner_search_catalog.json.gz from scripts/build_snf_owners_index.py on deploy.
    """
    from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES

    catalog: dict[str, dict[str, Any]] = {}
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()

    def _maybe_add(pac: str, display: str, fac_st: str) -> None:
        if len(pac) != 10 or fac_st not in OWNERSHIP_PUBLIC_STATES:
            return
        name = _clean(display)
        if not name:
            return
        entry = catalog.setdefault(pac, {"name": name, "states": set()})
        if len(name) > len(str(entry.get("name") or "")):
            entry["name"] = name
        entry["states"].add(fac_st)

    def _ingest_row(row: dict[str, Any]) -> None:
        fac = _clean(row.get("ORGANIZATION NAME"))
        if not fac:
            return
        key = _norm_org_key(fac)
        ccn = legal_ccn.get(key) or name_ccn.get(key) or _resolve_ccn_with_method(fac)[0]
        fac_st = _facility_state_for_row(row, ccn or "")
        en_pac = normalize_associate_id(row.get(ENROLLMENT_PAC_COL))
        ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
        _maybe_add(en_pac, fac, fac_st)
        if ow_pac:
            _maybe_add(ow_pac, _owner_display_name(row), fac_st)

    conn = _sqlite_conn()
    if conn:
        try:
            for sql_row in conn.execute(f'SELECT * FROM "{_OWNERS_TABLE}"'):
                _ingest_row(_sqlite_row_to_dict(sql_row))
        except Exception:
            pass
    else:
        path = snf_owners_csv_path()
        if path:
            try:
                header = pd.read_csv(
                    str(path), dtype=str, encoding="latin-1", low_memory=False, nrows=0
                ).columns.tolist()
                cols = tuple(c for c in _CSV_USECOLS if c in header)
                for chunk in _read_owners_csv_chunks(usecols=cols, chunksize=150_000):
                    for _, r in chunk.iterrows():
                        _ingest_row(_row_to_dict(r))
            except Exception:
                pass

    rows: list[dict[str, str]] = []
    for pac, entry in sorted(catalog.items(), key=lambda x: str(x[1].get("name") or "").lower()):
        name = _clean(str(entry.get("name") or ""))
        states = sorted(str(s) for s in (entry.get("states") or set()) if s)
        if not name or not states:
            continue
        rows.append({"associate_id": pac, "name": name, "states": ",".join(states)})
    return rows


def write_public_owner_search_catalog_file() -> int:
    """Persist CT (public-state) owner search catalog for fast /owners hub loads."""
    rows = _build_public_owner_search_catalog_entries()
    _OWNERSHIP_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(_CT_OWNER_SEARCH_GZ, "wt", encoding="utf-8") as f:
        json.dump(rows, f, separators=(",", ":"))
    return len(rows)


@lru_cache(maxsize=1)
def _public_owner_search_catalog() -> tuple[tuple[str, str, str, frozenset[str]], ...]:
    if _CT_OWNER_SEARCH_GZ.is_file():
        try:
            with gzip.open(_CT_OWNER_SEARCH_GZ, "rt", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                entries: list[tuple[str, str, str, frozenset[str]]] = []
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    pac = normalize_associate_id(str(item.get("associate_id") or ""))
                    name = _clean(str(item.get("name") or ""))
                    if len(pac) != 10 or not name:
                        continue
                    states_raw = item.get("states") or item.get("state") or ""
                    if isinstance(states_raw, list):
                        states = frozenset(
                            str(s).strip().upper()[:2] for s in states_raw if str(s).strip()
                        )
                    else:
                        states = frozenset(
                            s.strip().upper()[:2]
                            for s in str(states_raw).split(",")
                            if s.strip()
                        )
                    if not states:
                        states = frozenset({"CT", "NY"})
                    entries.append((pac, name, _norm_org_key(name), states))
                if entries:
                    return tuple(entries)
        except Exception:
            pass
    built = _build_public_owner_search_catalog_entries()
    out: list[tuple[str, str, str, frozenset[str]]] = []
    for r in built:
        pac = normalize_associate_id(r.get("associate_id"))
        name = _clean(str(r.get("name") or ""))
        if len(pac) != 10 or not name:
            continue
        states = frozenset(
            s.strip().upper()[:2] for s in str(r.get("states") or "").split(",") if s.strip()
        )
        if not states:
            continue
        out.append((pac, name, _norm_org_key(name), states))
    return tuple(out)


def public_owner_associate_ids_for_sitemap() -> list[str]:
    """10-digit PACs classified indexable (see ownership.owner_indexability)."""
    from ownership.owner_indexability import public_owner_associate_ids_for_sitemap as _indexable_pacs

    return _indexable_pacs()


def search_public_owner_profiles(
    query: str,
    *,
    limit: int = 12,
    state_code: str | None = None,
) -> list[dict[str, str]]:
    """Name or 10-digit PAC search for publicly launched ownership states (CT + NY)."""
    q = (query or "").strip()
    if not q:
        return []
    catalog = _public_owner_search_catalog()
    if not catalog:
        return []

    st_filter = (state_code or "").strip().upper()[:2] or None

    def _in_state(states: frozenset[str]) -> bool:
        return not st_filter or st_filter in states

    pac_q = normalize_associate_id(q)
    if len(pac_q) == 10 and pac_q.isdigit():
        for pac, name, _, states in catalog:
            if pac == pac_q and _in_state(states):
                return [
                    {
                        "associate_id": pac,
                        "name": name,
                        "profile_url": associate_profile_url(pac),
                    }
                ]
        return []

    qnorm = _norm_org_key(q)
    if len(qnorm) < 2:
        return []

    scored: list[tuple[int, int, str, str]] = []
    for pac, name, key, states in catalog:
        if not _in_state(states):
            continue
        if qnorm not in key and qnorm not in _norm_org_key(name):
            continue
        rank = 0 if key.startswith(qnorm) else (1 if qnorm in key[: max(len(qnorm) + 4, 8)] else 2)
        scored.append((rank, len(name), pac, name))
    scored.sort(key=lambda x: (x[0], x[1], x[3].lower()))
    out: list[dict[str, str]] = []
    for _, _, pac, name in scored[: max(1, limit)]:
        out.append(
            {
                "associate_id": pac,
                "name": name,
                "profile_url": associate_profile_url(pac),
            }
        )
    return out
