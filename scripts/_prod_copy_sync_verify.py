#!/usr/bin/env python3
"""Post-deploy verify: copy-sync prose + data values on production."""
from __future__ import annotations

import json
import re
import sys
import urllib.request

BASE = "https://www.pbj320.com"
REPORT = f"{BASE}/insights/ny-minimum-staffing"
UA = {"User-Agent": "pbj320-copy-sync-verify/1.0"}


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def prose_only(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    for marker in (
        "window.PBJ_REPORT_INTERACTIVE = ",
        "window.PBJ_REPORT_FACILITIES = ",
        "window.PBJ_REPORT_CHARTS = ",
        "window.PBJ_REPORT_UI = ",
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
    raise ValueError("interactive JSON missing")


def lookup(curve: list, t: float = 3.5) -> dict:
    return next(p for p in curve if abs(p["threshold"] - t) < 0.001)


def main() -> int:
    st, html = fetch(REPORT)
    print(f"report HTTP {st} bytes={len(html)}")
    if st != 200:
        return 1

    prose = prose_only(html)
    ownership_para = re.search(
        r"Below-minimum rates differed by ownership type\.[^<]{0,500}",
        html,
    )
    print("OWNERSHIP_PROSE:", ownership_para.group(0)[:400] if ownership_para else "MISSING")

    stale = [t for t in ("20.5%", "60.1%", "48.1%", "5.4%", "33.22%", "442 facility-days", "NYC accounts for 168") if t in prose]
    print("STALE_PROSE:", stale or "none")

    good = [t for t in ("20.7%", "60.3%", "49.7%", "5.2%", "CNA-side includes CNA") if t in html]
    print("COPY_MARKERS:", good)

    mode = extract_interactive(html)["modes"]["total"]
    curves = mode["curves"]
    cfd = mode.get("curve_facility_days") or {}

    def snap(key: str, wk: str | None = None) -> dict:
        pt = lookup(curves[key])
        fd = int(cfd.get(key) or mode["facility_days_total"])
        out = {"fd": fd, "below": int(pt["below"]), "pct": round(float(pt["pct_below"]), 1)}
        if wk:
            wpt = lookup(curves[wk])
            wfd = int(cfd.get(wk) or 0)
            out["wkend"] = {"fd": wfd, "below": int(wpt["below"]), "pct": round(float(wpt["pct_below"]), 1)}
        return out

    data = {
        "all_ny": snap("all_ny"),
        "nyc": snap("nyc", "weekend_nyc"),
        "for_profit": snap("ny_for_profit"),
        "non_profit": snap("ny_non_profit"),
        "government": snap("ny_government"),
    }
    print("DATA", json.dumps(data))

    for label, url in (
        ("xlsx", f"{BASE}/downloads/PBJ320_NY_2025_daily_staffing_verification_file.xlsx"),
        ("zip", f"{BASE}/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs.zip"),
    ):
        s, _ = fetch(url)
        print(f"download {label}: HTTP {s}")

    classic_req = urllib.request.Request(
        f"{BASE}/insights/ny-minimum-staffing/classic",
        method="HEAD",
        headers=UA,
    )
    with urllib.request.urlopen(classic_req, timeout=60) as resp:
        print(f"classic: HTTP {resp.status} loc={resp.headers.get('Location')}")

    ok = (
        ownership_para
        and not stale
        and data["all_ny"]["fd"] == 216134
        and data["nyc"]["fd"] == 59582
        and data["nyc"]["wkend"]["fd"] == 16978
        and "20.7%" in good
    )
    print("GATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
