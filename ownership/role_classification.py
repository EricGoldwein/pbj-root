"""
CMS SNF All Owners records include both ownership interests and managing-control
relationships. PBJ320 classifies role codes into plain-language categories for
display and sorting. These categories are interpretive and should not be treated
as independent legal conclusions.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

ROLE_CODE_COL = "ROLE CODE - OWNER"
ROLE_TEXT_COL = "ROLE TEXT - OWNER"
ASSOC_DATE_COL = "ASSOCIATION DATE - OWNER"
PCT_COL = "PERCENTAGE OWNERSHIP"
OWNER_PAC_COL = "ASSOCIATE ID - OWNER"

CATEGORY_OPERATIONAL = "operational_control"
CATEGORY_OWNERSHIP = "ownership_interest"
CATEGORY_GOVERNANCE = "corporate_governance"
CATEGORY_ADMIN = "administrative_disclosure"
CATEGORY_FINANCIAL = "financial_interest"
CATEGORY_OTHER = "other"

# Recommended display order (highest sort rank first).
CATEGORY_RANK: dict[str, int] = {
    CATEGORY_OPERATIONAL: 6,
    CATEGORY_OWNERSHIP: 5,
    CATEGORY_GOVERNANCE: 4,
    CATEGORY_ADMIN: 3,
    CATEGORY_FINANCIAL: 2,
    CATEGORY_OTHER: 1,
}

CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_OPERATIONAL: "Operational/control",
    CATEGORY_OWNERSHIP: "Ownership interest",
    CATEGORY_GOVERNANCE: "Corporate governance",
    CATEGORY_ADMIN: "Administrative/disclosed party",
    CATEGORY_FINANCIAL: "Financial interest",
    CATEGORY_OTHER: "Other disclosed role",
}

PRIMARY_ROLE_LABELS: dict[str, str] = {
    CATEGORY_OPERATIONAL: "Operational/managerial control",
    CATEGORY_OWNERSHIP: "Ownership interest",
    CATEGORY_GOVERNANCE: "Corporate officer/director",
    CATEGORY_ADMIN: "ADP of the SNF",
    CATEGORY_FINANCIAL: "Financial interest",
    CATEGORY_OTHER: "Other disclosed role",
}

OPERATIONAL_CODES = frozenset({"43", "63", "25", "42"})
OWNERSHIP_CODES = frozenset({"01", "34", "35", "85", "86"})
GOVERNANCE_CODES = frozenset({"40", "41"})
ADMIN_CODES = frozenset({"72"})
FINANCIAL_CODES = frozenset({"36", "37"})

CODE_TO_CATEGORY: dict[str, str] = {}
for code in OPERATIONAL_CODES:
    CODE_TO_CATEGORY[code] = CATEGORY_OPERATIONAL
for code in OWNERSHIP_CODES:
    CODE_TO_CATEGORY[code] = CATEGORY_OWNERSHIP
for code in GOVERNANCE_CODES:
    CODE_TO_CATEGORY[code] = CATEGORY_GOVERNANCE
for code in ADMIN_CODES:
    CODE_TO_CATEGORY[code] = CATEGORY_ADMIN
for code in FINANCIAL_CODES:
    CODE_TO_CATEGORY[code] = CATEGORY_FINANCIAL

# Within-category tie-break (higher = more prominent).
CODE_PRIORITY: dict[str, int] = {
    "43": 100,
    "63": 95,
    "25": 90,
    "42": 85,
    "34": 88,
    "35": 87,
    "01": 80,
    "85": 78,
    "86": 77,
    "40": 70,
    "41": 65,
    "72": 55,
    "36": 45,
    "37": 40,
}

_DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%Y%m%d",
    "%m-%d-%Y",
)


def normalize_role_code(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return ""
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    if len(digits) >= 2:
        return digits[-2:].zfill(2)
    return digits.zfill(2)


def parse_ownership_pct(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip().replace("%", "").replace(",", "")
    if not s or s.lower() in ("nan", "none", "—", "-", "n/a"):
        return None
    try:
        v = float(s)
        return v if v >= 0 else None
    except ValueError:
        return None


def parse_association_date(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s[:10] if len(s) > 10 and fmt != "%Y%m%d" else s, fmt)
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        mo, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000 if yr < 50 else 1900
        try:
            return datetime(yr, mo, day)
        except ValueError:
            return None
    return None


def _category_from_role_text(text: str) -> str:
    low = str(text or "").strip().lower()
    if not low:
        return CATEGORY_OTHER
    if "operational" in low and ("managerial" in low or "manager" in low):
        return CATEGORY_OPERATIONAL
    if "managing control" in low or "managing employee" in low:
        return CATEGORY_OPERATIONAL
    if "w-2 managing" in low or "w2 managing" in low:
        return CATEGORY_OPERATIONAL
    if "ownership interest" in low or "direct ownership" in low or "indirect ownership" in low:
        return CATEGORY_OWNERSHIP
    if "5%" in low and ("owner" in low or "ownership" in low):
        return CATEGORY_OWNERSHIP
    if "corporate officer" in low or "corporate director" in low:
        return CATEGORY_GOVERNANCE
    if low.startswith("adp") or "adp of the snf" in low:
        return CATEGORY_ADMIN
    if "mortgage interest" in low or "security interest" in low:
        return CATEGORY_FINANCIAL
    return CATEGORY_OTHER


def classify_owner_record(row: dict[str, Any]) -> dict[str, Any]:
    """Classify one CMS SNF All Owners row (or compatible dict)."""
    code = normalize_role_code(row.get(ROLE_CODE_COL))
    role_text_raw = str(row.get(ROLE_TEXT_COL) or row.get("role") or "").strip()
    category = CODE_TO_CATEGORY.get(code) if code else ""
    if not category:
        category = _category_from_role_text(role_text_raw)
    priority = CODE_PRIORITY.get(code, 10)
    if category == CATEGORY_OTHER and not code:
        priority = 5
    display_role_text = role_text_raw
    primary = PRIMARY_ROLE_LABELS.get(category, CATEGORY_LABELS.get(category, "Other disclosed role"))
    if code == "40":
        primary = "Corporate officer"
    elif code == "41":
        primary = "Corporate director"
    return {
        "role_code": code,
        "role_text_raw": role_text_raw,
        "role_category": category,
        "role_category_label": CATEGORY_LABELS.get(category, "Other disclosed role"),
        "role_priority": priority,
        "is_operational_control": category == CATEGORY_OPERATIONAL,
        "is_ownership_interest": category == CATEGORY_OWNERSHIP,
        "is_corporate_governance": category == CATEGORY_GOVERNANCE,
        "is_administrative_disclosure": category == CATEGORY_ADMIN,
        "is_financial_interest": category == CATEGORY_FINANCIAL,
        "display_role_text": display_role_text,
        "primary_role_label": primary,
        "ownership_pct": parse_ownership_pct(row.get(PCT_COL) or row.get("pct")),
        "association_date": parse_association_date(
            row.get(ASSOC_DATE_COL) or row.get("association_date")
        ),
    }


def _pick_primary_classification(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    if not classifications:
        return classify_owner_record({})
    return max(
        classifications,
        key=lambda c: (
            CATEGORY_RANK.get(str(c.get("role_category") or ""), 0),
            int(c.get("role_priority") or 0),
            float(c.get("ownership_pct") or -1),
        ),
    )


def party_consolidation_key(row: dict[str, Any], *, owner_pac: str = "") -> str:
    pac = (owner_pac or str(row.get(OWNER_PAC_COL) or "")).strip()
    if pac:
        digits = re.sub(r"\D", "", pac)
        if len(digits) >= 9:
            return f"pac:{digits[-10:].zfill(10)}"
    name = str(
        row.get("name")
        or row.get("ORGANIZATION NAME - OWNER")
        or ""
    ).strip()
    ptype = str(row.get("party_type") or row.get("TYPE - OWNER") or "").strip()
    norm = re.sub(r"[^a-z0-9]+", "", name.lower())
    return f"name:{norm}:{ptype.lower()}"


def consolidate_owner_rows(
    rows: list[dict[str, Any]],
    *,
    build_party: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Merge CMS rows for the same owner on one enrollment.
    build_party(key, rows) -> party dict; default builds a minimal consolidated party.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = party_consolidation_key(row)
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for key, group in groups.items():
        if build_party is not None:
            out.append(build_party(key, group))
        else:
            out.append(build_consolidated_party_from_rows(key, group))
    return out


def build_consolidated_party_from_rows(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = [classify_owner_record(r) for r in rows]
    primary = _pick_primary_classification(classifications)
    role_texts: list[str] = []
    role_codes: list[str] = []
    pcts: list[str] = []
    dates_raw: list[str] = []
    max_pct: float | None = None
    earliest: datetime | None = None

    for r, c in zip(rows, classifications):
        rt = str(c.get("display_role_text") or "").strip()
        if rt and rt not in role_texts:
            role_texts.append(rt)
        code = str(c.get("role_code") or "")
        if code and code not in role_codes:
            role_codes.append(code)
        pct_val = c.get("ownership_pct")
        if pct_val is not None:
            max_pct = pct_val if max_pct is None else max(max_pct, pct_val)
            pct_s = f"{pct_val:g}%" if pct_val == int(pct_val) else f"{pct_val:g}%"
            if pct_s not in pcts:
                pcts.append(pct_s)
        raw_pct = str(r.get(PCT_COL) or r.get("pct") or "").strip()
        if raw_pct and raw_pct.lower() not in ("nan", "none") and raw_pct not in pcts:
            pcts.append(raw_pct if "%" in raw_pct else f"{raw_pct}%")
        ad = str(r.get(ASSOC_DATE_COL) or r.get("association_date") or "").strip()
        if ad and ad not in dates_raw:
            dates_raw.append(ad)
        dt = c.get("association_date")
        if isinstance(dt, datetime):
            earliest = dt if earliest is None else min(earliest, dt)

    dates_raw.sort(
        key=lambda d: parse_association_date(d) or datetime.min,
    )
    return {
        "consolidation_key": key,
        "role_codes": role_codes,
        "roles": role_texts,
        "pcts": pcts,
        "association_dates": dates_raw,
        "association_date_earliest": earliest,
        "max_ownership_pct": max_pct,
        **{k: primary[k] for k in primary if k.startswith("role_") or k.startswith("is_") or k in (
            "primary_role_label",
            "display_role_text",
        )},
        "role_classifications": classifications,
    }


def enrich_control_party(party: dict[str, Any]) -> dict[str, Any]:
    """Add classification fields to an existing control-party dict."""
    if party.get("role_category") and party.get("primary_role_label"):
        return party
    codes = list(party.get("role_codes") or [])
    roles = list(party.get("roles") or [])
    classifications: list[dict[str, Any]] = []
    if party.get("role_classifications"):
        classifications = list(party["role_classifications"])
    else:
        for i, role_text in enumerate(roles):
            row = {ROLE_TEXT_COL: role_text, ROLE_CODE_COL: codes[i] if i < len(codes) else ""}
            if party.get("pcts"):
                row[PCT_COL] = (party["pcts"] or [None])[min(i, len(party["pcts"]) - 1)]
            if party.get("association_dates"):
                row[ASSOC_DATE_COL] = (party["association_dates"] or [None])[0]
            classifications.append(classify_owner_record(row))
        if not classifications and (party.get("pcts") or party.get("association_dates")):
            row = {
                ROLE_TEXT_COL: "",
                PCT_COL: (party.get("pcts") or [None])[0],
                ASSOC_DATE_COL: (party.get("association_dates") or [None])[0],
            }
            classifications.append(classify_owner_record(row))
    primary = _pick_primary_classification(classifications)
    party = {**party, **{k: primary[k] for k in primary if k.startswith("role_") or k.startswith("is_") or k in (
        "primary_role_label",
        "display_role_text",
    )}}
    if classifications:
        party["role_classifications"] = classifications
    if codes and "role_codes" not in party:
        party["role_codes"] = codes
    max_pct = party.get("max_ownership_pct")
    if max_pct is None:
        max_pct = _max_pct_from_party(party)
        if max_pct is not None:
            party["max_ownership_pct"] = max_pct
    return party


def _max_pct_from_party(party: dict[str, Any]) -> float | None:
    best: float | None = None
    for raw in party.get("pcts") or []:
        v = parse_ownership_pct(raw)
        if v is not None:
            best = v if best is None else max(best, v)
    return best


def party_sort_key(party: dict[str, Any]) -> tuple[Any, ...]:
    p = enrich_control_party(dict(party))
    cat_rank = CATEGORY_RANK.get(str(p.get("role_category") or ""), 0)
    priority = int(p.get("role_priority") or 0)
    pct = p.get("max_ownership_pct")
    if pct is None:
        pct = _max_pct_from_party(p) or -1.0
    ad = p.get("association_date_earliest")
    if ad is None and p.get("association_dates"):
        ad = parse_association_date((p["association_dates"] or [""])[0])
    date_ord = ad.timestamp() if isinstance(ad, datetime) else 0.0
    return (
        -cat_rank,
        -priority,
        -float(pct),
        -date_ord,
        str(p.get("name") or "").upper(),
    )


def sort_control_parties(parties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [enrich_control_party(dict(p)) for p in parties]
    return sorted(enriched, key=party_sort_key)


def sort_cms_owner_change_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort added/removed/changed owner rows (CHOW or SNF diffs) by role signal."""
    return sort_control_parties(records)


