#!/usr/bin/env python3
"""Write data/deploy/sitemap.xml at deploy (never on the live Gunicorn worker).

Run after build_state_page_aggregates.py / ensure_deploy_csvs so search_index and
owner_indexability_cache exist. Verified from: app.py _build_sitemap_xml().
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_OUT = REPO / "data" / "deploy" / "sitemap.xml"


def main() -> int:
    t0 = time.perf_counter()
    out = Path(os.environ.get("PBJ_SITEMAP_BUILD_PATH", str(DEFAULT_OUT)))
    out.parent.mkdir(parents=True, exist_ok=True)

    import app as app_mod  # noqa: E402

    xml = app_mod._build_sitemap_xml()
    out.write_text(xml, encoding="utf-8")
    n_urls = xml.count("<url>")
    elapsed = time.perf_counter() - t0
    print(
        f"[build_sitemap_xml] wrote {out} urls={n_urls} bytes={len(xml.encode('utf-8'))} "
        f"elapsed_s={elapsed:.1f}",
        flush=True,
    )
    if n_urls < 10:
        print("[build_sitemap_xml] WARNING: very few URLs — check search_index / owner cache", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
