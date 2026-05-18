"""Write static SVG charts for insights post (national + rural/urban + state map + scatter)."""
from __future__ import annotations

import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_DEFAULT = ROOT.parent / "PBJapp" / "cms-cost-report" / "output" / "cms_cost_report_state_summary_2023.csv"


def main() -> None:
    years = list(range(2011, 2024))
    p50 = [0.8661, 0.8671, 0.8608, 0.8636, 0.8550, 0.8464, 0.8407, 0.8384, 0.8366, 0.7493, 0.7168, 0.7565, 0.7974]
    p25 = [0.7552, 0.7580, 0.7475, 0.7482, 0.7421, 0.7304, 0.7193, 0.7135, 0.7135, 0.6382, 0.5987, 0.6262, 0.6607]
    p75 = [0.9243, 0.9249, 0.9214, 0.9229, 0.9178, 0.9147, 0.9108, 0.9109, 0.9109, 0.8333, 0.8197, 0.8615, 0.8904]

    w, h = 820, 420
    left, right, top, bot = 72, 760, 48, 360
    ymin, ymax = 0.58, 0.95

    def x_of(i: int) -> float:
        return left + i * (right - left) / (len(years) - 1)

    def y_of(v: float) -> float:
        return bot - (v - ymin) / (ymax - ymin) * (bot - top)

    pts_top = [f"{x_of(i):.1f},{y_of(p75[i]):.1f}" for i in range(len(years))]
    pts_bot = [f"{x_of(i):.1f},{y_of(p25[i]):.1f}" for i in range(len(years) - 1, -1, -1)]
    d_ribbon = "M " + " L ".join(pts_top) + " L " + " L ".join(pts_bot) + " Z"
    pts_med = [f"{x_of(i):.1f},{y_of(p50[i]):.1f}" for i in range(len(years))]
    d_med = "M " + " L ".join(pts_med)

    ticks = "".join(
        f'<text x="{x_of(i):.1f}" y="{bot + 22}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="11" font-family="system-ui,sans-serif">{years[i]}</text>'
        for i in range(0, len(years), 2)
    )

    svg1 = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t1">
  <title id="t1">National median occupancy proxy with middle 50 percent band, 2011 to 2023</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="{w / 2}" y="30" text-anchor="middle" fill="#e2e8f0" font-size="16" font-weight="700"
    font-family="system-ui,sans-serif">Occupancy proxy: median and middle 50%</text>
  <text x="{w / 2}" y="50" text-anchor="middle" fill="#94a3b8" font-size="12"
    font-family="system-ui,sans-serif">Dashboard-ready rows, CMS SNF cost reports</text>
  <line x1="{left}" y1="{bot}" x2="{right}" y2="{bot}" stroke="#334155" stroke-width="1"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{bot}" stroke="#334155" stroke-width="1"/>
  <path d="{d_ribbon}" fill="rgba(96,165,250,0.22)" stroke="none"/>
  <path d="{d_med}" fill="none" stroke="#60a5fa" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {ticks}
  <text x="{right}" y="{top + 18}" text-anchor="end" fill="#94a3b8" font-size="11"
    font-family="system-ui,sans-serif">Sharp drop 2020–21; partial rebound by 2023</text>
