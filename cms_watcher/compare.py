"""Compare CMS observed state vs PBJ320 production + prior watcher state."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .cms_fetch import CmsObservedState
from .production_state import ProductionObservedState
from .registry import CmsSource

Status = str  # CURRENT | NEW_RELEASE | METADATA_CHANGED | PRODUCTION_BEHIND | ...


@dataclass
class SourceEvaluation:
    source_id: str
    title: str
    statuses: list[str]
    cms: dict[str, Any] | None
    production: dict[str, Any]
    previous_cms_fingerprint: str | None
    affected_surfaces: list[str]
    affected_downstream: list[dict[str, str]]
    summary: str
    check_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_token(value: str | None) -> str:
    if not value:
        return ""
    s = value.strip().upper().replace("_", "-").replace(".", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _month_label_to_ym(label: str | None) -> tuple[int, int] | None:
    if not label:
        return None
    months = {
        "JAN": 1,
        "JANUARY": 1,
        "FEB": 2,
        "FEBRUARY": 2,
        "MAR": 3,
        "MARCH": 3,
        "APR": 4,
        "APRIL": 4,
        "MAY": 5,
        "JUN": 6,
        "JUNE": 6,
        "JUL": 7,
        "JULY": 7,
        "AUG": 8,
        "AUGUST": 8,
        "SEP": 9,
        "SEPT": 9,
        "SEPTEMBER": 9,
        "OCT": 10,
        "OCTOBER": 10,
        "NOV": 11,
        "NOVEMBER": 11,
        "DEC": 12,
        "DECEMBER": 12,
    }
    m = re.match(r"([A-Za-z]+)\s+(\d{4})$", label.strip())
    if m:
        mo = months.get(m.group(1).upper())
        if mo:
            return int(m.group(2)), mo
    m = re.match(r"(\d{4})-(\d{2})$", label.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _iso_date(label: str | None) -> str | None:
    if not label:
        return None
    m = re.search(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})", label)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _quarter_token(label: str | None) -> str | None:
    if not label:
        return None
    m = re.search(r"(20\d{2})\s*Q\s*([1-4])|(20\d{2})Q([1-4])|Q([1-4])\s*(20\d{2})", label, re.I)
    if not m:
        return None
    if m.group(1) and m.group(2):
        return f"{m.group(1)}Q{m.group(2)}"
    if m.group(3) and m.group(4):
        return f"{m.group(3)}Q{m.group(4)}"
    if m.group(5) and m.group(6):
        return f"{m.group(6)}Q{m.group(5)}"
    return None


def production_behind(source: CmsSource, cms: CmsObservedState, prod: ProductionObservedState) -> bool | None:
    """Return True/False/None(unknown) whether production lags CMS vintage."""
    if not prod.status_known:
        return None
    cms_v = cms.data_vintage_label
    prod_v = prod.vintage_label
    if not cms_v or not prod_v:
        return None

    if source.source_id == "provider_information":
        cms_ym = _month_label_to_ym(cms_v)
        prod_ym = _month_label_to_ym(prod_v)
        if cms_ym and prod_ym:
            return cms_ym > prod_ym
        return _norm_token(cms_v) != _norm_token(prod_v)

    if source.source_id == "pbj_nurse_staffing":
        cq = _quarter_token(cms_v) or _quarter_token(cms.temporal or "")
        # temporal end 2026-03-31 ≈ 2026Q1
        if not cq and cms.temporal:
            m = re.search(r"/(20\d{2})-(\d{2})-(\d{2})$", cms.temporal)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                q = (mo - 1) // 3 + 1
                cq = f"{y}Q{q}"
        pq = _quarter_token(prod_v)
        if cq and pq:
            return cq != pq and cq > pq
        return None

    if source.source_id in ("snf_all_owners", "snf_enrollments"):
        c = _iso_date(cms_v) or _iso_date(cms.distribution_filename)
        p = _iso_date(prod_v)
        if c and p:
            return c > p
        return _norm_token(c or cms_v) != _norm_token(p or prod_v)

    if source.source_id == "chain_performance":
        # CMS Chain_Performance_YYYYMMDD vs local Mon YYYY
        cms_iso = _iso_date(cms_v)
        prod_ym = _month_label_to_ym(prod_v)
        if cms_iso and prod_ym:
            cy, cm = int(cms_iso[:4]), int(cms_iso[5:7])
            return (cy, cm) > prod_ym
        return _norm_token(cms_v) != _norm_token(prod_v)

    if source.source_id == "snf_chow":
        # Production label like "Q2 2026"; CMS file date 2026-07-17
        # If CMS file date is newer than coverage_date_max / not matching release, behind.
        cms_iso = _iso_date(cms_v) or _iso_date(cms.distribution_filename)
        cov = prod.detail.get("coverage_date_max")
        if cms_iso and cov:
            return str(cms_iso) > str(cov)
        # Different release labels ⇒ treat as behind when CMS filename not reflected
        return _norm_token(cms_v) != _norm_token(prod_v)

    return None


def evaluate_source(
    source: CmsSource,
    *,
    cms: CmsObservedState | None,
    production: ProductionObservedState,
    previous_fingerprint: str | None,
    check_error: str | None = None,
) -> SourceEvaluation:
    statuses: list[str] = []
    if check_error or cms is None:
        statuses.append("CHECK_FAILED")
        return SourceEvaluation(
            source_id=source.source_id,
            title=source.title,
            statuses=statuses,
            cms=None,
            production=production.to_dict(),
            previous_cms_fingerprint=previous_fingerprint,
            affected_surfaces=list(source.surfaces),
            affected_downstream=[
                {
                    "name": a.name,
                    "path": a.path_glob,
                    "persistence": a.persistence,
                }
                for a in source.downstream
            ],
            summary=f"CHECK_FAILED: {check_error or 'missing CMS state'}",
            check_error=check_error or "missing CMS state",
        )

    assert cms is not None
    new_release = bool(previous_fingerprint) and previous_fingerprint != cms.raw_fingerprint
    metadata_changed = new_release  # fingerprint includes modified/released/filename/url

    if new_release:
        statuses.append("NEW_RELEASE")
    if metadata_changed and not new_release:
        statuses.append("METADATA_CHANGED")

    behind = production_behind(source, cms, production)
    if behind is True:
        statuses.append("PRODUCTION_BEHIND")
    elif behind is False and not statuses:
        statuses.append("CURRENT")
    elif behind is False and statuses:
        # CMS advanced relative to prior watcher state but production already matches CMS
        pass
    elif behind is None:
        statuses.append("DOWNSTREAM_UNKNOWN")

    # Downstream: if production behind, list artifacts as needing refresh; else if unknown probe
    downstream_rows = []
    any_unknown = False
    for art in source.downstream:
        row = {
            "name": art.name,
            "path": art.path_glob,
            "persistence": art.persistence,
            "freshness": "STALE_IF_SOURCE_REFRESHED" if behind else (
                "UNKNOWN" if art.freshness_probe == "unknown" or behind is None else "OK"
            ),
        }
        if row["freshness"] == "UNKNOWN":
            any_unknown = True
        downstream_rows.append(row)

    if behind is True and any_unknown:
        if "DOWNSTREAM_STALE" not in statuses:
            statuses.append("DOWNSTREAM_STALE")
        if "DOWNSTREAM_UNKNOWN" not in statuses:
            statuses.append("DOWNSTREAM_UNKNOWN")
    elif behind is True:
        if "DOWNSTREAM_STALE" not in statuses:
            statuses.append("DOWNSTREAM_STALE")
    elif behind is None and "DOWNSTREAM_UNKNOWN" not in statuses:
        statuses.append("DOWNSTREAM_UNKNOWN")

    if not statuses:
        statuses.append("CURRENT")

    # De-dupe while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for status in statuses:
        if status not in seen:
            seen.add(status)
            deduped.append(status)
    statuses = deduped

    cms_label = cms.data_vintage_label or cms.distribution_filename or cms.modified or "?"
    prod_label = production.vintage_label or "UNKNOWN"
    summary = (
        f"CMS CURRENT: {cms_label} | PBJ320 CURRENT: {prod_label} | STATUS: {', '.join(statuses)}"
    )

    return SourceEvaluation(
        source_id=source.source_id,
        title=source.title,
        statuses=statuses,
        cms=cms.to_dict(),
        production=production.to_dict(),
        previous_cms_fingerprint=previous_fingerprint,
        affected_surfaces=list(source.surfaces),
        affected_downstream=downstream_rows,
        summary=summary,
        check_error=None,
    )
