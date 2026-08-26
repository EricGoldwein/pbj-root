"""
Temporal attribution helpers for CMS association timing vs metric periods.

## What ASSOCIATION DATE - OWNER establishes (CMS)

CMS SNF All Owners data dictionary:

  "Date on which the owner became associated with the Skilled Nursing Facility."

In CMS PECOS vocabulary, "owner" on this file means an associate with
**ownership interest and/or managing control** of the enrollment — not
necessarily an equity holder. ROLE CODE / ROLE TEXT distinguish the relationship.

What the field **does** establish:
- A PECOS-reported **association start date** for that associate↔enrollment row.
- Role-specific: the same PAC can have different association dates for different roles.

What the field **does not** establish:
- An "ownership closing" / equity-effective date.
- An association **end** date (snapshots are point-in-time; no end column).
- That the associate held the relationship for an entire metric period.
- That Care Compare star ratings or other survey-era metrics are contemporaneous
  with that association.

## PBJ quarterly HPRD attribution

A facility CCN is HPRD-eligible at most once. It qualifies when **at least one**
CMS role on that CCN is a supported relationship for the PBJ quarter:

- ``ownership_interest`` (CMS ownership-interest role codes), or
- CMS role code **43** (OPERATIONAL/MANAGERIAL CONTROL), or
- CMS role code **63** (MANAGING CONTROL - GOVERNING BODY)

Each role is evaluated with **that role's own** ASSOCIATION DATE - OWNER
(not CSV first-seen order, and not a single shared facility date).

Full-period ``supported`` for a qualifying role requires association_date on or
before the **start** of the PBJ quarter.

Association after quarter end → ``exclude`` for that qualifying role.
Association mid-quarter (after start, on/before end) → ``uncertain`` until a
national daily PBJ windowed HPRD loader exists (see PARTIAL_PERIOD_HPRD_*).

Corporate governance alone (codes **40** OFFICER / **41** DIRECTOR) and other
non-qualifying roles (e.g. **72** ADP OF THE SNF) stay visible on the profile
but do **not** qualify the CCN for owner-level HPRD means.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

# National daily PBJ is not wired into ownership portfolio rollups. Mid-quarter
# associations therefore cannot compute Σhours/Σcensus for [assoc, QE] safely.
PARTIAL_PERIOD_HPRD_SUPPORTED = False
PARTIAL_PERIOD_HPRD_NOTE = (
    "Partial-period HPRD (association_date→quarter_end) requires a national "
    "day-level PBJ hours/census index. Ownership rollups currently use quarterly "
    "HPRD only; mid-quarter associations are uncertain, not manufactured means."
)

# CMS SNF All Owners Owner Role Code Reference Table — managing-control codes
# that qualify for owner-level PBJ HPRD (in addition to ownership_interest).
HPRD_QUALIFYING_MANAGING_CONTROL_CODES = frozenset({"43", "63"})

AssociationTiming = Literal[
    "association_began_on_or_before_period_start",
    "association_began_during_period",
    "association_began_after_period_end",
    "association_date_missing",
    "metric_period_unknown",
]

MetricAttributionMode = Literal[
    "owner_performance_candidate",
    "facility_context_only",
    "unsupported",
]

RelationshipKind = Literal[
    "ownership_interest",
    "control_or_management",
    "governance",
    "administrative",
    "financial",
    "other_or_unknown",
    "enrollment_party",
    "chow_party",
]

AttributionStatus = Literal[
    "supported",  # full-period attributable (OI / code 43 / code 63 + assoc ≤ Q start)
    "partial_period_supported",  # reserved; not emitted while PARTIAL_PERIOD_HPRD_SUPPORTED is False
    "exclude",
    "uncertain",
    "facility_context",
]

_QUARTER_RE = re.compile(r"Q\s*([1-4])\s*[/\-]?\s*(\d{4})", re.IGNORECASE)
_QUARTER_ENDS = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
_QUARTER_STARTS = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}

_ROLE_TO_KIND = {
    "ownership_interest": "ownership_interest",
    "operational_control": "control_or_management",
    "corporate_governance": "governance",
    "administrative_disclosure": "administrative",
    "financial_interest": "financial",
    "other": "other_or_unknown",
}


def parse_association_start(raw: Any) -> date | None:
    """Parse ASSOCIATION DATE - OWNER (PECOS association start, not equity close)."""
    s = str(raw or "").strip()
    if not s or s.lower() in ("nan", "none", "—", "-", "n/a", "null"):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%m-%d-%Y", "%Y%m%d"):
        try:
            chunk = s[:8] if fmt == "%Y%m%d" and len(s) >= 8 and s[:8].isdigit() else s[:10]
            return datetime.strptime(chunk, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        mo, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000 if yr < 50 else 1900
        try:
            return date(yr, mo, day)
        except ValueError:
            return None
    return None


def parse_pbj_quarter_bounds(quarter: Any) -> tuple[date, date] | None:
    """Parse PBJ ``quarter`` (e.g. ``Q1 2026`` / ``2026Q1``) into inclusive [start, end]."""
    s = str(quarter or "").strip()
    if not s:
        return None
    m = _QUARTER_RE.search(s)
    if not m:
        m2 = re.search(r"(20\d{2})\s*Q\s*([1-4])", s, re.IGNORECASE)
        if m2:
            year, q = int(m2.group(1)), int(m2.group(2))
        else:
            return None
    else:
        q = int(m.group(1))
        year = int(m.group(2))
    sm, sd = _QUARTER_STARTS[q]
    em, ed = _QUARTER_ENDS[q]
    return date(year, sm, sd), date(year, em, ed)


def relationship_kind_from_role_category(role_category: Any) -> RelationshipKind:
    key = str(role_category or "").strip()
    return _ROLE_TO_KIND.get(key, "other_or_unknown")  # type: ignore[return-value]


def normalize_hprd_role_code(raw: Any) -> str:
    """Normalize a CMS owner role code to a 2-digit string (digits only)."""
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


def role_qualifies_for_owner_hprd(
    *,
    role_code: Any = None,
    relationship_kind: RelationshipKind | str | None = None,
) -> bool:
    """
    True when this CMS role may attribute owner-level PBJ HPRD.

    Qualifying: ownership_interest category/kind, or CMS codes 43 / 63.
    Codes 40/41 (governance), 72 (ADP), 25/42 (other managing-employee codes),
    and other non-OI roles do not qualify on their own.
    """
    kind = str(relationship_kind or "").strip()
    if kind == "ownership_interest":
        return True
    code = normalize_hprd_role_code(role_code)
    return code in HPRD_QUALIFYING_MANAGING_CONTROL_CODES


def metric_attribution_mode(metric_kind: str) -> MetricAttributionMode:
    kind = str(metric_kind or "").strip().lower()
    if kind in ("pbj_hprd", "pbj_nurse_hprd", "hprd", "reported_total_nurse_hprd"):
        return "owner_performance_candidate"
    if kind.startswith("care_compare") or kind in (
        "overall_rating",
        "staffing_rating",
        "health_inspection_rating",
        "qm_rating",
        "quality_rating",
    ):
        return "facility_context_only"
    if kind in ("census", "beds", "avg_residents", "certified_beds"):
        return "facility_context_only"
    return "unsupported"


def _resolve_period_bounds(
    metric_start: Any, metric_end: Any
) -> tuple[date | None, date | None]:
    start = metric_start if isinstance(metric_start, date) else None
    end = metric_end if isinstance(metric_end, date) else None
    if start is None and metric_start is not None:
        bounds = parse_pbj_quarter_bounds(metric_start)
        if bounds:
            start, end = bounds
        else:
            start = parse_association_start(metric_start)
    if end is None and metric_end is not None:
        end = parse_association_start(metric_end)
    if end is None and start is None and metric_start is not None:
        bounds = parse_pbj_quarter_bounds(metric_start)
        if bounds:
            start, end = bounds
    return start, end


def association_timing_vs_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
) -> AssociationTiming:
    """
    Compare PECOS association start to a metric window.

    Distinguishes full-period (assoc ≤ start) from mid-period (start < assoc ≤ end).
    """
    assoc = (
        association_start
        if isinstance(association_start, date)
        else parse_association_start(association_start)
    )
    if assoc is None:
        return "association_date_missing"

    start, end = _resolve_period_bounds(metric_start, metric_end)
    if end is None:
        return "metric_period_unknown"
    if start is None:
        if assoc > end:
            return "association_began_after_period_end"
        return "association_began_during_period"

    if assoc > end:
        return "association_began_after_period_end"
    if assoc > start:
        return "association_began_during_period"
    return "association_began_on_or_before_period_start"


def relationship_supported_for_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
    *,
    relationship_kind: RelationshipKind | str | None = None,
    role_code: Any = None,
    metric_kind: str | None = None,
) -> AttributionStatus:
    """
    Gate for one CMS role against a metric window.

    PBJ HPRD qualifying roles (ownership_interest, or codes 43 / 63):
      assoc ≤ quarter start → supported (full-period)
      start < assoc ≤ end → uncertain (partial daily HPRD not available)
      assoc > end → exclude

    Non-qualifying roles (governance 40/41, ADP 72, other control codes, etc.)
    → uncertain for HPRD means (still visible on profiles).

    Care Compare ratings → facility_context.
    """
    mode = metric_attribution_mode(metric_kind or "")
    if metric_kind and mode == "facility_context_only":
        return "facility_context"
    if metric_kind and mode == "unsupported":
        return "facility_context"

    timing = association_timing_vs_period(association_start, metric_start, metric_end)
    kind = str(relationship_kind or "").strip() or "other_or_unknown"
    qualifies = role_qualifies_for_owner_hprd(
        role_code=role_code, relationship_kind=kind
    )

    if metric_kind and mode == "owner_performance_candidate":
        if not qualifies:
            return "uncertain"
        if timing == "association_began_after_period_end":
            return "exclude"
        if timing in ("association_date_missing", "metric_period_unknown"):
            return "uncertain"
        if timing == "association_began_on_or_before_period_start":
            return "supported"
        if timing == "association_began_during_period":
            if PARTIAL_PERIOD_HPRD_SUPPORTED:
                return "partial_period_supported"
            return "uncertain"
        return "uncertain"

    # Timing-only legacy path (no metric_kind): require full-period for "supported".
    if timing == "association_began_after_period_end":
        return "exclude"
    if timing in ("association_date_missing", "metric_period_unknown"):
        return "uncertain"
    if timing == "association_began_on_or_before_period_start":
        return "supported"
    if timing == "association_began_during_period":
        return "uncertain"
    return "supported"


def _role_dict_kind_and_code(role: dict[str, Any]) -> tuple[RelationshipKind, str]:
    code = normalize_hprd_role_code(
        role.get("role_code") or role.get("ROLE CODE - OWNER")
    )
    cat = str(
        role.get("role_category")
        or role.get("primary_role_category")
        or ""
    ).strip()
    if not cat and (code or role.get("role") or role.get("ROLE TEXT - OWNER")):
        try:
            from ownership.role_classification import (
                ROLE_CODE_COL,
                ROLE_TEXT_COL,
                classify_owner_record,
            )

            info = classify_owner_record(
                {
                    ROLE_CODE_COL: code or role.get("role_code"),
                    ROLE_TEXT_COL: role.get("role")
                    or role.get("ROLE TEXT - OWNER")
                    or role.get("role_text_raw")
                    or "",
                }
            )
            cat = str(info.get("role_category") or "")
            if not code:
                code = normalize_hprd_role_code(info.get("role_code"))
        except Exception:
            cat = cat or ""
    kind = relationship_kind_from_role_category(cat)
    return kind, code


def hprd_attribution_from_roles(
    roles: list[dict[str, Any]] | None,
    metric_start: Any,
    metric_end: Any,
) -> AttributionStatus:
    """
    Aggregate per-role HPRD attribution for one CCN.

    Each role uses its own association_date. The CCN is ``supported`` if any
    qualifying role is supported; never double-counts for weighting (caller
    still weights the CCN once).
    """
    role_list = [r for r in (roles or []) if isinstance(r, dict)]
    if not role_list:
        return "uncertain"

    qual_statuses: list[AttributionStatus] = []
    for role in role_list:
        kind, code = _role_dict_kind_and_code(role)
        qualifies = role_qualifies_for_owner_hprd(
            role_code=code, relationship_kind=kind
        )
        status = relationship_supported_for_period(
            role.get("association_date")
            or role.get("ASSOCIATION DATE - OWNER"),
            metric_start,
            metric_end,
            relationship_kind=kind,
            role_code=code,
            metric_kind="pbj_hprd",
        )
        if qualifies:
            qual_statuses.append(status)

    if any(s == "supported" for s in qual_statuses):
        return "supported"
    if any(s == "partial_period_supported" for s in qual_statuses):
        return "partial_period_supported"
    if any(s == "uncertain" for s in qual_statuses):
        return "uncertain"
    if any(s == "exclude" for s in qual_statuses):
        return "exclude"
    # Governance-only / ADP / other non-qualifying: visible, not in HPRD mean.
    return "uncertain"


def attribution_status_for_facility(
    facility: dict[str, Any],
    *,
    metric_start: date | None,
    metric_end: date | None,
    metric_kind: str = "pbj_hprd",
) -> AttributionStatus:
    """Per-facility attribution for a specific metric kind."""
    if metric_start is None or metric_end is None:
        if metric_attribution_mode(metric_kind) == "facility_context_only":
            return "facility_context"
        return "uncertain"

    if metric_attribution_mode(metric_kind) == "facility_context_only":
        return "facility_context"
    if metric_attribution_mode(metric_kind) == "unsupported":
        return "facility_context"

    roles = facility.get("roles")
    if isinstance(roles, list) and roles:
        return hprd_attribution_from_roles(roles, metric_start, metric_end)

    role_cat = facility.get("role_category") or facility.get("primary_role_category")
    return relationship_supported_for_period(
        facility.get("association_date"),
        metric_start,
        metric_end,
        relationship_kind=relationship_kind_from_role_category(role_cat),
        role_code=facility.get("role_code"),
        metric_kind=metric_kind,
    )


CMS_ASSOCIATION_DATE_DEFINITION = (
    "Date on which the owner became associated with the Skilled Nursing Facility "
    "(CMS SNF All Owners data dictionary). PECOS association start for an "
    "ownership-interest and/or managing-control role — not an equity closing date "
    "and not an association end date."
)
