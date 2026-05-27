#!/usr/bin/env python3
"""Precompute state-page aggregates at deploy (facility counts, case-mix, rural, high-risk).

Run after ensure_deploy_csvs.py so facility + provider CSVs exist.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import state_page_aggregates as spa  # noqa: E402


def main() -> int:
    t0 = time.perf_counter()
    # Import app after path setup (heavy; needs pandas + CSVs).
    import app as app_mod  # noqa: E402

    if not app_mod.HAS_PANDAS:
        print('[build_state_page_aggregates] pandas required', flush=True)
        return 1

    q = app_mod.get_canonical_latest_quarter()
    if not q:
        print('[build_state_page_aggregates] no canonical quarter', flush=True)
        return 1

    print(f'[build_state_page_aggregates] canonical quarter {q}', flush=True)

    facility_counts = app_mod._ensure_state_facility_counts_for_quarter(q)
    case_mix_medians = app_mod._ensure_state_case_mix_medians(q)
    national_rural, rural_by_state = app_mod.get_rural_shares_for_quarter(q)
    high_risk_val, effective_qtr = app_mod._compute_high_risk_by_state_for_quarter(q)
    if isinstance(high_risk_val, tuple) and len(high_risk_val) >= 1:
        high_risk_by_state = high_risk_val[0] if isinstance(high_risk_val[0], dict) else {}
        effective_qtr = high_risk_val[1] if len(high_risk_val) > 1 else effective_qtr
    elif isinstance(high_risk_val, dict):
        high_risk_by_state = high_risk_val
    else:
        high_risk_by_state = {}

    fq_path = app_mod._facility_quarterly_csv_path()
    provider_paths = app_mod._resolved_provider_info_paths()
    provider_path = provider_paths[0] if provider_paths else None

    bundle = {
        'version': spa.BUNDLE_VERSION,
        'built_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'canonical_quarter': str(q),
        'effective_high_risk_quarter': str(effective_qtr or q),
        'sources': {
            'facility_quarterly': spa.source_meta(fq_path, str(REPO)),
            'provider_primary': spa.source_meta(provider_path, str(REPO)),
        },
        'facility_counts_by_quarter': {str(q): facility_counts},
        'case_mix_medians_by_quarter': {str(q): case_mix_medians},
        'rural_shares_by_quarter': {
            str(q): {
                'national': national_rural,
                'states': rural_by_state or {},
            },
        },
        'high_risk_by_quarter': {str(q): high_risk_by_state},
    }

    out_path = spa.write_bundle(str(REPO), bundle)
    elapsed = time.perf_counter() - t0
    n_states_fc = len(facility_counts or {})
    n_states_cm = len(case_mix_medians or {})
    n_states_hr = len(high_risk_by_state or {})
    print(
        f'[build_state_page_aggregates] wrote {out_path} '
        f'({n_states_fc} states facility counts, {n_states_cm} case-mix, '
        f'{n_states_hr} high-risk) in {elapsed:.1f}s',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
