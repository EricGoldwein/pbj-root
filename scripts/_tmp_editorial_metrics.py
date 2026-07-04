"""One-off metrics for editorial 3.50 daily / quarterly patch."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"


def load_interactive(html: str) -> dict:
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
    raise RuntimeError("interactive not found")


def curve_at(curve, t=3.5):
    return next(p for p in curve if abs(p["threshold"] - t) < 0.001)


if __name__ == "__main__":
    html = HTML.read_text(encoding="utf-8")
    inter = load_interactive(html)
    mode = inter["modes"]["ny_mapped_non_admin_hprd"]
    all_pt = curve_at(mode["curves"]["all_ny"])
    wk_pt = curve_at(mode["curves"]["weekend"])
    print("all", all_pt)
    print("weekend", wk_pt)
    dows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, d in enumerate(dows):
        pt = curve_at(mode["curves_by_dow"][i])
        print(d, pt["pct_below"], pt["below"], pt.get("facility_days"))
