"""
Temporal attribution for owner↔facility relationships vs PBJ metric periods.

CMS SNF All Owners publishes ASSOCIATION DATE - OWNER as a start-only field
(no association end). Snapshot presence is treated as the end bound.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

AttributionStatus = Literal["supported", "exclude", "uncertain"]

_QUARTER_RE = re.compile(r"Q\s*([1-4])\s*[/\-]?\s*(\d{4})", re.IGNORECASE)
_QUARTER_ENDS = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
_QUARTER_STARTS = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}


def parse_association_start(raw: Any) -> date | None:
    """Parse ASSOCIATION DATE - OWNER (or equivalent) to a calendar date."""
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
    """
    Parse provider-info ``quarter`` (e.g. ``Q1 2026``) into inclusive [start, end].
    """
    s = str(quarter or "").strip()
    if not s:
        return None
    m = _QUARTER_RE.search(s)
    if not m:
        return None
    q = int(m.group(1))
    year = int(m.group(2))
    sm, sd = _QUARTER_STARTS[q]
    em, ed = _QUARTER_ENDS[q]
    return date(year, sm, sd), date(year, em, ed)


def relationship_supported_for_period(
    association_start: Any,
    metric_start: Any,
    metric_end: Any,
) -> AttributionStatus:
    """
    Whether an owner association supports inclusion in a metric-period aggregate.

    Rules (start-only association date):
    - missing/invalid assoc date → uncertain
    - assoc start > metric_end → exclude (relationship begins after the period)
    - assoc start <= metric_end → supported (overlap; snapshot presence is end bound)
    """
    assoc = association_start if isinstance(association_start, date) else parse_association_start(
        association_start
    )
    if assoc is None:
        return "uncertain"

    end = metric_end if isinstance(metric_end, date) else None
    if end is None and metric_end is not None:
        end = parse_association_start(metric_end)
    if end is None and metric_start is not None and metric_end is None:
        # Allow callers to pass quarter string as metric_start only via parse helper.
        bounds = parse_pbj_quarter_bounds(metric_start)
        if bounds:
            _, end = bounds
    if end is None:
        return "uncertain"

    if assoc > end:
        return "exclude"
    return "supported"


def attribution_status_for_facility(
    facility: dict[str, Any],
    *,
    metric_start: date | None,
    metric_end: date | None,
) -> AttributionStatus:
    """Compute attribution_status for one enriched facility row."""
    if metric_start is None or metric_end is None:
        return "uncertain"
    return relationship_supported_for_period(
        facility.get("association_date"),
        metric_start,
        metric_end,
    )