</svg>"""
    (ROOT / "insights-cost-report-national-occupancy.svg").write_text(svg1, encoding="utf-8")

    w2, h2 = 720, 380
    l2, r2, t2, b2 = 64, 660, 52, 320
    yr_sel = [2019, 2020, 2021, 2022, 2023]
    rur = [0.791, 0.723, 0.672, 0.697, 0.734]
    urb = [0.851, 0.757, 0.733, 0.775, 0.816]

    def x2(i: int) -> float:
        return l2 + i * (r2 - l2) / (len(yr_sel) - 1)

    def y2(v: float) -> float:
        return b2 - (v - 0.58) / (0.95 - 0.58) * (b2 - t2)

    dr = "M " + " L ".join([f"{x2(i):.1f},{y2(rur[i]):.1f}" for i in range(len(yr_sel))])
    du = "M " + " L ".join([f"{x2(i):.1f},{y2(urb[i]):.1f}" for i in range(len(yr_sel))])
    ticks2 = "".join(
        f'<text x="{x2(i):.1f}" y="{b2 + 22}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="12" font-family="system-ui,sans-serif">{yr_sel[i]}</text>'
        for i in range(len(yr_sel))
    )

    svg2 = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w2} {h2}" role="img" aria-labelledby="t2">
  <title id="t2">Rural vs urban median occupancy proxy, 2019 to 2023</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="{w2 / 2}" y="30" text-anchor="middle" fill="#e2e8f0" font-size="16" font-weight="700"
    font-family="system-ui,sans-serif">Rural vs urban median occupancy</text>
  <line x1="{l2}" y1="{b2}" x2="{r2}" y2="{b2}" stroke="#334155"/>
  <line x1="{l2}" y1="{t2}" x2="{l2}" y2="{b2}" stroke="#334155"/>
  <path d="{dr}" fill="none" stroke="#34d399" stroke-width="2.5"/>
  <path d="{du}" fill="none" stroke="#a78bfa" stroke-width="2.5"/>
  {ticks2}
  <text x="{r2}" y="{t2 + 20}" text-anchor="end" fill="#34d399" font-size="11"
    font-family="system-ui,sans-serif">Rural</text>
  <text x="{r2}" y="{t2 + 36}" text-anchor="end" fill="#a78bfa" font-size="11"
    font-family="system-ui,sans-serif">Urban</text>
</svg>"""
    (ROOT / "insights-cost-report-rural-urban-occupancy.svg").write_text(svg2, encoding="utf-8")

    # Scatter: all states 2023 from pipeline file in PBJapp (path relative to dev machine)
    csv_path = Path(os.environ.get("COST_REPORT_STATE_SUMMARY_CSV", str(CSV_DEFAULT)))
    rows: list[tuple[str, float, float, int]] = []
    if csv_path.is_file():
        with csv_path.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                st = (row.get("state_code") or "").strip()
                try:
                    wm = float(row["weighted_medicaid_day_share"])
                    mo = float(row["median_occupancy_proxy"])
                    nf = int(float(row["n_facilities"]))
                except (KeyError, ValueError):
                    continue
                rows.append((st, wm, mo, nf))

    w3, h3 = 780, 520
    margin_l, margin_r, margin_t, margin_b = 72, 40, 56, 72
    plot_w = w3 - margin_l - margin_r
    plot_h = h3 - margin_t - margin_b
    xmin, xmax = 0.05, 0.92
    ymin3, ymax3 = 0.55, 1.0

    def sx(wx: float) -> float:
        return margin_l + (wx - xmin) / (xmax - xmin) * plot_w

    def sy(wy: float) -> float:
        return margin_t + (ymax3 - wy) / (ymax3 - ymin3) * plot_h

    circles = []
    for st, wm, mo, nf in rows:
        rpx = max(3.0, min(22.0, 2.2 * (nf**0.5)))
        circles.append(
            f'<circle cx="{sx(wm):.1f}" cy="{sy(mo):.1f}" r="{rpx:.1f}" fill="rgba(96,165,250,0.35)" '
            f'stroke="#60a5fa" stroke-width="1"/>'
        )
    labels = [("WV", 0.8100949400688469, 0.9356164383561644), ("TX", 0.6015369325345976, 0.626902059688945)]
    for st, wm, mo, nf in rows:
        if st == "OH":
            labels.append(("OH", wm, mo))
        if st == "CA":
            labels.append(("CA", wm, mo))
    label_el = "".join(
        f'<text x="{sx(wm) + 8:.1f}" y="{sy(mo) - 6:.1f}" fill="#e2e8f0" font-size="12" '
        f'font-weight="600" font-family="system-ui,sans-serif">{abbr}</text>'
        for abbr, wm, mo in labels
    )

    svg3 = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w3} {h3}" role="img" aria-labelledby="t3">
  <title id="t3">States: weighted Medicaid day share vs median occupancy proxy, 2023</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="{w3 / 2}" y="34" text-anchor="middle" fill="#e2e8f0" font-size="16" font-weight="700"
    font-family="system-ui,sans-serif">2023 states: Medicaid day share vs median occupancy</text>
  <text x="{w3 / 2}" y="54" text-anchor="middle" fill="#94a3b8" font-size="11"
    font-family="system-ui,sans-serif">Each dot is one state; dot size scales with facility count</text>
  <line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{margin_l + plot_w}" y2="{margin_t + plot_h}" stroke="#334155"/>
  <line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + plot_h}" stroke="#334155"/>
  <text x="{margin_l + plot_w / 2}" y="{h3 - 22}" text-anchor="middle" fill="#94a3b8" font-size="12"
    font-family="system-ui,sans-serif">Weighted Medicaid share of resident days (0–1)</text>
  <text x="18" y="{margin_t + plot_h / 2}" text-anchor="middle" fill="#94a3b8" font-size="12"
    font-family="system-ui,sans-serif" transform="rotate(-90 18 {margin_t + plot_h / 2})">Median occupancy proxy</text>
  {''.join(circles)}
  {label_el}
