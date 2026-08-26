"""CMS source registry and PBJ320 downstream dependency map.

This module is documentation-as-code: the watcher uses it to label which
surfaces/artifacts would need a human refresh when CMS advances. It does not
rebuild anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CatalogKind = Literal["provider_data_metastore", "cms_data_json"]
Surface = Literal[
    "public_staffing",
    "dynamic_provider",
    "ownership",
    "premium",
    "legacy",
    "compliance",
]


@dataclass(frozen=True)
class DownstreamArtifact:
    """One derived thing that depends on a CMS source."""

    name: str
    path_glob: str
    transform: str
    consumer: str
    persistence: Literal[
        "committed",
        "manual_pre_commit",
        "render_build",
        "runtime_memory",
        "premium_only",
        "legacy_only",
        "external_unproven",
    ]
    surfaces: tuple[Surface, ...]
    freshness_probe: Literal[
        "filename_date",
        "policy_active_release",
        "latest_quarter_json",
        "national_csv_max_quarter",
        "chow_index_meta",
        "combined_processing_date",
        "unknown",
    ] = "unknown"


@dataclass(frozen=True)
class CmsSource:
    """Stable CMS dataset identity + how we read production vintage."""

    source_id: str
    title: str
    catalog: CatalogKind
    # provider-data metastore dataset id OR data.json UUID
    stable_key: str
    # Exact data.json title match when catalog=cms_data_json
    data_json_title: str | None = None
    surfaces: tuple[Surface, ...] = ()
    production_probe: str = "unknown"
    downstream: tuple[DownstreamArtifact, ...] = field(default_factory=tuple)
    notes: str = ""


SOURCE_REGISTRY: tuple[CmsSource, ...] = (
    CmsSource(
        source_id="provider_information",
        title="Provider Information",
        catalog="provider_data_metastore",
        stable_key="4pq5-n9py",
        surfaces=("public_staffing", "dynamic_provider", "ownership", "compliance"),
        production_probe="provider_info_norm_month",
        notes=(
            "Care Compare monthly nursing-home provider snapshot. "
            "PBJ320 serves ProviderInfoNorm_YYYY_MM (often via PBJapp handoff)."
        ),
        downstream=(
            DownstreamArtifact(
                name="ProviderInfoNorm snapshot",
                path_glob="provider_info/ProviderInfoNorm_YYYY_MM.csv",
                transform="PBJapp normalize + copy handoff (manual)",
                consumer="provider pages, /api/dates, report pin, ownership CMI",
                persistence="committed",
                surfaces=("dynamic_provider", "public_staffing", "ownership"),
                freshness_probe="filename_date",
            ),
            DownstreamArtifact(
                name="provider_info_combined_latest",
                path_glob="provider_info_combined_latest.csv",
                transform="manual extract/combine before commit",
                consumer="ownership legal names, search enrichment, report",
                persistence="committed",
                surfaces=("dynamic_provider", "ownership"),
                freshness_probe="combined_processing_date",
            ),
            DownstreamArtifact(
                name="facility provider indexes",
                path_glob="data/provider_indexes/*",
                transform="scripts/build_facility_provider_indexes.py",
                consumer="/provider/<ccn> cold path",
                persistence="render_build",
                surfaces=("dynamic_provider",),
                freshness_probe="unknown",
            ),
            DownstreamArtifact(
                name="search_index.json",
                path_glob="search_index.json",
                transform="generate_search_index.py (manual pre-commit)",
                consumer="homepage/search",
                persistence="committed",
                surfaces=("public_staffing", "dynamic_provider"),
                freshness_probe="unknown",
            ),
            DownstreamArtifact(
                name="provider HTML TTL cache",
                path_glob="(process memory)",
                transform="app.py provider page cache (TTL ~900s)",
                consumer="/provider/<ccn>",
                persistence="runtime_memory",
                surfaces=("dynamic_provider",),
                freshness_probe="unknown",
            ),
        ),
    ),
    CmsSource(
        source_id="pbj_nurse_staffing",
        title="Payroll Based Journal Daily Nurse Staffing",
        catalog="cms_data_json",
        stable_key="7e0d53ba-8f02-4c66-98a5-14a1c997c50d",
        data_json_title="Payroll Based Journal Daily Nurse Staffing",
        surfaces=("public_staffing", "dynamic_provider", "compliance", "premium"),
        production_probe="pbj_latest_quarter",
        notes="Quarterly daily nurse hours → facility_quarterly_metrics pipeline (PBJapp) → pbj-root gz.",
        downstream=(
            DownstreamArtifact(
                name="facility_quarterly_metrics.csv.gz",
                path_glob="facility_quarterly_metrics.csv.gz",
                transform="PBJapp generate_metrics → gzip; commit",
                consumer="Render decompress → provider/state/entity pages",
                persistence="committed",
                surfaces=("public_staffing", "dynamic_provider"),
                freshness_probe="national_csv_max_quarter",
            ),
            DownstreamArtifact(
                name="facility_quarterly_metrics.csv",
                path_glob="facility_quarterly_metrics.csv",
                transform="scripts/ensure_deploy_csvs.py (Render build)",
                consumer="runtime loaders",
                persistence="render_build",
                surfaces=("public_staffing", "dynamic_provider"),
                freshness_probe="national_csv_max_quarter",
            ),
            DownstreamArtifact(
                name="national_quarterly_metrics.csv",
                path_glob="national_quarterly_metrics.csv",
                transform="manual aggregate from facility metrics",
                consumer="charts, /api/dates data_range",
                persistence="committed",
                surfaces=("public_staffing",),
                freshness_probe="national_csv_max_quarter",
            ),
            DownstreamArtifact(
                name="state_quarterly_metrics.csv",
                path_glob="state_quarterly_metrics.csv",
                transform="manual aggregate + patch_state_quarterly_medians.py",
                consumer="/state/*, /report",
                persistence="committed",
                surfaces=("public_staffing",),
                freshness_probe="national_csv_max_quarter",
            ),
            DownstreamArtifact(
                name="latest_quarter_data.json",
                path_glob="latest_quarter_data.json",
                transform="generate_dynamic_data_json.py",
                consumer="homepage, /api/dates",
                persistence="committed",
                surfaces=("public_staffing",),
                freshness_probe="latest_quarter_json",
            ),
            DownstreamArtifact(
                name="state_page_aggregates.json.gz",
                path_glob="data/state_page_aggregates.json.gz",
                transform="scripts/build_state_page_aggregates.py",
                consumer="/state/* hydrate",
                persistence="render_build",
                surfaces=("public_staffing",),
                freshness_probe="unknown",
            ),
            DownstreamArtifact(
                name="staffing compliance bundle",
                path_glob="data/compliance/staffing_compliance_*",
                transform="PBJapp export → ensure/build on Render",
                consumer="provider takeaway compliance bullets",
                persistence="committed",
                surfaces=("compliance", "dynamic_provider"),
                freshness_probe="unknown",
            ),
            DownstreamArtifact(
                name="premium facility nurse slices",
                path_glob="(PBJapp deployments/pbj320-<CCN>/)",
                transform="create_vercel_deployment.py (manual)",
                consumer="Vercel /premium/<ccn>",
                persistence="premium_only",
                surfaces=("premium",),
                freshness_probe="unknown",
            ),
        ),
    ),
    CmsSource(
        source_id="pbj_nonnurse_staffing",
        title="Payroll Based Journal Daily Non-Nurse Staffing",
        catalog="cms_data_json",
        stable_key="b497431a-5b57-42c0-9016-90105b51841e",
        data_json_title="Payroll Based Journal Daily Non-Nurse Staffing",
        surfaces=("premium",),
        production_probe="unknown",
        notes="Used in PBJapp/premium facility dashboards; not a separate public pbj-root national series.",
        downstream=(
            DownstreamArtifact(
                name="premium non-nurse facility slices",
                path_glob="(PBJapp deployments/pbj320-<CCN>/facility_*_nonnurse_daily.csv)",
                transform="PBJapp packaging",
                consumer="Vercel premium dashboards",
                persistence="premium_only",
                surfaces=("premium",),
                freshness_probe="unknown",
            ),
        ),
    ),
    CmsSource(
        source_id="pbj_employee_detail",
        title="Payroll Based Journal Employee Detail Nursing Home Staffing",
        catalog="cms_data_json",
        stable_key="d65b8be0-946e-410b-ab06-01829628d5a1",
        data_json_title="Payroll Based Journal Employee Detail Nursing Home Staffing",
        surfaces=("premium",),
        production_probe="unknown",
        notes="EIN PUF — premium/PBJapp only; public pbj-root does not serve EIN.",
        downstream=(
            DownstreamArtifact(
                name="EIN national + facility analytics",
                path_glob="(PBJapp EIN/ + deployments/pbj320-<CCN>/facility_*_ein_*)",
                transform="PBJapp EIN ingest + packaging",
                consumer="Vercel premium EIN panels",
                persistence="premium_only",
                surfaces=("premium",),
                freshness_probe="unknown",
            ),
        ),
    ),
    CmsSource(
        source_id="snf_all_owners",
        title="Skilled Nursing Facility All Owners",
        catalog="cms_data_json",
        stable_key="afe44b85-cc6d-40d7-b5df-00ae8910d1d2",
        data_json_title="Skilled Nursing Facility All Owners",
        surfaces=("ownership", "dynamic_provider"),
        production_probe="ownership_active_release",
        notes="Pinned by ownership/ownership_release_policy.json active_release_date (not glob-latest).",
        downstream=(
            DownstreamArtifact(
                name="active SNF_All_Owners CSV",
                path_glob="ownership/SNF_All_Owners_*.csv",
                transform="manual download + policy pin",
                consumer="ownership indexes / profiles",
                persistence="committed",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
            DownstreamArtifact(
                name="snf_owners_org_index.json.gz",
                path_glob="ownership/snf_owners_org_index.json.gz",
                transform="scripts/build_snf_owners_index.py",
                consumer="/owners hub + PAC profiles",
                persistence="render_build",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
            DownstreamArtifact(
                name="snf_owners_ccn_index.json.gz",
                path_glob="ownership/snf_owners_ccn_index.json.gz",
                transform="scripts/build_snf_owners_ccn_index.py",
                consumer="/provider ownership panel",
                persistence="render_build",
                surfaces=("ownership", "dynamic_provider"),
                freshness_probe="policy_active_release",
            ),
            DownstreamArtifact(
                name="owners sqlite / database",
                path_glob="ownership/*owners*.sqlite*",
                transform="scripts/build_owners_database.py",
                consumer="/owners routes",
                persistence="render_build",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
            DownstreamArtifact(
                name="CCN ownership bridge lookup",
                path_glob="ownership/_derived/cms_snf_ownership_ccn_bridge/release_*_lookup.json",
                transform="bridge builders (manual pre-commit)",
                consumer="PAC↔CCN portfolio linkage",
                persistence="committed",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
        ),
    ),
    CmsSource(
        source_id="snf_enrollments",
        title="Skilled Nursing Facility Enrollments",
        catalog="cms_data_json",
        stable_key="5f2c306f-3b1c-42cd-b037-187b2ce22126",
        data_json_title="Skilled Nursing Facility Enrollments",
        surfaces=("ownership",),
        production_probe="ownership_enrollment_release",
        notes="Paired with All Owners via ownership_release_policy enrollment_source_filename.",
        downstream=(
            DownstreamArtifact(
                name="active SNF_Enrollments CSV",
                path_glob="ownership/SNF_Enrollments_*.csv",
                transform="manual download + policy pin",
                consumer="enrollment↔CCN bridge / legal names",
                persistence="committed",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
            DownstreamArtifact(
                name="enrollment pairing / bridge",
                path_glob="ownership/_derived/cms_snf_ownership_ccn_bridge/*",
                transform="manual bridge build",
                consumer="ownership indexes",
                persistence="committed",
                surfaces=("ownership",),
                freshness_probe="policy_active_release",
            ),
        ),
    ),
    CmsSource(
        source_id="snf_chow",
        title="Skilled Nursing Facility Change of Ownership",
        catalog="cms_data_json",
        stable_key="f557a6ed-95b3-4a22-8433-4175db2dec1c",
        data_json_title="Skilled Nursing Facility Change of Ownership",
        surfaces=("ownership",),
        production_probe="chow_index_meta",
        notes="chow_index.json is committed; NOT rebuilt in Render buildCommand.",
        downstream=(
            DownstreamArtifact(
                name="chow_index.json",
                path_glob="chow_index.json",
                transform="scripts/build_chow_index.py (manual)",
                consumer="CHOW UI / ownership CHOW panels",
                persistence="committed",
                surfaces=("ownership",),
                freshness_probe="chow_index_meta",
            ),
        ),
    ),
    CmsSource(
        source_id="chain_performance",
        title="Nursing Home Chain Performance Measures",
        catalog="cms_data_json",
        stable_key="97ecfad1-d3f1-4d42-b774-d74661d830bc",
        data_json_title="Nursing Home Chain Performance Measures",
        surfaces=("public_staffing", "ownership"),
        production_probe="chain_performance_month",
        notes=(
            "CMS now ships Chain_Performance_YYYYMMDD.csv; pbj-root still consumes "
            "Nursing_Home_Chain_Performance_Measures_<Mon>_<Year>.csv."
        ),
        downstream=(
            DownstreamArtifact(
                name="chain performance CSV",
                path_glob="ownership/Nursing_Home_Chain_Performance_Measures_*.csv",
                transform="manual rename/place + commit",
                consumer="entity pages, /api/entity-summary",
                persistence="committed",
                surfaces=("public_staffing", "ownership"),
                freshness_probe="filename_date",
            ),
        ),
    ),
)


def get_source(source_id: str) -> CmsSource:
    for src in SOURCE_REGISTRY:
        if src.source_id == source_id:
            return src
    raise KeyError(f"unknown CMS source_id: {source_id}")


def dependency_graph_rows() -> list[dict[str, Any]]:
    """Flat rows for docs/reporting: source → transform → artifact → consumer."""
    rows: list[dict[str, Any]] = []
    for src in SOURCE_REGISTRY:
        if not src.downstream:
            rows.append(
                {
                    "source_id": src.source_id,
                    "cms_title": src.title,
                    "artifact": "(none registered)",
                    "transform": "",
                    "consumer": "",
                    "persistence": "",
                    "surfaces": ",".join(src.surfaces),
                }
            )
            continue
        for art in src.downstream:
            rows.append(
                {
                    "source_id": src.source_id,
                    "cms_title": src.title,
                    "artifact": art.name,
                    "path": art.path_glob,
                    "transform": art.transform,
                    "consumer": art.consumer,
                    "persistence": art.persistence,
                    "surfaces": ",".join(art.surfaces),
                    "freshness_probe": art.freshness_probe,
                }
            )
    return rows
