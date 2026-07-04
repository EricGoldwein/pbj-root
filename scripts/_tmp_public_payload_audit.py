#!/usr/bin/env python3
"""One-off public-site payload audit (prod)."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from html.parser import HTMLParser

BASE = "https://www.pbj320.com"
PATHS = [
    "/insights/ny-minimum-staffing",
    "/provider/335513",
    "/provider/015009",
    "/report",
    "/state/new-york",
    "/state/florida",
    "/state/connecticut",
    "/state/texas",
    "/entity/507",
    "/entity/690",
    "/entity/237",
    "/entity/217",
    "/entity/9",
    "/owners/ny",
    "/owners/ct",
    "/owners",
    "/",
]


class DomCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes = 0
        self.hidden_nodes = 0

    def handle_starttag(self, tag, attrs) -> None:
        self.nodes += 1
        d = dict(attrs)
        if d.get("hidden") is not None or d.get("aria-hidden") == "true":
            self.hidden_nodes += 1


def _first_group(pat: str, text: str) -> int:
    m = re.search(pat, text, re.S)
    return len(m.group(1)) if m else 0


def embedded_json_bytes(text: str) -> int:
    total = 0
    total += _first_group(r"var d = (\{.*?\});\s*\n\s*var textColor", text)
    total += _first_group(r"window\.__REPORT_FP_BY_STATE__\s*=\s*(\{.*?\});", text)
    total += _first_group(r"window\.__PBJ_REVIEW_FRAMEWORK__\s*=\s*(\{.*?\});", text)
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
        total += len(m.group(1))
    for m in re.finditer(r'data-try-pool="(\[.*?\])"', text):
        total += len(m.group(1))
    return total


def analyze(path: str) -> dict:
    url = BASE + path
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "PBJ320-public-payload-audit/1"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            ct = r.headers.get("content-type", "")
    except Exception as e:
        return {"path": path, "error": str(e)}
    text = body.decode("utf-8", "replace")
    if "text/html" not in (ct or "") and not text.lstrip().startswith("<"):
        return {"path": path, "bytes": len(body), "content_type": ct, "skip": "non-html"}
    counter = DomCounter()
    try:
        counter.feed(text)
    except Exception:
        pass
    hidden_dom_details = (
        len(re.findall(r'class="chow-detail-store"', text))
        + len(re.findall(r'chow-tx-row[^>]*\bhidden\b', text))
        + len(re.findall(r'entity-facility-row[^>]*style="display:\s*none', text))
        + len(re.findall(r'class="pbj-ai-csv-data"', text))
        + len(re.findall(r'class="chow-detail-stores"', text))
    )
    return {
        "path": path,
        "bytes": len(body),
        "fetch_s": round(time.perf_counter() - t0, 3),
        "dom_nodes": counter.nodes,
        "dom_hidden_nodes": counter.hidden_nodes,
        "embedded_json_bytes": embedded_json_bytes(text),
        "chart_data_var_d_bytes": _first_group(r"var d = (\{.*?\});\s*\n\s*var textColor", text),
        "hidden_csv_textareas": len(re.findall(r'class="pbj-ai-csv-data"', text)),
        "hidden_csv_bytes": sum(
            len(m.group(1)) for m in re.finditer(r'class="pbj-ai-csv-data"[^>]*>(.*?)</textarea>', text, re.S)
        ),
        "entity_facility_rows_total": len(re.findall(r'entity-facility-row', text)),
        "entity_rows_display_none": len(re.findall(r'entity-facility-row[^>]*style="display:\s*none', text)),
        "chow_detail_stores": len(re.findall(r'class="chow-detail-store"', text)),
        "chow_lazy_buttons": len(re.findall(r'data-chow-lazy-id=', text)),
        "chow_paginated_hidden_rows": len(re.findall(r'chow-tx-row[^>]*\bhidden\b', text)),
        "state_hr_ssr_rows": len(re.findall(r'class="state-hr-facility-name"', text)),
        "hidden_dom_detail_markers": hidden_dom_details,
        "inline_scripts_bytes": sum(
            len(m.group(0)) for m in re.finditer(r'<script(?![^>]*\ssrc=)[^>]*>.*?</script>', text, re.S)
        ),
        "report_fp_json_bytes": _first_group(r"window\.__REPORT_FP_BY_STATE__\s*=\s*(\{.*?\});", text),
    }


def discover_owner_profiles() -> list[str]:
    req = urllib.request.Request(
        BASE + "/owners/ny",
        headers={"User-Agent": "PBJ320-public-payload-audit/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    return re.findall(r'href="(/owners/\d{10})"', text)[:2]


def main() -> int:
    paths = list(PATHS) + discover_owner_profiles()
    rows = [analyze(p) for p in paths]
    rows.sort(key=lambda x: x.get("bytes", 0), reverse=True)
    out = {
        "base": BASE,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pages": rows,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