</svg>"""
    (ROOT / "insights-cost-report-state-scatter-2023.svg").write_text(svg3, encoding="utf-8")

    # Tile map: weighted Medicaid share by state (static choropleth-style map)
    tile_positions: dict[str, tuple[int, int]] = {
        "WA": (0, 0), "MT": (1, 0), "ND": (2, 0), "MN": (3, 0), "WI": (4, 0), "MI": (5, 0), "VT": (8, 0), "NH": (9, 0), "ME": (10, 0),
        "OR": (0, 1), "ID": (1, 1), "SD": (2, 1), "IA": (3, 1), "IL": (4, 1), "IN": (5, 1), "OH": (6, 1), "PA": (7, 1), "NY": (8, 1), "MA": (9, 1),
        "CA": (0, 2), "NV": (1, 2), "WY": (2, 2), "NE": (3, 2), "MO": (4, 2), "KY": (5, 2), "WV": (6, 2), "VA": (7, 2), "MD": (8, 2), "NJ": (9, 2), "CT": (10, 2), "RI": (11, 2),
        "UT": (1, 3), "CO": (2, 3), "KS": (3, 3), "AR": (4, 3), "TN": (5, 3), "NC": (6, 3), "SC": (7, 3), "DE": (8, 3), "DC": (9, 3),
        "AZ": (1, 4), "NM": (2, 4), "OK": (3, 4), "LA": (4, 4), "MS": (5, 4), "AL": (6, 4), "GA": (7, 4),
        "TX": (3, 5), "FL": (8, 5),
        "AK": (0, 6), "HI": (1, 6), "PR": (11, 6),
    }
    medicaid_by_state = {st: wm for st, wm, _, _ in rows if st}

    map_w, map_h = 860, 580
    cell = 56
    gap = 8
    pad_x, pad_y = 68, 84
    min_share, max_share = 0.35, 0.85

    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def tile_rgb(share: float | None) -> tuple[int, int, int]:
        if share is None:
            return (71, 85, 105)  # slate-600 for no-data tiles
        t = (_clamp(share, min_share, max_share) - min_share) / (max_share - min_share)
        # Interpolate from light blue to deep blue.
        r = round(191 + (30 - 191) * t)
        g = round(219 + (64 - 219) * t)
        b = round(254 + (175 - 254) * t)
        return (r, g, b)

    def tile_fill(share: float | None) -> str:
        r, g, b = tile_rgb(share)
        return f"rgb({r},{g},{b})"

    def text_fill_for_tile(share: float | None) -> str:
        r, g, b = tile_rgb(share)
        # Relative luminance proxy for contrast.
        luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
        return "#0f172a" if luminance > 150 else "#f8fafc"

    tiles: list[str] = []
    labels: list[str] = []
    for st, (cx, cy) in tile_positions.items():
        x = pad_x + cx * (cell + gap)
        y = pad_y + cy * (cell + gap)
        share = medicaid_by_state.get(st)
        tiles.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="10" ry="10" '
            f'fill="{tile_fill(share)}" stroke="rgba(148,163,184,0.45)" stroke-width="1.2"/>'
        )
        labels.append(
            f'<text x="{x + cell / 2}" y="{y + 24}" text-anchor="middle" fill="{text_fill_for_tile(share)}" '
            f'font-size="12" font-weight="700" font-family="system-ui,sans-serif">{st}</text>'
        )
        if share is not None:
            labels.append(
                f'<text x="{x + cell / 2}" y="{y + 42}" text-anchor="middle" fill="{text_fill_for_tile(share)}" '
                f'font-size="10" font-family="system-ui,sans-serif">{share:.2f}</text>'
            )
        else:
            labels.append(
                f'<text x="{x + cell / 2}" y="{y + 42}" text-anchor="middle" fill="#cbd5e1" '
                f'font-size="10" font-family="system-ui,sans-serif">N/A</text>'
            )

    legend_x = 560
    legend_y = 540
    gradient_stops = []
    for i in range(0, 11):
        s = min_share + (max_share - min_share) * (i / 10)
        gradient_stops.append(
            f'<stop offset="{i * 10}%" stop-color="{tile_fill(s)}"/>'
        )

    svg4 = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {map_w} {map_h}" role="img" aria-labelledby="t4">
  <title id="t4">State tile map: weighted Medicaid day share, 2023</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="{map_w / 2}" y="36" text-anchor="middle" fill="#e2e8f0" font-size="18" font-weight="700"
    font-family="system-ui,sans-serif">2023 state map: weighted Medicaid day share</text>
  <text x="{map_w / 2}" y="58" text-anchor="middle" fill="#94a3b8" font-size="12"
    font-family="system-ui,sans-serif">Tile choropleth by state (resident-day shares). Darker blue = higher Medicaid share; N/A means no data in this slice.</text>
  {''.join(tiles)}
  {''.join(labels)}
  <defs>
    <linearGradient id="legendBlue" x1="0%" y1="0%" x2="100%" y2="0%">
      {''.join(gradient_stops)}
    </linearGradient>
  </defs>
  <rect x="{legend_x}" y="{legend_y}" width="180" height="14" fill="url(#legendBlue)" rx="7" ry="7"/>
  <text x="{legend_x}" y="{legend_y - 8}" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">Weighted Medicaid share</text>
  <text x="{legend_x}" y="{legend_y + 30}" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">{min_share:.2f}</text>
  <text x="{legend_x + 180}" y="{legend_y + 30}" text-anchor="end" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">{max_share:.2f}</text>
</svg>"""
    (ROOT / "insights-cost-report-state-medicaid-tilemap-2023.svg").write_text(svg4, encoding="utf-8")

    # Simple preview thumbnail (wide)
    prev = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" role="img" aria-label="Cost reports and staffing context">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e3a8a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#g)"/>
  <text x="600" y="260" text-anchor="middle" fill="#e2e8f0" font-size="42" font-weight="700" font-family="system-ui,sans-serif">PBJ + cost reports</text>
  <text x="600" y="330" text-anchor="middle" fill="#94a3b8" font-size="24" font-family="system-ui,sans-serif">Staffing hours meet operating context</text>
  <path d="M 120 480 L 240 360 L 360 400 L 480 300 L 600 340 L 720 260 L 840 300 L 960 280 L 1080 320" fill="none" stroke="#60a5fa" stroke-width="4"/>
</svg>"""
    (ROOT / "insights-cost-report-preview.svg").write_text(prev, encoding="utf-8")

    print("Wrote:", ROOT / "insights-cost-report-national-occupancy.svg")


if __name__ == "__main__":
    main()
