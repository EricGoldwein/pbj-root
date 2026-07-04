#!/usr/bin/env python3
import re
import urllib.request

UA = {"User-Agent": "pbj320-deploy-verify/1.0"}
URLS = {
    "report": "https://www.pbj320.com/insights/ny-minimum-staffing",
    "preview": "https://www.pbj320.com/preview/ny-staffing-compliance-2025/p4v8nq",
    "press": "https://www.pbj320.com/insights/ny-minimum-staffing/press",
    "hub": "https://www.pbj320.com/insights",
}
STALE = [
    "17,082", "17,208", "81.7%", "82.3%", "60,389", "33,809",
    "43,181", "14,061", "442 facility", "442 days",
    'provider_name": "nan"', 'data-fd="60389"',
]

for name, url in URLS.items():
    t = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", errors="replace")
    hits = [s for s in STALE if s in t]
    # UI-only: also flag bare 17208 only if near weekend table / wt-count
    if "17208" in t and "17,208" not in t:
        if re.search(r"wt-count|weekend_nyc|14,061", t):
            hits.append("17208 (bare)")
    print(f"{name}: {hits or 'none'}")
