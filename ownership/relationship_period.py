"""
Temporal helpers for CMS association timing vs metric periods.

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
- Causal responsibility for staffing outcomes.

## Portfolio HPRD inclusion (descriptive, not attribution)

The owner-profile **Portfolio HPRD** card is a descriptive statistic over
CMS-linked facilities. A facility CCN is included at most once when **at least
one** preserved CMS relationship for that PAC began on or before the **start**
of the PBJ quarter — **regardless of role category**.

Each relationship is evaluated with **that role's own** ASSOCIATION DATE - OWNER
(not CSV first-seen order, and not a single shared facility date). A later role
must not override an earlier timing-qualifying relationship.

Association after quarter end → ``exclude`` for that relationship.
Association mid-quarter (after start, on/before end) or missing date →
``uncertain`` until a national daily PBJ windowed HPRD loader exists
(see PARTIAL_PERIOD_HPRD_*). Uncertain and exclude statuses are omitted from
the Portfolio HPRD mean.

This is **not** owner-attributable / causal staffing responsibility.
Role classification for display lives in ``ownership.role_classification``.
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

AssociationTiming = Literal[
    "association_began_on_or_before_period_start",
    "association_began_during_period",
    "association_began_after_period_end",
    "association_date_missing",
    "metric_period_unknown",
]

MetricAttributionMode = Literal[
    "portfolio_linked_facility",
    "facility_context_only",
    "unsupported",
]

# Portfolio inclusion statuses for the HPRD card gate.
# "supported" means timing-eligible for portfolio inclusion — not causal attribution.
AttributionStatus = Literal[
    "supported",
    "partial_period_supported",  # reserved; not emitted while PARTIAL_PERIOD_HPRD_SUPPORTED is False
    "exclude",
    "uncertain",
    "facility_context",
]

_QUARTER_RE = re.compile(r"Q\s*([1-4])\s*[/\-]?\s*(\d{4})", re.IGNORECASE)
_QUARTER_ENDS = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
_QUARTER_STARTS = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}


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
        if not m2:
            return None
        year, q = int(m2.group(1)), int(m2.group(2))
    else:
        q = int(m.group(1))
        year = int(m.group(2))
    sm, sd = _QUARTER_STARTS[q]
    em, ed = _QUARTER_ENDS[q]
    return date(year, sm, sd), date(year, em, ed)


def metric_attribution_mode(metric_kind: str) -> MetricAttributionMode:
    kind = str(metric_kind or "").strip().lower()
    if kind in ("pbj_hprd", "pbj_nurse_hprd", "hprd", "reported_total_nurse_hprd"):
        return "portfolio_linked_facility"
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


def rating_metric_context_status(*, metric_kind: str = "overall_rating") -> AttributionStatus:
    """Care Compare / rating metrics are facility context only (never Portfolio HPRD)."""
    del metric_kind
    return "facility_context"


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


def _timing_to_portfolio_status(timing: AssociationTiming) -> AttributionStatus:
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


def relationship_supported_for_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
    *,
    metric_kind: str | None = None,
    **_ignored: Any,
) -> AttributionStatus:
    """
    Gate for one CMS relationship against a metric window (timing only).

    Portfolio HPRD (``pbj_hprd``):
      assoc ≤ quarter start → supported (portfolio-included)
      start < assoc ≤ end → uncertain (partial daily HPRD not available)
      assoc > end → exclude
      missing / unknown period → uncertain

    Care Compare ratings → facility_context.

    Extra keyword args (e.g. legacy ``relationship_kind`` / ``role_code``) are
    ignored — role category is not an eligibility gate.
    """
    del _ignored
    mode = metric_attribution_mode(metric_kind or "")
    if metric_kind and mode == "facility_context_only":
        return "facility_context"
    if metric_kind and mode == "unsupported":
        return "facility_context"

    timing = association_timing_vs_period(association_start, metric_start, metric_end)
    return _timing_to_portfolio_status(timing)


def hprd_portfolio_inclusion_from_roles(
    roles: list[dict[str, Any]] | None,
    metric_start: Any,
    metric_end: Any,
) -> AttributionStatus:
    """
    Aggregate per-role **portfolio inclusion** timing for one CCN.

    Each relationship contributes only its association_date. Role codes and
    categories are not consulted. The CCN is ``supported`` if any relationship
    began on/before quarter start.
    """
    role_list = [r for r in (roles or []) if isinstance(r, dict)]
    if not role_list:
        return "uncertain"

    statuses: list[AttributionStatus] = []
    for role in role_list:
        status = relationship_supported_for_period(
            role.get("association_date")
            or role.get("ASSOCIATION DATE - OWNER"),
            metric_start,
            metric_end,
            metric_kind="pbj_hprd",
        )
        statuses.append(status)

    if any(s == "supported" for s in statuses):
        return "supported"
    if any(s == "partial_period_supported" for s in statuses):
        return "partial_period_supported"
    if any(s == "uncertain" for s in statuses):
        return "uncertain"
    if any(s == "exclude" for s in statuses):
        return "exclude"
    return "uncertain"


def portfolio_inclusion_status_for_facility(
    facility: dict[str, Any],
    *,
    metric_start: date | None,
    metric_end: date | None,
    metric_kind: str = "pbj_hprd",
) -> AttributionStatus:
    """Per-facility Portfolio HPRD inclusion (timing-only; any CMS role)."""
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
        return hprd_portfolio_inclusion_from_roles(roles, metric_start, metric_end)

    return relationship_supported_for_period(
        facility.get("association_date"),
        metric_start,
        metric_end,
        metric_kind=metric_kind,
    )


CMS_ASSOCIATION_DATE_DEFINITION = (
    "Date on which the owner became associated with the Skilled Nursing Facility "
    "(CMS SNF All Owners data dictionary). PECOS association start for an "
    "associate↔enrollment relationship — not an equity closing date, not an "
    "association end date, and not proof of staffing responsibility."
)
