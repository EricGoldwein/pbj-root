"""Tests for public source vintage contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from public_source_vintage import build_public_source_vintages, inject_data_sources_vintage_html


def test_build_public_source_vintages_distinct_rows(tmp_path: Path) -> None:
    (tmp_path / "latest_quarter_data.json").write_text(
        json.dumps({"quarter": "2026Q1", "quarter_display": "Q1 2026"}),
        encoding="utf-8",
    )
    (tmp_path / "provider_info").mkdir()
    (tmp_path / "provider_info" / "ProviderInfoNorm_2026_08.csv").write_text("ccn\n", encoding="utf-8")
    (tmp_path / "ownership").mkdir()
    (tmp_path / "ownership" / "Nursing_Home_Chain_Performance_Measures_Jun_2026.csv").write_text("a\n", encoding="utf-8")
    (tmp_path / "ownership" / "ownership_release_policy.json").write_text(
        json.dumps({"active_release_date": "2026-07-17", "releases": {"2026-07-17": {"status": "active"}}}),
        encoding="utf-8",
    )
    sff_dir = tmp_path / "data_sources" / "cms" / "sff"
    sff_dir.mkdir(parents=True)
    (sff_dir / "current_release.json").write_text(json.dumps({"source_release": "2026-08"}), encoding="utf-8")

    rows = build_public_source_vintages(tmp_path)
    by_id = {r["source_id"]: r for r in rows}
    assert by_id["cms.pbj_nurse_staffing"]["source_vintage"] == "Q1 2026"
    assert by_id["cms.provider_info"]["source_vintage"] == "August 2026"
    assert by_id["cms.sff_pdf_list"]["source_vintage"] == "August 2026"
    assert by_id["cms.chain_performance"]["source_vintage"] == "June 2026"
    assert by_id["cms.macpac_state_staffing"]["source_vintage"] == "March 2022 compendium"


def test_source_vintage_label_helper(tmp_path: Path) -> None:
    from public_source_vintage import source_vintage_label

    (tmp_path / "latest_quarter_data.json").write_text(
        json.dumps({"quarter": "2026Q1", "quarter_display": "Q1 2026"}),
        encoding="utf-8",
    )
    (tmp_path / "provider_info").mkdir()
    (tmp_path / "provider_info" / "ProviderInfoNorm_2026_08.csv").write_text("ccn\n", encoding="utf-8")

    assert source_vintage_label("cms.pbj_nurse_staffing", tmp_path) == "Q1 2026"
    assert source_vintage_label("cms.provider_info", tmp_path) == "August 2026"
    assert source_vintage_label("missing.source", tmp_path) == "—"


def test_inject_removes_hardcoded_last_updated_placeholder() -> None:
    html = "<p>Provider Information vintage: __PAGE_LAST_UPDATED__</p>__PUBLIC_SOURCE_VINTAGE_TABLE__"
    out = inject_data_sources_vintage_html(html, Path(__file__).resolve().parent)
    assert "__PAGE_LAST_UPDATED__" not in out
    assert "__PUBLIC_SOURCE_VINTAGE_TABLE__" not in out
    assert "<table" in out
