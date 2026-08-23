"""Public staffing day-evidence lookup (precomputed PBJapp handoff)."""

from __future__ import annotations

import os
import re
from typing import Any

import staffing_evidence_bundle as seb
from canonical_urls import provider_url
from pbj_public_query.provenance import absolute_url, daily_staffing_evidence_citation, pbj320_derived_block

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PERIOD_RE = re.compile(r"^(?:CY)?(\d{4})Q([1-4])$", re.I)


def normalize_evidence_period(raw: str | None) -> str:
    """Normalize to CY2026Q1 form; empty string if blank/invalid."""
    s = str(raw or "").strip().upper().replace(" ", "")
    if not s:
        return ""
    m = _PERIOD_RE.match(s)
    if not m:
        return ""
    return f"CY{m.group(1)}Q{m.group(2)}"


def available_evidence_periods(app_root: str | None = None) -> list[str]:
    root = app_root or APP_ROOT
    manifest = seb.load_manifest(root) or {}
    raw = manifest.get("quarters_in_bundle") or []
    out: list[str] = []
    for q in raw:
        n = normalize_evidence_period(str(q))
        if n and n not in out:
            out.append(n)
    return out


def canonical_latest_evidence_period(app_root: str | None = None) -> str | None:
    periods = available_evidence_periods(app_root)
    return periods[-1] if periods else None


def get_staffing_evidence(
    ccn: str,
    work_date: str,
    metric: str = "RN_HPRD",
    *,
    period: str | None = None,
) -> dict[str, Any] | None:
    """Bounded lookup: one CCN + one ISO date + one metric.

    Optional ``period`` (e.g. CY2026Q1 / 2026Q1):
    - If the requested period is not loaded in the evidence bundle → structured
      unavailable error (never silently substitutes another quarter).
    - If a day_fact exists but its stored quarter differs → unavailable for period.
    - If omitted, returns the day_fact for that CCN+date when present.
    """
    prov = seb.normalize_ccn(ccn)
    date = seb.normalize_work_date(work_date)
    met = seb.normalize_metric(metric)
    if not prov or not date or not met:
        return None

    want_period = normalize_evidence_period(period) if period else ""
    available = available_evidence_periods(APP_ROOT)
    latest = available[-1] if available else None

    if want_period and want_period not in available:
        return {
            "ok": False,
            "error": "evidence_unavailable_for_period",
            "message": (
                f"Evidence unavailable for requested period {want_period}. "
                f"Loaded periods: {available or ['(none)']}. "
                "No silent quarter substitution."
            ),
            "requested_period": want_period,
            "available_periods": available,
            "canonical_latest_evidence_period": latest,
            "ccn": prov,
            "work_date": date,
            "metric": met,
        }

    evidence = seb.lookup_day_evidence(APP_ROOT, prov, date, met)
    if not evidence:
        if want_period:
            return {
                "ok": False,
                "error": "evidence_unavailable_for_period",
                "message": (
                    f"No day evidence for CCN {prov} on {date} in period {want_period}."
                ),
                "requested_period": want_period,
                "available_periods": available,
                "canonical_latest_evidence_period": latest,
                "ccn": prov,
                "work_date": date,
                "metric": met,
            }
        return None

    quarter = normalize_evidence_period(str(evidence.get("quarter") or "")) or str(
        evidence.get("quarter") or ""
    )
    if want_period and quarter and want_period != quarter:
        return {
            "ok": False,
            "error": "evidence_unavailable_for_period",
            "message": (
                f"Day {date} for CCN {prov} is stored under {quarter}, "
                f"not requested period {want_period}. No silent quarter substitution."
            ),
            "requested_period": want_period,
            "row_period": quarter,
            "available_periods": available,
            "canonical_latest_evidence_period": latest,
            "ccn": prov,
            "work_date": date,
            "metric": met,
        }

    from canonical_urls import get_facility_name_from_search_index

    name = get_facility_name_from_search_index(prov)
    canon = provider_url(prov, name)

    payload = {
        "ccn": prov,
        "work_date": date,
        "metric": met,
        "evidence": {
            "metric_display": evidence.get("metric_display"),
            "value": evidence.get("value"),
            "formula": evidence.get("formula"),
            "ccn": prov,
            "work_date": date,
            "quarter": quarter,
        },
        "citation": daily_staffing_evidence_citation(
            quarter=quarter,
            work_date=date,
            canonical_url=canon,
        ),
        "analysis": pbj320_derived_block(
            metric=met,
            description=(
                "Daily HPRD assembled from PBJapp precomputed day_fact handoff; "
                "not recalculated in pbj-root."
            ),
            methodology_url="/data-sources#pbj-daily-staffing",
        ),
        "audit": {
            "provenance_precision": evidence.get("provenance_precision"),
            "source_record_id": evidence.get("source_record_id"),
            "numerator": evidence.get("numerator"),
            "denominator": evidence.get("denominator"),
        },
        "canonical_url": absolute_url(canon) if canon.startswith("/") else canon,
        "evidence_url": f"{canon}#staffing",
        "evidence_period": quarter,
        "available_periods": available,
        "canonical_latest_evidence_period": latest,
        "extraction_bounds": {
            "scope": "single_facility_day_metric",
            "allows_date_range": False,
            "allows_all_days_in_quarter": False,
            "allows_all_facilities": False,
            "allows_unrestricted_pagination": False,
        },
    }
    manifest = seb.load_manifest(APP_ROOT) or {}
    if manifest.get("built_at"):
        payload["release"] = {
            "evidence_bundle_built_at": manifest.get("built_at"),
            "quarters_in_bundle": manifest.get("quarters_in_bundle"),
            "bundle_schema_version": manifest.get("bundle_schema_version"),
        }
    return payload
