"""
Canonical ownership release store (current-state materializations).

Build path:
  raw SNF_All_Owners CSV
    -> snf_owners (raw normalized rows; existing)
    -> current_relationships / facility_current / pac_* tables (this module)
    -> search catalog, state indexes, indexability cache, sitemap inputs

Downstream builders must consume these tables instead of re-scanning CSV or
constructing full owner profiles for index/search/sitemap work.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES
from ownership.role_classification import (
    CATEGORY_OWNERSHIP,
    CATEGORY_OPERATIONAL,
    accumulate_facility_link,
    classify_owner_record,
    facility_link_counts_from_buckets,
    intersect_facility_link_buckets,
)

_OWNERSHIP_DIR = Path(__file__).resolve().parent
_REPO = _OWNERSHIP_DIR.parent
DB_PATH = _OWNERSHIP_DIR / "snf_owners_lookup.sqlite"
TABLE_RAW = "snf_owners"
SOURCE_RELEASE_DEFAULT = "SNF_All_Owners_2026.07.17"

REL_TABLE = "current_relationships"
FAC_TABLE = "facility_current"
PAC_TAX_TABLE = "pac_publication_taxonomy"
PAC_IDX_TABLE = "pac_indexability"
SEARCH_TABLE = "owner_search_lite"
OI_TABLE = "ownership_interest_current"
PAC_CCN_TABLE = "pac_to_ccns"
CCN_PAC_TABLE = "ccn_to_pacs"
META_TABLE = "canonical_build_meta"

_CHOW_RECENT_YEARS = 3


def _log(msg: str) -> None:
    print(f"[canonical_store] {msg}", flush=True)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def apply_build_pragmas(conn: sqlite3.Connection) -> None:
    """Offline-build pragmas (not for multi-writer production durability)."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")


def drop_materialized_tables(conn: sqlite3.Connection) -> None:
    for name in (
        REL_TABLE,
        FAC_TABLE,
        PAC_TAX_TABLE,
        PAC_IDX_TABLE,
        SEARCH_TABLE,
        OI_TABLE,
        PAC_CCN_TABLE,
        CCN_PAC_TABLE,
        META_TABLE,
    ):
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')


