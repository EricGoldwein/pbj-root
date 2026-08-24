from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_provider_cold_path_has_no_retry_interstitial_or_global_admission_gate():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Another facility page is being prepared" not in source
    assert "Provider page is loading" not in source
    assert "_provider_cold_render_semaphore" not in source
    assert "queue_rejected" not in source


def test_always_run_deploy_gate_ensures_ownership_runtime_index():
    source = (ROOT / "scripts" / "ensure_deploy_csvs.py").read_text(encoding="utf-8")
    assert "snf_owners_lookup.sqlite" in source
    assert "build_snf_owners_index.py" in source
    assert "idx_enrollment_pac" in source
    assert "idx_owner_pac" in source
