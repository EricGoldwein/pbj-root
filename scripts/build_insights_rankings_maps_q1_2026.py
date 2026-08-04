"""Build static state + CMS-region map SVGs for the Q1 2026 rankings insights draft.

Infrastructure only: does not change interactive /report maps.
Verified from: state_quarterly_metrics.csv + cms_region_quarterly_metrics.csv (CY_Qtr=2026Q1).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

TILE_POSITIONS: dict[str, tuple[int, int]] = {
    "WA": (0, 0), "MT": (1, 0), "ND": (2, 0), "MN": (3, 0), "WI": (4, 0), "MI": (5, 0),
    "VT": (8, 0), "NH": (9, 0), "ME": (10, 0),
    "OR": (0, 1), "ID": (1, 1), "SD": (2, 1), "IA": (3, 1), "IL": (4, 1), "IN": (5, 1),
    "OH": (6, 1), "PA": (7, 1), "NY": (8, 1), "MA": (9, 1),
    "CA": (0, 2), "NV": (1, 2), "WY": (2, 2), "NE": (3, 2), "MO": (4, 2), "KY": (5, 2),
    "WV": (6, 2), "VA": (7, 2), "MD": (8, 2), "NJ": (9, 2), "CT": (10, 2), "RI": (11, 2),
    "UT": (1, 3), "CO": (2, 3), "KS": (3, 3), "AR": (4, 3), "TN": (5, 3), "NC": (6, 3),
    "SC": (7, 3), "DE": (8, 3), "DC": (9, 3),
    "AZ": (1, 4), "NM": (2, 4), "OK": (3, 4), "LA": (4, 4), "MS": (5, 4), "AL": (6, 4),
    "GA": (7, 4),
    "TX": (3, 5), "FL": (8, 5),
    "AK": (0, 6), "HI": (1, 6), "PR": (11, 6),
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _viridis_rgb(t: float) -> tuple[int, int, int]:
    """Cheap 5-stop viridis-ish scale (low -> high). t in [0,1]."""
    stops = [
        (0.0, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.5, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.0, (253, 231, 37)),
    ]
    t = _clamp(t, 0.0, 1.0)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return (
                round(c0[0] + (c1[0] - c0[0]) * u),
                round(c0[1] + (c1[1] - c0[1]) * u),
                round(c0[2] + (c1[2] - c0[2]) * u),
            )
    return stops[-1][1]


def _fill(t: float | None) -> str:
    if t is None:
        return "rgb(71, 85, 105)"
    r, g, b = _viridis_rgb(t)
    return f"rgb({r},{g},{b})"


def _text_fill(t: float | None) -> str:
    if t is None:
        return "#cbd5e1"
    r, g, b = _viridis_rgb(t)
    luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    return "#0f172a" if luminance > 150 else "#f8fafc"


def build_state_tilemap(
    values_by_abbr: dict[str, float],
    out: Path,
    *,
    title: str,
    legend: str,
    value_fmt: str = ".2f",
    exclude_from_scale: tuple[str, ...] = ("AK", "PR"),
) -> None:
    values = [v for v in values_by_abbr.values() if v is not None]
    # Color scale from contiguous states so AK/HI/PR outliers do not wash out the map;
    # those territories are still drawn and labeled with their values.
    scale_vals = [
        values_by_abbr[a]
        for a in values_by_abbr
        if a not in exclude_from_scale and values_by_abbr[a] is not None
    ]
    vmin = min(scale_vals) if scale_vals else min(values)
    vmax = max(scale_vals) if scale_vals else max(values)

    def norm(v: float | None) -> float | None:
        if v is None:
            return None
        if vmax <= vmin:
            return 0.5
        return _clamp((v - vmin) / (vmax - vmin), 0.0, 1.0)

    def fmt_val(v: float) -> str:
        if value_fmt.endswith("d") or value_fmt == ".0f":
            return f"{v:.0f}"
        return format(v, value_fmt)

    map_w, map_h = 860, 560
    cell, gap = 56, 8
    pad_x, pad_y = 68, 36
    tiles: list[str] = []
    labels: list[str] = []
    for st, (cx, cy) in TILE_POSITIONS.items():
        x = pad_x + cx * (cell + gap)
        y = pad_y + cy * (cell + gap)
        v = values_by_abbr.get(st)
        t = norm(v)
        tiles.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="10" ry="10" '
            f'fill="{_fill(t)}" stroke="rgba(148,163,184,0.45)" stroke-width="1.2"/>'
        )
        labels.append(
            f'<text x="{x + cell / 2}" y="{y + 24}" text-anchor="middle" fill="{_text_fill(t)}" '
            f'font-size="12" font-weight="700" font-family="system-ui,sans-serif">{st}</text>'
        )
        if v is not None:
            labels.append(
                f'<text x="{x + cell / 2}" y="{y + 42}" text-anchor="middle" fill="{_text_fill(t)}" '
                f'font-size="10" font-family="system-ui,sans-serif">{fmt_val(v)}</text>'
            )
        else:
            labels.append(
                f'<text x="{x + cell / 2}" y="{y + 42}" text-anchor="middle" fill="#cbd5e1" '
                f'font-size="10" font-family="system-ui,sans-serif">N/A</text>'
            )

    legend_stops = "".join(
        f'<stop offset="{i * 10}%" stop-color="{_fill(i / 10)}"/>' for i in range(0, 11)
    )
    grad_id = "legendScale"
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {map_w} {map_h}" role="img" aria-labelledby="t1">
  <title id="t1">{title}</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  {''.join(tiles)}
  {''.join(labels)}
  <defs>
    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="0%">{legend_stops}</linearGradient>
  </defs>
  <rect x="560" y="520" width="180" height="14" fill="url(#{grad_id})" rx="7" ry="7"/>
  <text x="560" y="512" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">{legend}</text>
  <text x="560" y="550" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">{fmt_val(vmin)}</text>
  <text x="740" y="550" text-anchor="end" fill="#94a3b8" font-size="11" font-family="system-ui,sans-serif">{fmt_val(vmax)}</text>
</svg>
"""
    out.write_text(svg, encoding="utf-8")


