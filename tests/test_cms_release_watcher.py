"""Tests for the read-only CMS release watcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cms_watcher.cms_fetch import CmsObservedState, fetch_cms_state, fetch_provider_data_metastore
from cms_watcher.compare import evaluate_source, production_behind
from cms_watcher.notify import issue_body, issue_title, maybe_create_issue
from cms_watcher.production_state import read_production_state
from cms_watcher.registry import SOURCE_REGISTRY, get_source
from cms_watcher.state_store import load_state, save_state, update_source_observation
from cms_watcher.__main__ import run_watch

ROOT = Path(__file__).resolve().parents[1]


def test_registry_covers_required_sources():
    ids = {s.source_id for s in SOURCE_REGISTRY}
    for required in (
        "provider_information",
        "pbj_nurse_staffing",
        "pbj_nonnurse_staffing",
        "pbj_employee_detail",
        "snf_all_owners",
        "snf_enrollments",
        "snf_chow",
        "chain_performance",
    ):
        assert required in ids


def test_production_provider_is_july_2026():
    prod = read_production_state("provider_information", root=ROOT)
    assert prod.status_known
    assert prod.vintage_label == "Jul 2026"


def test_production_pbj_is_2026q1():
    prod = read_production_state("pbj_nurse_staffing", root=ROOT)
    assert prod.status_known
    assert prod.vintage_label == "2026Q1"


def test_production_ownership_active_release():
    owners = read_production_state("snf_all_owners", root=ROOT)
    assert owners.status_known
    assert owners.vintage_label == "2026-07-31"
    assert owners.detail.get("ownership_source_filename") == "SNF_All_Owners_2026.07.31.csv"

    enr = read_production_state("snf_enrollments", root=ROOT)
    assert enr.status_known
    assert enr.vintage_label == "2026-07-31"


def _provider_metastore_payload():
    return {
        "title": "Provider Information",
        "identifier": "4pq5-n9py",
        "released": "2026-08-26",
        "modified": "2026-08-01",
        "nextUpdateDate": "2026-09-30",
        "distribution": [
            {
                "identifier": "dist-1",
                "data": {
                    "@type": "dcat:Distribution",
                    "downloadURL": (
                        "https://data.cms.gov/provider-data/sites/default/files/resources/"
                        "abc_1/NH_ProviderInfo_Aug2026.csv"
                    ),
                    "mediaType": "text/csv",
                },
            }
        ],
    }


def test_provider_metastore_parse_aug_2026():
    src = get_source("provider_information")
    observed = fetch_provider_data_metastore(
        src,
        fetch_json=lambda url, headers=None: _provider_metastore_payload(),
    )
    assert observed.data_vintage_label == "Aug 2026"
    assert observed.distribution_filename == "NH_ProviderInfo_Aug2026.csv"
    assert observed.released == "2026-08-26"
    assert observed.next_update_date == "2026-09-30"


def test_provider_behind_aug_vs_july():
    src = get_source("provider_information")
    cms = fetch_provider_data_metastore(
        src,
        fetch_json=lambda url, headers=None: _provider_metastore_payload(),
    )
    prod = read_production_state("provider_information", root=ROOT)
    assert production_behind(src, cms, prod) is True
    ev = evaluate_source(src, cms=cms, production=prod, previous_fingerprint=None)
    assert "PRODUCTION_BEHIND" in ev.statuses
    assert "NEW_RELEASE" not in ev.statuses  # first observation seeds; no prior fingerprint


def test_new_release_detected_when_prior_fingerprint_differs():
    src = get_source("provider_information")
    cms = fetch_provider_data_metastore(
        src,
        fetch_json=lambda url, headers=None: _provider_metastore_payload(),
    )
    prod = read_production_state("provider_information", root=ROOT)
    ev = evaluate_source(
        src,
        cms=cms,
        production=prod,
        previous_fingerprint="old-fingerprint",
    )
    assert "NEW_RELEASE" in ev.statuses
    assert "PRODUCTION_BEHIND" in ev.statuses


def test_unchanged_second_run_no_new_release(tmp_path: Path):
    src = get_source("provider_information")
    cms = fetch_provider_data_metastore(
        src,
        fetch_json=lambda url, headers=None: _provider_metastore_payload(),
    )
    prod = read_production_state("provider_information", root=ROOT)
    ev1 = evaluate_source(src, cms=cms, production=prod, previous_fingerprint=None)
    state_path = tmp_path / "watcher_state.json"
    state = load_state(state_path)
    update_source_observation(
        state,
        source_id=src.source_id,
        cms_fingerprint=cms.raw_fingerprint,
        cms_snapshot=cms.to_dict(),
        production_snapshot=prod.to_dict(),
        statuses=ev1.statuses,
    )
    save_state(state_path, state)

    state2 = load_state(state_path)
    prev_fp = state2["sources"][src.source_id]["cms_fingerprint"]
    ev2 = evaluate_source(src, cms=cms, production=prod, previous_fingerprint=prev_fp)
    assert "NEW_RELEASE" not in ev2.statuses
    assert maybe_create_issue(ev2, dry_run=True)["action"] == "skipped"


def test_pbj_current_when_cms_matches_2026q1():
    src = get_source("pbj_nurse_staffing")
    cms = CmsObservedState(
        source_id=src.source_id,
        title=src.title,
        stable_key=src.stable_key,
        catalog=src.catalog,
        released=None,
        modified="2026-07-29",
        next_update_date=None,
        temporal="2017-01-01/2026-03-31",
        distribution_filename="PBJ_dailynursestaffing_CY2026Q1.csv",
        distribution_url="https://example.invalid/PBJ_dailynursestaffing_CY2026Q1.csv",
        distribution_identifier=None,
        data_vintage_label="2026Q1",
        raw_fingerprint="fp-pbj-2026q1",
    )
    prod = read_production_state("pbj_nurse_staffing", root=ROOT)
    assert production_behind(src, cms, prod) is False
    ev = evaluate_source(src, cms=cms, production=prod, previous_fingerprint="fp-pbj-2026q1")
    assert "CURRENT" in ev.statuses
    assert "PRODUCTION_BEHIND" not in ev.statuses


def test_ownership_distinguishes_cms_file_date_and_policy():
    src = get_source("snf_all_owners")
    cms = CmsObservedState(
        source_id=src.source_id,
        title=src.title,
        stable_key=src.stable_key,
        catalog=src.catalog,
        released=None,
        modified="2026-08-17",
        next_update_date=None,
        temporal="2022-09-01/2026-08-31",
        distribution_filename="SNF_All_Owners_2026.07.31.csv",
        distribution_url="https://example.invalid/SNF_All_Owners_2026.07.31.csv",
        distribution_identifier=None,
        data_vintage_label="2026-07-31",
        raw_fingerprint="fp-owners",
    )
    prod = read_production_state("snf_all_owners", root=ROOT)
    assert production_behind(src, cms, prod) is False
    assert prod.detail.get("active_release_date") == "2026-07-31"
    # CMS catalog modified can be Aug while file vintage remains 2026-07-31
    assert cms.modified == "2026-08-17"
    assert cms.data_vintage_label == "2026-07-31"


def test_issue_body_lists_downstream_and_surfaces():
    src = get_source("provider_information")
    cms = fetch_provider_data_metastore(
        src,
        fetch_json=lambda url, headers=None: _provider_metastore_payload(),
    )
    prod = read_production_state("provider_information", root=ROOT)
    ev = evaluate_source(src, cms=cms, production=prod, previous_fingerprint="old")
    title = issue_title(ev)
    assert "Provider Information" in title
    assert "Aug 2026" in title
    body = issue_body(ev)
    assert "CMS CURRENT" in body
    assert "PBJ320 CURRENT" in body
    assert "dynamic_provider" in body
    assert "ProviderInfoNorm" in body


def test_run_watch_does_not_modify_production_artifacts(tmp_path: Path):
    """Watcher may only write its state file under an isolated path."""
    # Snapshot mtimes of a few production artifacts
    watched = [
        ROOT / "ownership" / "ownership_release_policy.json",
        ROOT / "latest_quarter_data.json",
        ROOT / "provider_info" / "ProviderInfoNorm_2026_07.csv",
        ROOT / "chow_index.json",
    ]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}

    state_path = tmp_path / "watcher_state.json"
    # Use mocked fetch via monkeypatch on fetch_cms_state would be ideal; here we allow live
    # network but assert production files untouched. If offline, still assert state-only write.

    def fake_fetch(source, fetch_json=None, catalog_cache=None):
        if source.source_id == "provider_information":
            return fetch_provider_data_metastore(
                source,
                fetch_json=lambda url, headers=None: _provider_metastore_payload(),
            )
        return CmsObservedState(
            source_id=source.source_id,
            title=source.title,
            stable_key=source.stable_key,
            catalog=source.catalog,
            released=None,
            modified="2026-01-01",
            next_update_date=None,
            temporal=None,
            distribution_filename="dummy.csv",
            distribution_url="https://example.invalid/dummy.csv",
            distribution_identifier=None,
            data_vintage_label="dummy",
            raw_fingerprint=f"fp-{source.source_id}",
        )

    import cms_watcher.__main__ as main_mod

    original = main_mod.fetch_cms_state
    main_mod.fetch_cms_state = fake_fetch
    try:
        report = run_watch(
            root=ROOT,
            state_path=state_path,
            write_state=True,
            notify=False,
            dry_run_notify=True,
            source_ids=["provider_information", "pbj_nurse_staffing"],
        )
    finally:
        main_mod.fetch_cms_state = original

    assert state_path.is_file()
    after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}
    assert before == after
    assert report["wrote_state"] is True


@pytest.mark.live
def test_live_cms_provider_aug_2026_and_pbj_q1():
    """Optional live network check against CMS (skipped unless --live / RUN_LIVE_CMS=1)."""
    import os

    if os.environ.get("RUN_LIVE_CMS") != "1":
        pytest.skip("Set RUN_LIVE_CMS=1 to hit live CMS metadata")

    provider = get_source("provider_information")
    cms_pi = fetch_cms_state(provider)
    assert cms_pi.data_vintage_label == "Aug 2026"
    prod_pi = read_production_state("provider_information", root=ROOT)
    assert production_behind(provider, cms_pi, prod_pi) is True

    nurse = get_source("pbj_nurse_staffing")
    cms_pbj = fetch_cms_state(nurse)
    assert "2026Q1" in (cms_pbj.data_vintage_label or cms_pbj.distribution_filename or "")
    prod_pbj = read_production_state("pbj_nurse_staffing", root=ROOT)
    assert production_behind(nurse, cms_pbj, prod_pbj) is False
