#!/usr/bin/env python3
"""Post-deploy smoke checks (report perf, phoebe webp, GPT rate limit, provider cache warm)."""
import re
import subprocess
import sys
from pathlib import Path

import urllib.error
import urllib.request

_ROOT = Path(__file__).resolve().parents[1]

UA = "PBJ320DeployCheck/1.0"


def get(url, headers=None, timeout=90):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b""
        return e.code, e.headers.get("Content-Type", ""), body


def main():
    results = []

    warm_script = _ROOT / "scripts" / "warm_provider_cache.py"
    if warm_script.is_file():
        print("=== PROVIDER CACHE WARM (optional, costs CPU) ===")
        warm_rc = subprocess.call(
            [
                sys.executable,
                str(warm_script),
                "--base-url",
                "https://www.pbj320.com",
                "--limit",
                "20",
                "--passes",
                "3",
            ],
        )
        results.append(
            (
                "A0 provider cache warm (modest)",
                warm_rc == 0,
                f"exit={warm_rc} limit=20 passes=3",
            )
        )
        print()

    st, ct, body = get("https://www.pbj320.com/health", timeout=20)
    results.append(("A1 health", st == 200 and body.strip() == b"ok", f"{st} body={body[:20]!r}"))

    st, ct, body = get("https://www.pbj320.com/contact-popup-shared.css?v=1", timeout=20)
    ok = st == 200 and "text/css" in ct and not body.lstrip()[:1] == b"<"
    results.append(("A2 contact-popup-shared.css", ok, f"{st} ct={ct} len={len(body)}"))

    st, ct, body = get("https://www.pbj320.com/phoebe-avatar-72.webp", timeout=20)
    results.append(("A3 phoebe-avatar-72.webp", st == 200 and len(body) < 50_000, f"{st} len={len(body)}"))

    st, ct, body = get("https://www.pbj320.com/report", timeout=60)
    html = body.decode("utf-8", errors="replace")
    markers = {
        "fetchStateQuarterlyMetricsCsvText": "fetchStateQuarterlyMetricsCsvText" in html,
        "defer d3": 'defer src="https://d3js.org/d3.v7.min.js"' in html,
        "loadData uses shared fetch": "fetchStateQuarterlyMetricsCsvText()," in html,
    }
    ok4 = all(markers.values())
    results.append(("A4 report deploy markers", ok4, str(markers)))

    st, ct, body = get("https://www.pbj320.com/provider/335513", timeout=120)
    html5 = body.decode("utf-8", errors="replace")
    has_webp = "phoebe-avatar-72.webp" in html5
    takeaway_png = bool(re.search(r"pbj-takeaway[\s\S]{0,800}phoebe\.png", html5))
    results.append(
        (
            "A5 provider 335513 webp",
            st == 200 and has_webp and not takeaway_png,
            f"{st} len={len(body)} webp={has_webp} takeaway_png={takeaway_png}",
        )
    )

    st, ct, body = get("https://www.pbj320.com/provider/075263", timeout=120)
    html6 = body.decode("utf-8", errors="replace")
    own = "pbj-details-ownership" in html6
    results.append(("A6 provider 075263 CT ownership", st == 200 and own, f"{st} ownership={own} len={len(body)}"))

    st, ct, body = get("https://www.pbj320.com/state/ct", timeout=90)
    html7 = body.decode("utf-8", errors="replace")
    results.append(
        (
            "A7 state/ct",
            st == 200 and len(body) > 10_000,
            f"{st} len={len(body)} webp={'phoebe-avatar-72.webp' in html7}",
        )
    )

    hits = []
    for _ in range(14):
        st, _, _ = get(
            "https://www.pbj320.com/provider/335513",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GPTBot/1.3; +https://openai.com/gptbot)"
            },
            timeout=120,
        )
        hits.append(st)
    count_429 = hits.count(429)
    count_200 = hits.count(200)
    ok8 = count_429 >= 1 and count_200 >= 1
    results.append(("A8 GPTBot rate limit", ok8, f"statuses={hits} 200={count_200} 429={count_429}"))

    print("=== DEPLOY CHECKS (53c6698) ===")
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status} | {name} | {detail}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"--- {passed}/{len(results)} passed ---")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