def create_schema(conn: sqlite3.Connection, *, with_indexes: bool = False) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS "{REL_TABLE}" (
            pac TEXT NOT NULL,
            ccn TEXT NOT NULL,
            link_kind TEXT NOT NULL,
            person_org TEXT,
            display_name TEXT,
            raw_role_code TEXT,
            raw_role_text TEXT,
            role_category TEXT,
            ownership_pct REAL,
            association_date TEXT,
            facility_org_name TEXT,
            state TEXT,
            ccn_method TEXT,
            source_release TEXT
        );
        CREATE TABLE IF NOT EXISTS "{FAC_TABLE}" (
            ccn TEXT PRIMARY KEY,
            name TEXT,
            state TEXT,
            city TEXT,
            has_abuse INTEGER DEFAULT 0,
            sff_status TEXT,
            active_roster INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS "{OI_TABLE}" (
            pac TEXT NOT NULL,
            ccn TEXT NOT NULL,
            ownership_pct REAL,
            association_date TEXT,
            display_name TEXT,
            state TEXT,
            PRIMARY KEY (pac, ccn)
        );
        CREATE TABLE IF NOT EXISTS "{PAC_CCN_TABLE}" (
            pac TEXT NOT NULL,
            ccn TEXT NOT NULL,
            link_kind TEXT NOT NULL,
            role_category TEXT,
            state TEXT,
            PRIMARY KEY (pac, ccn, link_kind, role_category)
        );
        CREATE TABLE IF NOT EXISTS "{CCN_PAC_TABLE}" (
            ccn TEXT NOT NULL,
            pac TEXT NOT NULL,
            link_kind TEXT NOT NULL,
            role_category TEXT,
            PRIMARY KEY (ccn, pac, link_kind, role_category)
        );
        CREATE TABLE IF NOT EXISTS "{PAC_TAX_TABLE}" (
            pac TEXT PRIMARY KEY,
            display_name TEXT,
            person_org TEXT,
            profile_kind TEXT,
            segment TEXT,
            schema_type TEXT,
            categories TEXT,
            has_ownership_interest INTEGER,
            has_control INTEGER,
            has_enrollment INTEGER,
            oi_facility_count INTEGER,
            any_facility_count INTEGER,
            state_count INTEGER,
            states TEXT
        );
        CREATE TABLE IF NOT EXISTS "{PAC_IDX_TABLE}" (
            pac TEXT PRIMARY KEY,
            classification TEXT NOT NULL,
            reason TEXT,
            flags TEXT,
            owner_name TEXT,
            facility_count INTEGER,
            active_facility_count INTEGER,
            slug TEXT
        );
        CREATE TABLE IF NOT EXISTS "{SEARCH_TABLE}" (
            pac TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT,
            slug TEXT,
            states TEXT,
            classification TEXT,
            segment TEXT,
            schema_type TEXT
        );
        CREATE TABLE IF NOT EXISTS "{META_TABLE}" (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    if with_indexes:
        create_access_indexes(conn)


def create_access_indexes(conn: sqlite3.Connection) -> None:
    stmts = [
        f'CREATE INDEX IF NOT EXISTS idx_rel_pac ON "{REL_TABLE}" (pac)',
        f'CREATE INDEX IF NOT EXISTS idx_rel_ccn ON "{REL_TABLE}" (ccn)',
        f'CREATE INDEX IF NOT EXISTS idx_rel_state ON "{REL_TABLE}" (state)',
        f'CREATE INDEX IF NOT EXISTS idx_rel_cat ON "{REL_TABLE}" (role_category)',
        f'CREATE INDEX IF NOT EXISTS idx_rel_pac_ccn ON "{REL_TABLE}" (pac, ccn)',
        f'CREATE INDEX IF NOT EXISTS idx_rel_ccn_pac ON "{REL_TABLE}" (ccn, pac)',
        f'CREATE INDEX IF NOT EXISTS idx_oi_pac ON "{OI_TABLE}" (pac)',
        f'CREATE INDEX IF NOT EXISTS idx_oi_ccn ON "{OI_TABLE}" (ccn)',
        f'CREATE INDEX IF NOT EXISTS idx_pac_ccn_pac ON "{PAC_CCN_TABLE}" (pac)',
        f'CREATE INDEX IF NOT EXISTS idx_ccn_pac_ccn ON "{CCN_PAC_TABLE}" (ccn)',
        f'CREATE INDEX IF NOT EXISTS idx_search_norm ON "{SEARCH_TABLE}" (name_norm)',
        f'CREATE INDEX IF NOT EXISTS idx_idx_class ON "{PAC_IDX_TABLE}" (classification)',
    ]
    for s in stmts:
        conn.execute(s)


def _owner_display_name(row: dict[str, Any]) -> str:
    from ownership.owner_profile import _owner_display_name as _disp

    return str(_disp(row) or "").strip()


def _load_facility_enrichment() -> dict[str, dict[str, Any]]:
    """CCN -> {state, city, name, has_abuse, sff_status, active_roster}."""
    from ownership.owner_indexability import _active_provider_ccns, _norm_ccn
    from ownership.owner_portfolio_metrics import (
        _parse_abuse_flag,
        _provider_info_col_map,
        _provider_info_row_dict,
        ownership_provider_info_paths,
    )
    import pandas as pd

    active = _active_provider_ccns()
    out: dict[str, dict[str, Any]] = {}
    for path in ownership_provider_info_paths():
        if not path.is_file():
            continue
        header = list(pd.read_csv(path, nrows=0, dtype=str).columns)
        col_map = _provider_info_col_map(header)
        usecols = [c for c in col_map.values() if c]
        for chunk in pd.read_csv(path, dtype=str, low_memory=False, usecols=usecols, chunksize=50_000):
            for _, row in chunk.iterrows():
                info = _provider_info_row_dict(row, col_map)
                ccn_col = col_map.get("ccn")
                raw = row.get(ccn_col) if ccn_col else ""
                ccn = _norm_ccn(raw)
                if not ccn:
                    continue
                prev = out.get(ccn) or {}
                merged = {
                    "ccn": ccn,
                    "name": info.get("provider_name") or prev.get("name") or "",
                    "state": info.get("state") or prev.get("state") or "",
                    "city": info.get("city") or prev.get("city") or "",
                    "has_abuse": int(
                        bool(_parse_abuse_flag(info.get("abuse_icon")))
                        or bool(prev.get("has_abuse"))
                    ),
                    "sff_status": info.get("sff_status") or prev.get("sff_status") or "",
                    "active_roster": int(ccn in active),
                }
                out[ccn] = merged
        break
    # Ensure active roster CCNs exist even if missing from provider CSV.
    from ownership.owner_profile import _ccn_to_state_from_search_index

    ccn_state = _ccn_to_state_from_search_index()
    for ccn in active:
        if ccn not in out:
            out[ccn] = {
                "ccn": ccn,
                "name": "",
                "state": ccn_state.get(ccn) or "",
                "city": "",
                "has_abuse": 0,
                "sff_status": "",
                "active_roster": 1,
            }
        else:
            out[ccn]["active_roster"] = 1
    return out


def _recent_chow_by_pac() -> dict[str, list[dict[str, Any]]]:
    from ownership.chow_lookup import _load_index
    from ownership.owner_profile import normalize_associate_id

    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * _CHOW_RECENT_YEARS)
    by_pac: dict[str, list[dict[str, Any]]] = defaultdict(list)
    idx = _load_index()
    for pac, recs in (idx.get("by_associate_id") or {}).items():
        pac_n = normalize_associate_id(pac)
        if len(pac_n) != 10:
            continue
        for rec in recs or []:
            raw = str(rec.get("effective_date") or "")[:10]
            dt = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            if dt and dt >= cutoff:
                by_pac[pac_n].append(
                    {
                        "effective_date": raw,
                        "state": str(rec.get("state") or "").strip().upper()[:2],
                        "ccn": str(rec.get("ccn") or "").strip(),
                    }
                )
    return by_pac


def _shared_oi_pacs(oi_pairs: Iterable[tuple[str, str]]) -> set[str]:
    """PACs that share ownership-interest on at least one CCN with another PAC."""
    by_ccn: dict[str, set[str]] = defaultdict(set)
    for pac, ccn in oi_pairs:
        by_ccn[ccn].add(pac)
    out: set[str] = set()
    for pacs in by_ccn.values():
        if len(pacs) >= 2:
            out.update(pacs)
    return out


def _schema_type_for_person_org(person_org: str) -> str:
    t = (person_org or "").strip().upper()
    if t in ("I", "INDIVIDUAL", "PERSON"):
        return "Person"
    return "Organization"


def materialize_canonical_store(
    *,
    db_path: Path | None = None,
    source_release: str | None = None,
) -> dict[str, Any]:
    """
    One-pass materialization of current-state ownership tables from snf_owners.
    Returns timing / row counts for the build report.
    """
    from ownership.owner_profile import (
        ENROLLMENT_PAC_COL,
        OWNER_PAC_COL,
        _ccn_to_state_from_search_index,
        _enrollment_to_ccn_bridge,
        _facility_name_to_ccn,
        _legal_business_name_to_ccn,
        _norm_ccn_key,
        _norm_org_key,
        _resolve_ccn_with_method,
        _sqlite_row_to_dict,
        associate_profile_url,
        normalize_associate_id,
        owner_display_slug,
    )
    from ownership.owner_indexability import (
        classify_owner_profile,
        is_suppress_owner_name,
    )
    from ownership.publication_taxonomy import classify_publication_segment

    db = db_path or DB_PATH
    if not db.is_file():
        raise FileNotFoundError(f"Missing owners DB: {db}")

    stats: dict[str, Any] = {"db": str(db), "stages": {}}
    t_all = time.perf_counter()

    t0 = time.perf_counter()
    facility_info = _load_facility_enrichment()
    stats["stages"]["facility_enrichment_s"] = round(time.perf_counter() - t0, 3)
    stats["facility_current_rows"] = len(facility_info)

    t0 = time.perf_counter()
    chow_by_pac = _recent_chow_by_pac()
    stats["stages"]["chow_index_s"] = round(time.perf_counter() - t0, 3)
    stats["chow_pacs_recent"] = len(chow_by_pac)

    t0 = time.perf_counter()
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()
    ccn_state = _ccn_to_state_from_search_index()
    org_ccn_cache: dict[str, tuple[str, str]] = {}
    e2c_bridge = _enrollment_to_ccn_bridge()
    stats["stages"]["crosswalk_load_s"] = round(time.perf_counter() - t0, 3)

    release = source_release or SOURCE_RELEASE_DEFAULT
    conn = connect(db)
    apply_build_pragmas(conn)
    try:
        drop_materialized_tables(conn)
        create_schema(conn, with_indexes=False)
        conn.commit()

        # Insert facility_current
        t0 = time.perf_counter()
        conn.executemany(
            f'INSERT OR REPLACE INTO "{FAC_TABLE}" '
            "(ccn, name, state, city, has_abuse, sff_status, active_roster) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f["ccn"],
                    f.get("name") or "",
                    f.get("state") or "",
                    f.get("city") or "",
                    int(f.get("has_abuse") or 0),
                    f.get("sff_status") or "",
                    int(f.get("active_roster") or 0),
                )
                for f in facility_info.values()
            ],
        )
        conn.commit()
        stats["stages"]["facility_insert_s"] = round(time.perf_counter() - t0, 3)

        # Single scan of snf_owners -> relationships
        t0 = time.perf_counter()
        rel_rows: list[tuple[Any, ...]] = []
        oi_rows: dict[tuple[str, str], tuple[Any, ...]] = {}
        pac_ccn_rows: set[tuple[str, str, str, str, str]] = set()
        ccn_pac_rows: set[tuple[str, str, str, str]] = set()

        # PAC aggregates
        pac_names: dict[str, str] = {}
        pac_types: dict[str, str] = {}
        pac_cats: dict[str, set[str]] = defaultdict(set)
        pac_ccns_any: dict[str, set[str]] = defaultdict(set)
        pac_ccns_oi: dict[str, set[str]] = defaultdict(set)
        pac_states: dict[str, set[str]] = defaultdict(set)
        pac_has_enrollment: set[str] = set()
        pac_has_owner_link: set[str] = set()
        pac_has_control: set[str] = set()
        owner_link_buckets: dict[str, dict[str, set[str]]] = {}
        by_state_owners: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        total_by_pac: dict[str, set[str]] = defaultdict(set)

        raw_n = 0
        unresolved = 0
        for sql_row in conn.execute(f'SELECT * FROM "{TABLE_RAW}"'):
            row = _sqlite_row_to_dict(sql_row)
            raw_n += 1
            fac = str(row.get("ORGANIZATION NAME") or "").strip()
            if not fac:
                continue

            eid_raw = str(row.get("ENROLLMENT ID") or "").strip()
            eid = eid_raw if eid_raw and eid_raw.lower() not in ("nan", "none", "") else ""
            ccn_from_bridge = _norm_ccn_key(e2c_bridge.get(eid, "")) if eid else ""

            if ccn_from_bridge:
                ccn = ccn_from_bridge
                method = "enrollment_exact"
            else:
                key = _norm_org_key(fac)
                if key in org_ccn_cache:
                    ccn, method = org_ccn_cache[key]
                else:
                    ccn = legal_ccn.get(key) or name_ccn.get(key) or ""
                    method = "legal_exact" if key in legal_ccn else ("name_exact" if key in name_ccn else "")
                    if not ccn:
                        ccn, method = _resolve_ccn_with_method(fac)
                    org_ccn_cache[key] = (ccn or "", method or "")
            if not ccn:
                unresolved += 1
                continue
            ccn_norm = _norm_ccn_key(ccn)
            fac_info = facility_info.get(ccn_norm) or {}
            fac_st = (
                (fac_info.get("state") or "").strip().upper()[:2]
                or ccn_state.get(ccn_norm)
                or ""
            )
            role_info = classify_owner_record(row)
            cat = str(role_info.get("role_category") or "")
            pct = role_info.get("ownership_pct")
            assoc = str(row.get("ASSOCIATION DATE - OWNER") or "").strip()
            ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
            en_pac = normalize_associate_id(row.get(ENROLLMENT_PAC_COL))
            ow_name = _owner_display_name(row)
            person_org = str(row.get("TYPE - OWNER") or "").strip()

            def _emit(
                pac: str,
                link_kind: str,
                display: str,
                p_org: str,
                *,
                role_code: str = "",
                role_text: str = "",
                role_cat: str = "",
                own_pct: float | None = None,
                assoc_date: str = "",
            ) -> None:
                if len(pac) != 10:
                    return
                use_cat = role_cat or cat
                use_pct = own_pct if own_pct is not None else pct
                use_assoc = assoc_date if assoc_date != "" or link_kind == "enrollment" else assoc
                if link_kind == "enrollment":
                    use_cat = "administrative_disclosure"
                    use_pct = None
                    use_assoc = ""
                    role_code = ""
                    role_text = ""
                rel_rows.append(
                    (
                        pac,
                        ccn_norm,
                        link_kind,
                        p_org,
                        display,
                        role_code or (role_info.get("role_code") or ""),
                        role_text or (role_info.get("role_text_raw") or ""),
                        use_cat,
                        use_pct,
                        use_assoc if link_kind != "enrollment" else "",
                        fac,
                        fac_st,
                        method,
                        release,
                    )
                )
                pac_ccn_rows.add((pac, ccn_norm, link_kind, use_cat or "", fac_st))
                ccn_pac_rows.add((ccn_norm, pac, link_kind, use_cat or ""))
                if display and (
                    pac not in pac_names
                    or len(display) > len(pac_names.get(pac) or "")
                ):
                    pac_names[pac] = display
                if p_org and pac not in pac_types:
                    pac_types[pac] = p_org
                if use_cat:
                    pac_cats[pac].add(use_cat)
                pac_ccns_any[pac].add(ccn_norm)
                if fac_st:
                    pac_states[pac].add(fac_st)
                if use_cat == CATEGORY_OWNERSHIP and link_kind == "owner":
                    pac_ccns_oi[pac].add(ccn_norm)
                    oi_rows[(pac, ccn_norm)] = (
                        pac,
                        ccn_norm,
                        use_pct,
                        use_assoc,
                        display,
                        fac_st,
                    )
                if use_cat == CATEGORY_OPERATIONAL and link_kind == "owner":
                    pac_has_control.add(pac)
                if link_kind == "enrollment":
                    pac_has_enrollment.add(pac)
                else:
                    pac_has_owner_link.add(pac)

            if len(ow_pac) == 10:
                _emit(ow_pac, "owner", ow_name, person_org)
                if fac_st:
                    accumulate_facility_link(owner_link_buckets, ow_pac, ccn_norm, row)
                    by_state_owners[fac_st][ow_pac].add(ccn_norm)
                    total_by_pac[ow_pac].add(ccn_norm)
            if len(en_pac) == 10:
                # Enrollment PAC is the facility enrollment associate.
                _emit(en_pac, "enrollment", fac, "O")

            if len(rel_rows) >= 50_000:
                conn.executemany(
                    f'INSERT INTO "{REL_TABLE}" VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    rel_rows,
                )
                rel_rows.clear()

        if rel_rows:
            conn.executemany(
                f'INSERT INTO "{REL_TABLE}" VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                rel_rows,
            )
        conn.executemany(
            f'INSERT OR REPLACE INTO "{OI_TABLE}" VALUES (?,?,?,?,?,?)',
            list(oi_rows.values()),
        )
        conn.executemany(
            f'INSERT OR IGNORE INTO "{PAC_CCN_TABLE}" VALUES (?,?,?,?,?)',
            list(pac_ccn_rows),
        )
        conn.executemany(
            f'INSERT OR IGNORE INTO "{CCN_PAC_TABLE}" VALUES (?,?,?,?)',
            list(ccn_pac_rows),
        )
        conn.commit()
        stats["stages"]["relationship_scan_s"] = round(time.perf_counter() - t0, 3)
        stats["raw_rows_scanned"] = raw_n
        stats["org_names_resolved"] = len(org_ccn_cache)
        stats["org_names_unresolved_rows"] = unresolved
        stats["relationship_rows"] = conn.execute(
            f'SELECT COUNT(*) FROM "{REL_TABLE}"'
        ).fetchone()[0]
        stats["oi_rows"] = len(oi_rows)
        stats["unique_pacs"] = len(pac_names)

        shared_oi = _shared_oi_pacs(oi_rows.keys())

        # Taxonomy + indexability from materialized features (no full profiles)
        t0 = time.perf_counter()
        tax_rows: list[tuple[Any, ...]] = []
        idx_rows: list[tuple[Any, ...]] = []
        search_rows: list[tuple[Any, ...]] = []
        indexability_cache_rows: list[dict[str, Any]] = []

        all_pacs = sorted(set(pac_names) | set(chow_by_pac))
        for pac in all_pacs:
            name = pac_names.get(pac) or ""
            if not name and pac in chow_by_pac:
                name = pac  # CHOW-only placeholder; may suppress
            cats = pac_cats.get(pac) or set()
            states = sorted(pac_states.get(pac) or set())
            ccns = sorted(pac_ccns_any.get(pac) or set())
            oi_ccns = pac_ccns_oi.get(pac) or set()
            has_en = pac in pac_has_enrollment
            has_ow = pac in pac_has_owner_link
            if has_en and has_ow:
                kind = "both"
            elif has_en:
                kind = "enrollment"
            elif has_ow:
                kind = "owner"
            elif pac in chow_by_pac:
                kind = "chow"
            else:
                kind = "owner"

            facilities = []
            for ccn in ccns:
                info = facility_info.get(ccn) or {}
                st = (info.get("state") or "").strip().upper()[:2] or (
                    next((s for s in states if s), "")
                )
                # Prefer ownership category if present on this CCN.
                role_cat = ""
                if ccn in oi_ccns:
                    role_cat = CATEGORY_OWNERSHIP
                elif pac in pac_has_control:
                    role_cat = CATEGORY_OPERATIONAL
                elif cats:
                    role_cat = next(iter(cats))
                facilities.append(
                    {
                        "ccn": ccn,
                        "state": st,
                        "pbj_matched": bool(info.get("active_roster")),
                        "has_abuse": bool(info.get("has_abuse")),
                        "sff_status": info.get("sff_status") or "",
                        "role_category": role_cat,
                    }
                )

            chow_recs = chow_by_pac.get(pac) or []
            related = []
            if pac in shared_oi:
                related.append({"shared_ownership_interest": True})

            # control_parties means OTHER managing parties on an enrollment profile,
            # not "this PAC itself holds a control role". Do not fake this flag.
            control_parties: list[dict[str, Any]] = []

            profile = {
                "associate_id": pac,
                "display_name": name,
                "states": states,
                "facilities": facilities,
                "portfolio_summary": {
                    "n_facilities": len(ccns),
                    "n_states": len(states),
                },
                "chow_transactions": chow_recs,
                "related_associates": related,
                "control_parties": control_parties,
                "profile_kind": kind,
                "is_chow_only": kind == "chow" and not ccns,
                "owner_control_section": {"facilities": facilities} if has_ow else None,
            }

            segment = classify_publication_segment(profile)
            schema_type = _schema_type_for_person_org(pac_types.get(pac) or "")
            if kind == "chow" and not ccns:
                schema_type = "Organization"

            tax_rows.append(
                (
                    pac,
                    name,
                    pac_types.get(pac) or "",
                    kind,
                    segment,
                    schema_type,
                    ",".join(sorted(cats)),
                    int(bool(oi_ccns)),
                    int(pac in pac_has_control),
                    int(has_en),
                    len(oi_ccns),
                    len(ccns),
                    len(states),
                    ",".join(states),
                )
            )

            classification, reason, meta = classify_owner_profile(profile)
            flags = meta.get("flags") or []
            slug = owner_display_slug(name) if name and not is_suppress_owner_name(name) else ""
            idx_rows.append(
                (
                    pac,
                    classification,
                    reason,
                    ",".join(flags),
                    name,
                    meta.get("facility_count") or len(ccns),
                    meta.get("active_facility_count") or 0,
                    slug,
                )
            )
            indexability_cache_rows.append(
                {
                    "associate_id": pac,
                    "owner_name": name,
                    "facility_count": meta.get("facility_count") or len(ccns),
                    "active_facility_count": meta.get("active_facility_count") or 0,
                    "flags": flags,
                    "classification": classification,
                    "reason": reason,
                }
            )

            # Search: public-state PAC with usable name; prefer index/noindex over suppress
            public_states = [s for s in states if s in OWNERSHIP_PUBLIC_STATES]
            if public_states and name and not is_suppress_owner_name(name):
                if classification != "suppress":
                    search_rows.append(
                        (
                            pac,
                            name,
                            _norm_org_key(name),
                            slug or owner_display_slug(name),
                            ",".join(public_states),
                            classification,
                            segment,
                            schema_type,
                        )
                    )

        conn.executemany(
            f'INSERT OR REPLACE INTO "{PAC_TAX_TABLE}" VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            tax_rows,
        )
        conn.executemany(
            f'INSERT OR REPLACE INTO "{PAC_IDX_TABLE}" VALUES (?,?,?,?,?,?,?,?)',
            idx_rows,
        )
        conn.executemany(
            f'INSERT OR REPLACE INTO "{SEARCH_TABLE}" VALUES (?,?,?,?,?,?,?,?)',
            search_rows,
        )
        conn.commit()
        stats["stages"]["taxonomy_indexability_s"] = round(time.perf_counter() - t0, 3)
        stats["pac_taxonomy_rows"] = len(tax_rows)
        stats["search_lite_rows"] = len(search_rows)
        from ownership.owner_indexability import summarize_owner_indexability_rows

        stats["indexability"] = summarize_owner_indexability_rows(indexability_cache_rows)

        t0 = time.perf_counter()
        create_access_indexes(conn)
        conn.commit()
        stats["stages"]["create_indexes_s"] = round(time.perf_counter() - t0, 3)

        # Persist gzip artifacts from materialized tables (single write path)
        t0 = time.perf_counter()
        _write_derived_artifacts_from_memory(
            by_state_owners=by_state_owners,
            total_by_pac=total_by_pac,
            owner_link_buckets=owner_link_buckets,
            pac_names=pac_names,
            indexability_cache_rows=indexability_cache_rows,
            search_rows=search_rows,
        )
        stats["stages"]["artifact_write_s"] = round(time.perf_counter() - t0, 3)

        meta = {
            "source_release": release,
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stats": json.dumps(stats),
        }
        conn.executemany(
            f'INSERT OR REPLACE INTO "{META_TABLE}" VALUES (?, ?)',
            list(meta.items()),
        )
        conn.commit()
    finally:
        conn.close()

    stats["stages"]["total_s"] = round(time.perf_counter() - t_all, 3)
    _log(
        f"done total_s={stats['stages']['total_s']} "
        f"rels={stats.get('relationship_rows')} "
        f"pacs={stats.get('unique_pacs')} "
        f"index={stats.get('indexability')}"
    )
    return stats


