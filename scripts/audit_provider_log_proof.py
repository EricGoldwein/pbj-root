#!/usr/bin/env python3
"""Log proof: fast path vs fallback signals (no inline PowerShell quoting)."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import app as m

    m.clear_provider_page_cache()
    m._PROVIDER_INDEXES_HYDRATED = False
    buf = io.StringIO()
    with redirect_stdout(buf):
        c = m.app.test_client()
        c.get('/provider/676230')
        c.get('/provider/676230')
    out = buf.getvalue()
    events = (
        'provider_indexes_hydrated',
        'facility_quarterly_lookup',
        'provider_index_fallback',
        'entity_metrics_stream',
        'state_percentile_csv_rebuild',
    )
    print('LOG_PROOF')
    for ev in events:
        n = out.count('"event":"' + ev + '"')
        print(f'{ev}={n}')
    bad = (
        out.count('"event":"provider_index_fallback"')
        + out.count('"event":"entity_metrics_stream"')
        + out.count('state_percentile_csv_rebuild')
    )
    good = out.count('"event":"facility_quarterly_lookup"') >= 1
    good = good and out.count('"event":"provider_indexes_hydrated"') >= 1
    print('PASS' if good and bad == 0 else 'FAIL')
    return 0 if good and bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
