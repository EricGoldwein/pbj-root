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

Therefore ``relationship_supported_for_period`` / timing helpers only answer:
"Did CMS report that this association began on or before the metric period end?"
They never claim full-period ownership or equity.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

# Timing vs a measurement window (association-date only).
AssociationTiming = Literal[
    "association_began_on_or_before_period_end",
    "association_began_after_period_end",
    "association_date_missing",
    "metric_period_unknown",
]

# Whether a metric may be rolled into an *owner-attributed performance* aggregate.
MetricAttributionMode = Literal[
    "owner_performance_candidate",  # may enter owner means if timing + role allow
    "facility_context_only",  # show on facility row; do not owner-attribute
    "unsupported",  # do not treat as owner performance
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
    "supported",  # legacy alias: timing ok for candidate metrics
    "exclude",  # association clearly after period
    "uncertain",  # missing date / unknown period
    "facility_context",  # metric retained on facility only
]

_QUARTER_RE = re.compile(r"Q\s*([1-4])\s*[/\-]?\s*(\d{4})", re.IGNORECASE)
_QUARTER_ENDS = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
_QUARTER_STARTS = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}

# Role categories from ownership.role_classification → relationship kind.
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


def metric_attribution_mode(metric_kind: str) -> MetricAttributionMode:
    """
    Which metrics may be owner-attributed with a period join.

    - ``pbj_hprd`` / ``pbj_nurse_hprd``: PBJ quarter staffing hours — candidate
      when association timing and an ownership_interest (or explicit control
      policy) allow.
    - ``care_compare_rating_*``: Care Compare stars are survey/inspection era
      composites — facility context only (not contemporaneous owner performance).
    - ``census`` / ``beds``: structural facility descriptors — facility context.
    """
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


def association_timing_vs_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
) -> AssociationTiming:
    """
    Compare PECOS association start to a metric window.

    ``association_began_on_or_before_period_end`` only means CMS reported the
    association started on/before the period end — not full-period ownership.
    """
    assoc = (
        association_start
        if isinstance(association_start, date)
        else parse_association_start(association_start)
    )
    if assoc is None:
        return "association_date_missing"

    end = metric_end if isinstance(metric_end, date) else None
    if end is None and metric_end is not None:
        end = parse_association_start(metric_end)
    if end is None and metric_start is not None:
        bounds = parse_pbj_quarter_bounds(metric_start)
        if bounds:
            _, end = bounds
    if end is None:
        return "metric_period_unknown"

    if assoc > end:
        return "association_began_after_period_end"
    return "association_began_on_or_before_period_end"


def relationship_supported_for_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
    *,
    relationship_kind: RelationshipKind | str | None = None,
    metric_kind: str | None = None,
) -> AttributionStatus:
    """
    Legacy-compatible gate for owner aggregates.

    Prefer calling with ``metric_kind`` + ``relationship_kind``:
    - Care Compare ratings → ``facility_context`` (never owner performance means)
    - PBJ HPRD → timing gate; ``exclude`` only when association start > period end
    - Without metric_kind, preserves prior timing-only behavior for tests
    """
    mode = metric_attribution_mode(metric_kind or "")
    if metric_kind and mode == "facility_context_only":
        return "facility_context"
    if metric_kind and mode == "unsupported":
        return "facility_context"

    timing = association_timing_vs_period(association_start, metric_start, metric_end)
    if timing == "association_began_after_period_end":
        return "exclude"
    if timing in ("association_date_missing", "metric_period_unknown"):
        return "uncertain"

    # Timing OK. Equity-interest preferred for owner HPRD means; control/other
    # remain uncertain for *performance* attribution (facility metrics still shown).
    kind = str(relationship_kind or "").strip() or "other_or_unknown"
    if metric_kind and mode == "owner_performance_candidate":
        if kind == "ownership_interest":
            return "supported"
        if kind in ("control_or_management", "governance", "financial"):
            # Present in CMS association; do not claim as ownership-period HPRD.
            return "uncertain"
        return "uncertain"

    # Timing-only legacy path (no metric_kind): map to supported/uncertain/exclude.
    return "supported"


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
    role_cat = facility.get("role_category") or facility.get("primary_role_category")
    return relationship_supported_for_period(
        facility.get("association_date"),
        metric_start,
        metric_end,
        relationship_kind=relationship_kind_from_role_category(role_cat),
        metric_kind=metric_kind,
    )


# Back-compat alias used in earlier remediation docs.
CMS_ASSOCIATION_DATE_DEFINITION = (
    "Date on which the owner became associated with the Skilled Nursing Facility "
    "(CMS SNF All Owners data dictionary). PECOS association start for an "
    "ownership-interest and/or managing-control role — not an equity closing date "
    "and not an association end date."
)