def _write_gzip_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _write_derived_artifacts_from_memory(
    *,
    by_state_owners: dict[str, dict[str, set[str]]],
    total_by_pac: dict[str, set[str]],
    owner_link_buckets: dict[str, dict[str, set[str]]],
    pac_names: dict[str, str],
    indexability_cache_rows: list[dict[str, Any]],
    search_rows: list[tuple[Any, ...]],
) -> None:
    from ownership.state_owner_index import STATE_OWNER_INDEX_STATES
    from ownership.owner_profile import associate_profile_url
    from ownership.owner_indexability import (
        _write_owner_indexability_cache,
        write_owner_indexability_audit_csv,
        log_owner_indexability_summary,
    )

    # state_owner_index
    state_index: dict[str, list[dict[str, Any]]] = {}
    for st in sorted(STATE_OWNER_INDEX_STATES):
        owners = by_state_owners.get(st) or {}
        rows: list[dict[str, Any]] = []
        for pac, ccns in owners.items():
            name = pac_names.get(pac) or pac
            buckets = owner_link_buckets.get(pac) or {"any": set(ccns)}
            state_buckets = intersect_facility_link_buckets(buckets, ccns)
            counts = facility_link_counts_from_buckets(state_buckets)
            counts["facility_count"] = len(ccns)
            rows.append(
                {
                    "associate_id": pac,
                    "name": name,
                    "profile_url": associate_profile_url(pac, name),
                    "facility_count_total": len(total_by_pac.get(pac) or set()),
                    **counts,
                }
            )
        rows.sort(key=lambda x: (-int(x.get("facility_count") or 0), str(x.get("name") or "")))
        state_index[st] = rows
    _write_gzip_json(_OWNERSHIP_DIR / "state_owner_index.json.gz", state_index)

    # state_top_owners (top 8 per state)
    top: dict[str, list[dict[str, Any]]] = {}
    for st, rows in state_index.items():
        top[st] = [
            {
                "associate_id": r["associate_id"],
                "name": r["name"],
                "profile_url": r["profile_url"],
                "facility_count": r.get("facility_count") or 0,
                "facility_count_ownership_interest": r.get("facility_count_ownership_interest") or 0,
                "facility_count_operational_control": r.get("facility_count_operational_control") or 0,
            }
            for r in rows[:8]
        ]
    _write_gzip_json(_OWNERSHIP_DIR / "state_top_owners.json.gz", top)

    # search catalog (lightweight; no profiles)
    catalog = [
        {
            "associate_id": r[0],
            "name": r[1],
            "states": r[4],
            "slug": r[3],
            "classification": r[5],
            "segment": r[6],
            "schema_type": r[7],
        }
        for r in search_rows
    ]
    catalog.sort(key=lambda x: str(x.get("name") or "").lower())
    _write_gzip_json(_OWNERSHIP_DIR / "ct_owner_search_catalog.json.gz", catalog)

    _write_owner_indexability_cache(indexability_cache_rows)
    write_owner_indexability_audit_csv(indexability_cache_rows)
    log_owner_indexability_summary(indexability_cache_rows)


