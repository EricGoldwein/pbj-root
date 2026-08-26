"""Tests for the read-only CMS release watcher (no repo state commits)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cms_watcher.cms_fetch import CmsObservedState, fetch_cms_state, fetch_provider_data_metastore
from cms_watcher.compare import evaluate_source, production_behind
from cms_watcher.notify import (
    find_issue_by_fingerprint,
    fingerprint_marker,
    issue_body,
    issue_title,
    maybe_create_issue,
    should_alert,
)
from cms_watcher.production_state import read_production_state
from cms_watcher.registry import SOURCE_REGISTRY, get_source
from cms_watcher.__main__ import run_watch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cms-release-watcher.yml"


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
    ev = evaluate_source(src, cms=cms, production=prod)
    assert "PRODUCTION_BEHIND" in ev.statuses
    assert "NEW_RELEASE" not in ev.statuses  # NEW_RELEASE only via notify/issue path


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
    ev = evaluate_source(src, cms=cms, production=prod)
    assert "CURRENT" in ev.statuses
    assert "PRODUCTION_BEHIND" not in ev.statuses
    assert should_alert(ev) is False
    assert maybe_create_issue(ev, dry_run=True)["action"] == "skipped"


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
    ev = evaluate_source(src, cms=cms, production=prod)
    title = issue_title(ev)
    assert "Provider Information" in title
    assert "Aug 2026" in title
    body = issue_body(ev)
    assert "CMS CURRENT" in body
    assert "PBJ320 CURRENT" in body
    assert "dynamic_provider" in body
    assert "ProviderInfoNorm" in body
    assert fingerprint_marker(src.source_id, cms.raw_fingerprint) in body


def _fake_fetch_factory():
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

    return fake_fetch


def test_daily_unchanged_run_no_repo_write_no_issue(tmp_path: Path):
    """Ordinary CURRENT-only path: no tracked file churn, no issue create."""
    import cms_watcher.__main__ as main_mod

    # Provider behind would alert; use only CURRENT staffing source.
    def fake_fetch(source, fetch_json=None, catalog_cache=None):
        return CmsObservedState(
            source_id=source.source_id,
            title=source.title,
            stable_key=source.stable_key,
            catalog=source.catalog,
            released=None,
            modified="2026-07-29",
            next_update_date=None,
            temporal="2017-01-01/2026-03-31",
            distribution_filename="PBJ_dailynursestaffing_CY2026Q1.csv",
            distribution_url="https://example.invalid/PBJ_dailynursestaffing_CY2026Q1.csv",
            distribution_identifier=None,
            data_vintage_label="2026Q1",
            raw_fingerprint="fp-pbj-2026q1-stable",
        )

    watched = [
        ROOT / "ownership" / "ownership_release_policy.json",
        ROOT / "latest_quarter_data.json",
        ROOT / "provider_info" / "ProviderInfoNorm_2026_07.csv",
        ROOT / "chow_index.json",
        ROOT / "data" / "cms_watcher" / "README.md",
    ]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}

    original = main_mod.fetch_cms_state
    main_mod.fetch_cms_state = fake_fetch
    try:
        report = run_watch(
            root=ROOT,
            notify=True,
            dry_run_notify=False,
            source_ids=["pbj_nurse_staffing"],
            existing_issues_by_fp={},  # no remote; CURRENT skips notify
        )
    finally:
        main_mod.fetch_cms_state = original

    after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}
    assert before == after
    assert report["wrote_repo_files"] is False
    assert report["git_commit"] is False
    assert report["git_push"] is False
    assert "last_checked_at" in report
    assert report["notifications"]
    assert report["notifications"][0]["action"] == "skipped"
    assert "CURRENT" in report["evaluations"][0]["statuses"]
    assert "NEW_RELEASE" not in report["evaluations"][0]["statuses"]
    # No watcher_state.json created under repo data path
    assert not (ROOT / "data" / "cms_watcher" / "watcher_state.json").exists()
    assert not list(tmp_path.glob("**/*"))


def test_simulated_provider_release_creates_one_issue_then_dedupes(monkeypatch):
    """New Provider Info release → one issue; second run + closed issue → no duplicate."""
    import cms_watcher.__main__ as main_mod

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "EricGoldwein/pbj-root")

    fake_fetch = _fake_fetch_factory()
    created: list[dict] = []
    issues_store: dict[str, dict] = {}

    def gh_api(method, path, *, token, body=None):
        if method == "GET" and "/search/issues" in path:
            return {"items": list(issues_store.values())}
        if method == "GET" and "/labels/" in path:
            return {"name": "cms-release-watcher"}
        if method == "POST" and path.endswith("/issues"):
            assert body is not None
            fp = None
            for line in (body.get("body") or "").splitlines():
                if "cms-release-watcher:provider_information:" in line:
                    fp = line.strip().removeprefix("<!-- ").removesuffix(" -->")
                    fp = fp.split(":")[-1]
            number = len(created) + 1
            item = {
                "number": number,
                "html_url": f"https://example.invalid/issues/{number}",
                "state": "open",
                "body": body.get("body"),
                "title": body.get("title"),
            }
            created.append(item)
            if fp:
                issues_store[f"provider_information:{fp}"] = item
            return item
        raise AssertionError(f"unexpected API call {method} {path}")

    original = main_mod.fetch_cms_state
    main_mod.fetch_cms_state = fake_fetch
    try:
        r1 = run_watch(
            root=ROOT,
            notify=True,
            dry_run_notify=False,
            source_ids=["provider_information"],
            gh_api=gh_api,
        )
        assert len(created) == 1
        assert r1["notifications"][0]["action"] == "created"
        assert "NEW_RELEASE" in r1["evaluations"][0]["statuses"]
        assert "PRODUCTION_BEHIND" in r1["evaluations"][0]["statuses"]
        fp = r1["notifications"][0]["fingerprint"]

        # Run 2: same release, open issue exists → no duplicate
        r2 = run_watch(
            root=ROOT,
            notify=True,
            dry_run_notify=False,
            source_ids=["provider_information"],
            gh_api=gh_api,
            existing_issues_by_fp={
                f"provider_information:{fp}": {
                    "number": 1,
                    "html_url": "https://example.invalid/issues/1",
                    "state": "open",
                    "body": fingerprint_marker("provider_information", fp),
                }
            },
        )
        assert len(created) == 1
        assert r2["notifications"][0]["action"] == "exists"
        assert r2["notifications"][0]["state"] == "open"
        assert "NEW_RELEASE" not in r2["evaluations"][0]["statuses"]
        assert "PRODUCTION_BEHIND" in r2["evaluations"][0]["statuses"]

        # Run 3: closed issue still dedupes
        r3 = run_watch(
            root=ROOT,
            notify=True,
            dry_run_notify=False,
            source_ids=["provider_information"],
            gh_api=gh_api,
            existing_issues_by_fp={
                f"provider_information:{fp}": {
                    "number": 1,
                    "html_url": "https://example.invalid/issues/1",
                    "state": "closed",
                    "body": fingerprint_marker("provider_information", fp),
                }
            },
        )
        assert len(created) == 1
        assert r3["notifications"][0]["action"] == "exists"
        assert r3["notifications"][0]["state"] == "closed"
        assert "NEW_RELEASE" not in r3["evaluations"][0]["statuses"]
    finally:
        main_mod.fetch_cms_state = original


def test_find_issue_searches_open_and_closed():
    import urllib.parse

    calls: list[str] = []

    def gh_api(method, path, *, token, body=None):
        calls.append(path)
        assert "is:open" not in path  # must include closed
        marker = fingerprint_marker("provider_information", "fp-abc")
        return {
            "items": [
                {
                    "number": 9,
                    "html_url": "https://example.invalid/issues/9",
                    "state": "closed",
                    "body": f"note\n{marker}\n",
                }
            ]
        }

    found = find_issue_by_fingerprint(
        "owner/repo",
        "provider_information",
        "fp-abc",
        "token",
        gh_api=gh_api,
    )
    assert found is not None
    assert found["state"] == "closed"
    decoded = urllib.parse.unquote(calls[0])
    assert "label:cms-release-watcher" in decoded
    assert "is:open" not in decoded


def test_run_watch_does_not_modify_production_artifacts():
    """Watcher must not write production artifacts or a committed state file."""
    watched = [
        ROOT / "ownership" / "ownership_release_policy.json",
        ROOT / "latest_quarter_data.json",
        ROOT / "provider_info" / "ProviderInfoNorm_2026_07.csv",
        ROOT / "chow_index.json",
    ]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}

    import cms_watcher.__main__ as main_mod

    original = main_mod.fetch_cms_state
    main_mod.fetch_cms_state = _fake_fetch_factory()
    try:
        report = run_watch(
            root=ROOT,
            notify=False,
            dry_run_notify=True,
            source_ids=["provider_information", "pbj_nurse_staffing"],
            existing_issues_by_fp={},
        )
    finally:
        main_mod.fetch_cms_state = original

    after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.is_file()}
    assert before == after
    assert report["wrote_repo_files"] is False
    assert not (ROOT / "data" / "cms_watcher" / "watcher_state.json").exists()


def test_workflow_has_no_git_write_and_read_only_contents():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "issues: write" in text
    # Executable git mutation steps must not appear (comments alone are insufficient).
    assert "git config" not in text
    assert "git add" not in text
    assert not any(
        line.strip().startswith("git commit") or line.strip().startswith("git push")
        for line in text.splitlines()
    )
    assert "--write-state" not in text
    assert "--notify" in text
    assert "permissions:" in text


def test_watcher_modules_have_no_git_commit_push_path():
    forbidden = ("git commit", "git push", "git.add", "Repo(")
    paths = list((ROOT / "cms_watcher").rglob("*.py"))
    paths.append(ROOT / "scripts" / "run_cms_release_watcher.py")
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path} contains {needle!r}"


def test_last_checked_at_is_runtime_only():
    import cms_watcher.__main__ as main_mod

    original = main_mod.fetch_cms_state
    main_mod.fetch_cms_state = _fake_fetch_factory()
    try:
        r1 = run_watch(
            root=ROOT,
            notify=False,
            dry_run_notify=False,
            source_ids=["pbj_nurse_staffing"],
        )
        r2 = run_watch(
            root=ROOT,
            notify=False,
            dry_run_notify=False,
            source_ids=["pbj_nurse_staffing"],
        )
    finally:
        main_mod.fetch_cms_state = original

    assert r1["last_checked_at"]
    assert r2["last_checked_at"]
    # Two runs may differ in timestamp; neither may create tracked state.
    assert not (ROOT / "data" / "cms_watcher" / "watcher_state.json").exists()
    readme = (ROOT / "data" / "cms_watcher" / "README.md").read_text(encoding="utf-8")
    assert "watcher_state.json" in readme
    assert "not" in readme.lower()


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