def build_region_bars(region_df: pd.DataFrame, out: Path) -> None:
    rows = region_df.sort_values("Total_Nurse_HPRD", ascending=True).reset_index(drop=True)
    n = len(rows)
    left, right, top, bottom = 220, 60, 70, 50
    bar_h, gap = 28, 10
    plot_w = 520
    map_w = left + plot_w + right
    map_h = top + n * (bar_h + gap) + bottom
    vmax = float(rows["Total_Nurse_HPRD"].max())
    vmin = float(rows["Total_Nurse_HPRD"].min())

    bars: list[str] = []
    for i, r in rows.iterrows():
        y = top + i * (bar_h + gap)
        v = float(r["Total_Nurse_HPRD"])
        t = 0.5 if vmax <= vmin else (v - vmin) / (vmax - vmin)
        w = max(8.0, plot_w * (v / vmax if vmax else 0))
        name = f"Region {int(r['REGION_NUMBER'])} — {r['REGION_NAME']}"
        bars.append(
            f'<text x="{left - 12}" y="{y + bar_h / 2 + 4}" text-anchor="end" fill="#e2e8f0" '
            f'font-size="12" font-family="system-ui,sans-serif">{name}</text>'
        )
        bars.append(
            f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="6" ry="6" fill="{_fill(t)}"/>'
        )
        bars.append(
            f'<text x="{left + w + 8}" y="{y + bar_h / 2 + 4}" fill="#e2e8f0" '
            f'font-size="12" font-family="system-ui,sans-serif">{v:.3f}</text>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {map_w} {map_h}" role="img" aria-labelledby="t2">
  <title id="t2">Q1 2026 CMS Region staffing: Total Nurse HPRD</title>
  <rect width="100%" height="100%" fill="#0f172a"/>
  <text x="{map_w / 2}" y="34" text-anchor="middle" fill="#e2e8f0" font-size="18" font-weight="700"
    font-family="system-ui,sans-serif">Q1 2026 CMS Region map: Total Nurse HPRD</text>
  <text x="{map_w / 2}" y="56" text-anchor="middle" fill="#94a3b8" font-size="12"
    font-family="system-ui,sans-serif">Regional ratios = region nurse hours ÷ region resident days (CMS PBJ). Not a facility ranking.</text>
  {''.join(bars)}
</svg>
"""
    out.write_text(svg, encoding="utf-8")


def main() -> None:
    state = pd.read_csv(ROOT / "state_quarterly_metrics.csv")
    state_q = state[state["CY_Qtr"] == "2026Q1"].copy()
    hprd_by_abbr = {
        str(r["STATE"]): float(r["Total_Nurse_HPRD"]) for _, r in state_q.iterrows()
    }
    build_state_tilemap(
        hprd_by_abbr,
        ROOT / "insights-rankings-state-hprd-tilemap-q1-2026.svg",
        title="Q1 2026 U.S. state Total Nurse HPRD",
        legend="Total Nurse HPRD",
        value_fmt=".2f",
    )
    census_by_abbr = {
        str(r["STATE"]): float(r["avg_daily_census"])
        for _, r in state_q.iterrows()
        if pd.notna(r.get("avg_daily_census"))
    }
    build_state_tilemap(
        census_by_abbr,
        ROOT / "insights-rankings-state-census-tilemap-q1-2026.svg",
        title="Q1 2026 U.S. state average daily census",
        legend="Avg daily census",
        value_fmt=".0f",
    )
    # Verified from: state_quarterly_metrics.csv Contract_Percentage (CY_Qtr=2026Q1)
    contract_by_abbr = {
        str(r["STATE"]): float(r["Contract_Percentage"])
        for _, r in state_q.iterrows()
        if pd.notna(r.get("Contract_Percentage"))
    }
    build_state_tilemap(
        contract_by_abbr,
        ROOT / "insights-rankings-state-contract-tilemap-q1-2026.svg",
        title="Q1 2026 U.S. state contract staffing percentage",
        legend="Contract staff %",
        value_fmt=".1f",
    )

    region = pd.read_csv(ROOT / "cms_region_quarterly_metrics.csv")
    region_q = region[region["CY_Qtr"] == "2026Q1"].copy()
    build_region_bars(
        region_q,
        ROOT / "insights-rankings-cms-region-hprd-q1-2026.svg",
    )
    print("Wrote state HPRD + census + contract tilemaps + CMS region SVG for Q1 2026")


if __name__ == "__main__":
    main()