def sort_owner_facility_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort facility link rows on owner profiles (role category, then %, then date)."""
    keyed: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for row in rows:
        fake_party = {
            "roles": [row.get("role") or ""],
            "role_codes": [row.get("role_code") or ""],
            "pcts": [row.get("pct") or ""],
            "association_dates": [row.get("association_date") or ""],
            "name": row.get("facility_name") or "",
        }
        keyed.append((party_sort_key(fake_party), row))
    keyed.sort(key=lambda x: x[0])
    return [r for _, r in keyed]


def facility_link_category_key(category: str) -> str:
    """JSON field suffix for per-category facility counts."""
    return f"facility_count_{category}"


def accumulate_facility_link(
    buckets: dict[str, dict[str, set[str]]],
    owner_pac: str,
    ccn_norm: str,
    row: dict[str, Any],
) -> None:
    """Track distinct CCNs per owner PAC and role category (plus ``any``)."""
    info = classify_owner_record(row)
    cat = str(info.get("role_category") or CATEGORY_OTHER)
    pac_buckets = buckets.setdefault(owner_pac, {})
    pac_buckets.setdefault("any", set()).add(ccn_norm)
    pac_buckets.setdefault(cat, set()).add(ccn_norm)


def facility_link_counts_from_buckets(
    pac_buckets: dict[str, set[str]],
) -> dict[str, int]:
    out: dict[str, int] = {"facility_count": len(pac_buckets.get("any") or set())}
    for cat in CATEGORY_RANK:
        key = facility_link_category_key(cat)
        out[key] = len(pac_buckets.get(cat) or set())
    return out


def format_role_short_for_classification(info: dict[str, Any]) -> str:
    """Compact label from classify_owner_record output."""
    label = str(info.get("primary_role_label") or "").strip()
    if not label:
        return "—"
    cat = info.get("role_category")
    if cat == CATEGORY_OWNERSHIP:
        pct = info.get("ownership_pct")
        if pct is not None and pct >= 5:
            if "direct" in str(info.get("role_text_raw") or "").lower():
                return "≥5% direct ownership"
            if "indirect" in str(info.get("role_text_raw") or "").lower():
                return "≥5% indirect ownership"
        return "Ownership interest"
    if cat == CATEGORY_OPERATIONAL:
        return "Operational/managerial control"
    if cat == CATEGORY_ADMIN:
        return "ADP of the SNF"
    if len(label) <= 28:
        return label
    return label[:26].rstrip() + "…"


def ownership_pct_display_label(raw: str) -> str:
    """Human-readable stake, e.g. 50 → '50% ownership interest'."""
    s = str(raw or "").strip()
    if not s or s in ("—", "-", "N/A", "n/a"):
        return ""
    if s.endswith("%"):
        core = s[:-1].strip().replace(",", "")
        if not core:
            return ""
        try:
            if float(core) == 0:
                return ""
        except ValueError:
            pass
        return f"{s} ownership interest"
    try:
        v = float(s.replace(",", ""))
        if v == 0:
            return ""
        if v == int(v):
            return f"{int(v)}% ownership interest"
        return f"{v:g}% ownership interest"
    except ValueError:
        return f"{s}% ownership interest" if "%" not in s else f"{s} ownership interest"
