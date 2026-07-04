import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = [
    ROOT / "insights-ny-minimum-staffing.html",
    ROOT / "insights-ny-minimum-staffing-press.html",
    ROOT / "insights_posts" / "ny-minimum-staffing.md",
]

for path in PUBLIC:
    text = path.read_text(encoding="utf-8")
    bad = []
    if re.search(r"82\.3\s*%", text) or '"wknd_pct":82.3' in text:
        bad.append("82.3%")
    if "17,082" in text or re.search(r'"facility_days":17082\b', text):
        bad.append("17082")
    print(f"{path.name}: {'OK' if not bad else 'BAD ' + ', '.join(bad)}")

html = (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8")
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
            I = json.loads(html[start : j + 1])
            break

total = I["modes"]["total"]
card = next(c for c in total["weekend_cards"] if c["curve"] == "weekend_nyc")
pt = next(p for p in total["curves"]["weekend_nyc"] if abs(p["threshold"] - 3.5) < 0.001)
print("default mode weekend_nyc:", card, pt, "display", round(100 * pt["below"] / card["facility_days"], 1))

excl = I["modes"].get("excl_admin", {})
excl_card = next((c for c in excl.get("weekend_cards", []) if c["curve"] == "weekend_nyc"), None)
print("excl_admin weekend_nyc card:", excl_card)

method = html[html.index('id="methodology"'): html.index("</section>", html.index('id="methodology"'))]
for tok in ("17082", "17,082", "17208", "17,208", "82.3", "hardcoded", "saturday_card"):
    print(f"methodology mentions {tok}:", tok in method)

footer = html[html.index('report-endmatter'): html.index("window.PBJ_REPORT_NY_STATUTE")]
for tok in ("17082", "17,082", "17208", "17,208", "82.3"):
    print(f"footer mentions {tok}:", tok in footer)
