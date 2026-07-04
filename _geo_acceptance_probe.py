import json, re, urllib.request
from html.parser import HTMLParser

class VisibleTextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data)

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "pbj-geo-acceptance/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body, None
    except Exception as e:
        if hasattr(e, "code"):
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            return e.code, body, str(e)
        return None, "", str(e)

def visible_text(html):
    p = VisibleTextCollector()
    p.feed(html)
    return " ".join(p.parts)

def selected_quarter(html):
    m = re.search(r'<option[^>]*selected[^>]*value="([^"]+)"', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'<option[^>]*value="([^"]+)"[^>]*selected', html, re.I)
    if m:
        return m.group(1)
    return None

def count_region_rows(html):
    tbody = re.findall(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
    row_counts = [len(re.findall(r"<tr\b", block, re.I)) for block in tbody]
    best = max(row_counts) if row_counts else 0
    data_rows = len(re.findall(r"<tr[^>]*class=[^>]*(?:region|county|geo-row)", html, re.I))
    link_rows = len(re.findall(r"/geo/connecticut/[^\"']+", html, re.I))
    return {
        "tbody_blocks": len(tbody),
        "max_tbody_tr": best,
        "classed_geo_rows": data_rows,
        "geo_subpath_links": link_rows,
    }

def choropleth_present(html):
    checks = {
        "canvas": bool(re.search(r"<canvas\b", html, re.I)),
        "svg": bool(re.search(r"<svg\b", html, re.I)),
        "mapbox": "mapbox" in html.lower(),
        "leaflet": "leaflet" in html.lower(),
        "choropleth": "choropleth" in html.lower(),
        "plotly": "plotly" in html.lower() or "js-plotly" in html.lower(),
    }
    checks["any_map_like"] = checks["canvas"] or checks["svg"] or checks["mapbox"] or checks["leaflet"] or checks["choropleth"]
    return checks

def analyze_page(name, url):
    status, html, err = fetch(url)
    vis = visible_text(html) if html else ""
    vis_lower = vis.lower()
    title_m = re.search(r"<title[^>]*>([^<]+)</title>", html or "", re.I)
    h1_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "", re.I)
    snippet = " | ".join(
        x
        for x in [
            title_m.group(1).strip() if title_m else None,
            h1_m.group(1).strip() if h1_m else None,
        ]
        if x
    )
    return {
        "name": name,
        "url": url,
        "status": status,
        "error": err,
        "html_length": len(html or ""),
        "snippet": snippet[:500],
        "default_selected_quarter": selected_quarter(html or ""),
        "county_in_visible_text": bool(re.search(r"\bcounty\b", vis_lower)),
        "planning_region_in_visible_text": bool(re.search(r"planning region", vis_lower)),
        "region_in_visible_text": bool(re.search(r"\bregion\b", vis_lower)),
        "region_row_counts": count_region_rows(html or ""),
        "choropleth": choropleth_present(html or ""),
        "geo_links_in_page": re.findall(r'href="([^"]*geo/connecticut[^"]*)"', html or "", re.I)[:8],
        "visible_text_sample": vis[:500] if vis else "",
    }

local_urls = [
    ("geo_default", "http://127.0.0.1:5055/geo/connecticut"),
    ("geo_2025Q3", "http://127.0.0.1:5055/geo/connecticut?quarter=2025Q3"),
    ("geo_2025Q4", "http://127.0.0.1:5055/geo/connecticut?quarter=2025Q4"),
    ("state_connecticut", "http://127.0.0.1:5055/state/connecticut"),
]
results = {
    "server": {"port": 5055, "base": "http://127.0.0.1:5055"},
    "local_pages": [analyze_page(n, u) for n, u in local_urls],
}
prod_status, prod_html, prod_err = fetch("https://www.pbj320.com/geo/connecticut", timeout=20)
title_m = re.search(r"<title[^>]*>([^<]+)</title>", prod_html or "", re.I)
results["production"] = {
    "url": "https://www.pbj320.com/geo/connecticut",
    "status": prod_status,
    "error": prod_err,
    "live": prod_status == 200,
    "is_404": prod_status == 404,
    "html_length": len(prod_html or ""),
    "snippet": title_m.group(1).strip() if title_m else "",
}
state_html_status, state_html, _ = fetch("http://127.0.0.1:5055/state/connecticut")
results["state_geographic_crosslink"] = {
    "status": state_html_status,
    "has_geo_connecticut_link": "/geo/connecticut" in (state_html or ""),
    "geo_links_sample": re.findall(r'href="([^"]*geo/connecticut[^"]*)"', state_html or "", re.I)[:8],
}
print(json.dumps(results, indent=2))
