"""Citation-ready provenance helpers for public MCP / JSON responses."""

from __future__ import annotations

from typing import Any, Literal

from site_public_config import (
    CMS_PBJ_DAILY_DATASET_URL,
    CMS_PBJ_STAFFING_SUBMISSION_URL,
    CMS_PROVIDER_INFO_DATASET_URL,
    PUBLIC_SITE_ORIGIN,
)

CMS_AGENCY = "Centers for Medicare & Medicaid Services (CMS)"
CMS_PBJ_DAILY_DATASET = "CMS Payroll-Based Journal Daily Nurse Staffing"
CMS_PBJ_QUARTERLY_DATASET = "CMS Payroll-Based Journal Nursing Home Staffing"
CMS_SNF_OWNERS_DATASET = "CMS SNF All Owners"
CMS_PROVIDER_INFO_DATASET = "CMS Provider Information"
CMS_SNF_OWNERS_DATASET_URL = (
    "https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/"
    "skilled-nursing-facility-all-owners"
)

ValueOrigin = Literal["cms_published", "pbj320_derived", "mixed"]


def absolute_url(path: str, origin: str | None = None) -> str:
    base = (origin or PUBLIC_SITE_ORIGIN).rstrip("/")
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return f"{base}{p}"


def _dataset_entry(
    *,
    name: str,
    dataset_url: str,
    value_origin: ValueOrigin,
    fields: list[str] | None = None,
    release: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "dataset_url": dataset_url,
        "value_origin": value_origin,
    }
    if release:
        row["release"] = release
    if fields:
        row["fields"] = fields
    return row


def build_citation(
    *,
    datasets: list[dict[str, Any]],
    period: dict[str, str] | None = None,
    canonical_url: str = "",
    methodology_url: str = "",
    agency: str = CMS_AGENCY,
) -> dict[str, Any]:
    """Human-readable CMS → PBJ320 citation block (secondary to primary tool payload)."""
    cite: dict[str, Any] = {"agency": agency, "datasets": datasets}
    if period:
        cite["period"] = period
    if methodology_url:
        cite["methodology_url"] = absolute_url(methodology_url)
    if canonical_url:
        cite["canonical_url"] = (
            canonical_url if canonical_url.startswith("http") else absolute_url(canonical_url)
        )
    return cite


def facility_profile_citation(*, quarter: str | None, canonical_url: str = "") -> dict[str, Any]:
    q = str(quarter or "").strip()
    return build_citation(
        period={"quarter": q} if q else {},
        canonical_url=canonical_url,
        methodology_url="/data-sources#methodology",
        datasets=[
            _dataset_entry(
                name=CMS_PBJ_QUARTERLY_DATASET,
                dataset_url=CMS_PBJ_STAFFING_SUBMISSION_URL,
                value_origin="pbj320_derived",
                release=q or None,
                fields=["staffing HPRD metrics", "state_percentiles"],
            ),
            _dataset_entry(
                name=CMS_PROVIDER_INFO_DATASET,
                dataset_url=CMS_PROVIDER_INFO_DATASET_URL,
                value_origin="cms_published",
                fields=["cms_ratings", "address"],
            ),
        ],
    )


def owner_portfolio_citation(*, ownership_release: str | None, canonical_url: str = "") -> dict[str, Any]:
    rel = str(ownership_release or "").strip()
    return build_citation(
        period={"ownership_release": rel} if rel else {},
        canonical_url=canonical_url,
        methodology_url="/data-sources#ownership",
        datasets=[
            _dataset_entry(
                name=CMS_SNF_OWNERS_DATASET,
                dataset_url=CMS_SNF_OWNERS_DATASET_URL,
                value_origin="cms_published",
                release=rel or None,
                fields=["owner identity", "portfolio facilities", "roles"],
            ),
        ],
    )


def daily_staffing_evidence_citation(
    *,
    quarter: str | None,
    work_date: str,
    canonical_url: str = "",
) -> dict[str, Any]:
    q = str(quarter or "").strip()
    return build_citation(
        period={"work_date": work_date, "quarter": q} if work_date or q else {},
        canonical_url=canonical_url,
        methodology_url="/data-sources#pbj-daily-staffing",
        datasets=[
            _dataset_entry(
                name=CMS_PBJ_DAILY_DATASET,
                dataset_url=CMS_PBJ_DAILY_DATASET_URL,
                value_origin="mixed",
                release=q or None,
                fields=["CMS hour and census inputs (cms_published)", "HPRD metric (pbj320_derived at build)"],
            ),
        ],
    )


def pbj_staffing_period_block(quarter: str | None) -> dict[str, str]:
    q = str(quarter or "").strip()
    out: dict[str, str] = {}
    if q:
        out["quarter"] = q
    return out


def cms_pbj_source_block(*, quarter: str | None = None) -> dict[str, Any]:
    block: dict[str, Any] = {
        "agency": CMS_AGENCY,
        "dataset": CMS_PBJ_DAILY_DATASET,
        "dataset_url": CMS_PBJ_DAILY_DATASET_URL,
    }
    block.update(pbj_staffing_period_block(quarter))
    return block


def pbj320_derived_block(*, metric: str, description: str, methodology_url: str) -> dict[str, Any]:
    return {
        "publisher": "PBJ320",
        "derived": True,
        "metric": metric,
        "description": description,
        "methodology_url": absolute_url(methodology_url),
    }


def attach_citation_envelope(
    payload: dict[str, Any],
    *,
    canonical_url: str = "",
    methodology_url: str = "/data-sources#methodology",
    evidence_url: str = "",
    quarter: str | None = None,
    ownership_release: str | None = None,
    caveats: list[str] | None = None,
    citation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap a tool result with citation metadata (does not dominate primary payload)."""
    out = dict(payload)
    if citation is None:
        if ownership_release:
            citation = owner_portfolio_citation(
                ownership_release=ownership_release,
                canonical_url=canonical_url,
            )
        else:
            citation = facility_profile_citation(quarter=quarter, canonical_url=canonical_url)
    out["citation"] = citation
    # Compact legacy alias for consumers expecting `source`
    primary = (citation.get("datasets") or [{}])[0]
    out["source"] = {
        "agency": citation.get("agency", CMS_AGENCY),
        "dataset": primary.get("name", CMS_PBJ_QUARTERLY_DATASET),
        "dataset_url": primary.get("dataset_url", CMS_PBJ_STAFFING_SUBMISSION_URL),
        **({"quarter": quarter} if quarter else {}),
        **({"ownership_release": ownership_release} if ownership_release else {}),
    }
    if canonical_url:
        out["canonical_url"] = (
            canonical_url if str(canonical_url).startswith("http") else absolute_url(canonical_url)
        )
    if methodology_url and "methodology_url" not in out:
        out["methodology_url"] = absolute_url(methodology_url)
    if evidence_url:
        out["evidence_url"] = evidence_url
    if caveats:
        out["caveats"] = list(caveats)
    return out
