#!/usr/bin/env python3
"""Poll production until copy-sync commit 02d1551 is live."""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request

REPORT = "https://www.pbj320.com/insights/ny-minimum-staffing"
UA = {"User-Agent": "pbj320-copy-sync-verify/1.0"}


def fetch(url: str, method: str = "GET") -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers=UA, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace"), dict(resp.headers)


def prose_only(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    for marker in (
        "window.PBJ_REPORT_INTERACTIVE = ",
        "window.PBJ_REPORT_FACILITIES = ",
        "window.PBJ_REPORT_CHARTS = ",
    ):
        html = re.sub(re.escape(marker) + r"[\s\S]*?;\s*", " ", html)
    return re.sub(r"<[^>]+>", " ", html)


def extract_interactive(html: str) -> dict:
    marker = "window.PBJ_REPORT_INTERACTIVE = "
    start = html.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start : j + 1])
    raise ValueError("no interactive")


def lookup(curve: list, t: float = 3.5) -> dict:
    return next(p for p in curve if abs(p["threshold"] - t) < 0.001)


def main() -> int:
    for i in range(1, 31):
        try:
            st, html, _ = fetch(REPORT)
        except urllib.error.HTTPError as exc:
            print(f"poll {i}: HTTP {exc.code}")
            time.sleep(45)
            continue
        except Exception as exc:
            print(f"poll {i}: error {exc}")
            time.sleep(45)
            continue

        prose = prose_only(html)
        copy_ok = ("differed by ownership type" in html) and ("differed sharply" not in html)
        stale = [
            t
            for t in (
                "20.5%",
                "60.1%",
                "48.1%",
                "5.4%",
                "33.22%",
                "442 facility-days",
                "NYC accounts for 168",
            )
            if t in prose
        ]
        cna_ok = "CNA-side includes CNA" in html
        p1 = re.search(r"Below-minimum rates differed[^<]{0,400}", html)
        p2 = re.search(r"The same pattern appears within New York City[^<]{0,300}", html)
        print(
            f"poll {i}: copy_ok={copy_ok} stale={stale or 'none'} cna={cna_ok} bytes={len(html)}"
        )
        if copy_ok and not stale and cna_ok:
            mode = extract_interactive(html)["modes"]["total"]
            curves = mode["curves"]
            cfd = mode.get("curve_facility_days") or {}

            def snap(key: str, wk: str | None = None) -> dict:
                pt = lookup(curves[key])
                fd = int(cfd.get(key) or mode["facility_days_total"])
                out = {
                    "fd": fd,
                    "below": int(pt["below"]),
                    "pct": round(float(pt["pct_below"]), 1),
                }
                if wk:
                    wpt = lookup(curves[wk])
                    wfd = int(cfd.get(wk) or 0)
                    out["wkend"] = {
                        "fd": wfd,
                        "below": int(wpt["below"]),
                        "pct": round(float(wpt["pct_below"]), 1),
                    }
                return out

            data = {"all_ny": snap("all_ny"), "nyc": snap("nyc", "weekend_nyc")}
            xs, _, _ = fetch(
                "https://www.pbj320.com/downloads/PBJ320_NY_2025_daily_staffing_verification_file.xlsx"
            )
            zs, _, _ = fetch(
                "https://www.pbj320.com/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs.zip"
            )
            cs, _, hdrs = fetch(
                "https://www.pbj320.com/insights/ny-minimum-staffing/classic",
                method="HEAD",
            )
            print("PROSE1:", p1.group(0) if p1 else "NONE")
            print("PROSE2:", p2.group(0) if p2 else "NONE")
            print("DATA:", json.dumps(data))
            print(f"downloads xlsx={xs} zip={zs}")
            print(f"classic={cs} loc={hdrs.get('Location')}")
            print("GATE PASS")
            return 0
        time.sleep(45)
    print("GATE TIMEOUT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