def refresh_indexability_from_canonical(*, db_path: Path | None = None) -> dict[str, int]:
    """Rebuild gzip indexability cache from pac_indexability table (no profiles)."""
    from ownership.owner_indexability import (
        _write_owner_indexability_cache,
        write_owner_indexability_audit_csv,
        log_owner_indexability_summary,
        summarize_owner_indexability_rows,
    )

    conn = connect(db_path)
    try:
        rows = []
        for r in conn.execute(
            f'SELECT pac, classification, reason, flags, owner_name, '
            f'facility_count, active_facility_count FROM "{PAC_IDX_TABLE}"'
        ):
            rows.append(
                {
                    "associate_id": r["pac"],
                    "classification": r["classification"],
                    "reason": r["reason"],
                    "flags": [f for f in str(r["flags"] or "").split(",") if f],
                    "owner_name": r["owner_name"] or "",
                    "facility_count": r["facility_count"] or 0,
                    "active_facility_count": r["active_facility_count"] or 0,
                }
            )
    finally:
        conn.close()
    _write_owner_indexability_cache(rows)
    write_owner_indexability_audit_csv(rows)
    log_owner_indexability_summary(rows)
    return summarize_owner_indexability_rows(rows)


def national_oi_ranking(*, limit: int = 25, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Largest ownership-interest portfolios from ownership_interest_current."""
    conn = connect(db_path)
    try:
        q = f"""
        SELECT pac, COUNT(DISTINCT ccn) AS oi_n,
               MAX(display_name) AS name,
               COUNT(DISTINCT CASE WHEN state != '' THEN state END) AS state_n
        FROM "{OI_TABLE}"
        GROUP BY pac
        ORDER BY oi_n DESC, name ASC
        LIMIT ?
        """
        out = []
        for r in conn.execute(q, (limit,)):
            pac = r["pac"]
            any_n = conn.execute(
                f'SELECT COUNT(DISTINCT ccn) FROM "{PAC_CCN_TABLE}" WHERE pac=?',
                (pac,),
            ).fetchone()[0]
            person_org = ""
            tax = conn.execute(
                f'SELECT person_org, display_name FROM "{PAC_TAX_TABLE}" WHERE pac=?',
                (pac,),
            ).fetchone()
            if tax:
                person_org = tax["person_org"] or ""
                name = tax["display_name"] or r["name"]
            else:
                name = r["name"]
            out.append(
                {
                    "associate_id": pac,
                    "name": name,
                    "person_org": person_org,
                    "oi_facility_count": r["oi_n"],
                    "any_facility_count": any_n,
                    "state_count": r["state_n"],
                }
            )
        return out
    finally:
        conn.close()
