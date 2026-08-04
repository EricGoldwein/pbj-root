"""Build interactive longitudinal rankings table HTML for the Q1 2026 insights draft."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Sparkline = last 4 quarters (≈1 year window ending Q1 2026)
SPARK_QUARTERS = [
    "2025Q2", "2025Q3", "2025Q4", "2026Q1",
]
# Extra quarters needed for YoY / QoQ deltas (not drawn on sparkline)
DELTA_QUARTERS = ["2025Q1", "2025Q4"]
LOAD_QUARTERS = sorted(set(SPARK_QUARTERS + DELTA_QUARTERS))

METRICS = [
    {
        "id": "total",
        "label": "Total",
        "col": "Total_Nurse_HPRD",
        "include_standard": True,
        "foot_label": "Total Nurse HPRD",
    },
    {
        "id": "rn",
        "label": "RN",
        "col": "RN_HPRD",
        "include_standard": False,
        "foot_label": "RN HPRD",
    },
    {
        "id": "aide",
        "label": "Nurse Aide",
        "col": "Nurse_Assistant_HPRD",
        "include_standard": False,
        "foot_label": "Nurse Aide HPRD",
    },
]

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DC": "District of Columbia", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota",
    "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina",
    "ND": "North Dakota", "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VA": "Virginia", "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin",
    "WV": "West Virginia", "WY": "Wyoming",
}

NAME_TO_CODE = {v.lower(): k for k, v in STATE_NAMES.items()}


def slug_for(code: str) -> str:
    return STATE_NAMES.get(code, code).lower().replace(" ", "-")


def fmt2(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):.2f}"


def load_macpac_standards() -> dict[str, dict]:
    """Return {STATE_CODE: {display, sort, listed}} for non-federal MACPAC rows >= 1.0 HPRD."""
    out: dict[str, dict] = {}
    csv_path = ROOT / "macpac_state_standards_clean.csv"
    if csv_path.is_file():
        df = pd.read_csv(csv_path)
        for _, r in df.iterrows():
            name = str(r.get("State") or "").strip()
            code = NAME_TO_CODE.get(name.lower())
            if not code:
                continue
            is_fed = str(r.get("Is_Federal_Minimum", "")).strip().lower() in ("true", "1", "yes")
            if is_fed:
                continue
            try:
                mn = float(r["Min_Staffing"])
                mx = float(r["Max_Staffing"])
            except (TypeError, ValueError, KeyError):
                continue
            # Exclude thin/partial standards below 1.0 HPRD (e.g. RN-only floors).
            if mn < 1.0:
                continue
            value_type = str(r.get("Value_Type") or "single").strip().lower()
            if value_type == "range" and abs(mx - mn) > 0.005:
                display = f"{mn:.2f}–{mx:.2f}"
                sort_v = mx
            else:
                display = f"{mn:.2f}"
                sort_v = mn
            out[code] = {"display": display, "sort": sort_v, "listed": True}
        return out

    for path in (
        ROOT / "pbj-wrapped" / "public" / "data" / "json" / "state_standards.json",
        ROOT / "state_standards.json",
    ):
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, s in data.items():
            code = str(key).upper()[:2]
            if not isinstance(s, dict):
                continue
            if str(s.get("Is_Federal_Minimum", "")).strip().lower() in ("true", "1", "yes"):
                continue
            try:
                mn = float(s.get("Min_Staffing"))
                mx = float(s.get("Max_Staffing", mn))
            except (TypeError, ValueError):
                continue
            if mn < 1.0:
                continue
            value_type = str(s.get("Value_Type") or "single").strip().lower()
            if value_type == "range" and abs(mx - mn) > 0.005:
                display = f"{mn:.2f}–{mx:.2f}"
                sort_v = mx
            else:
                display = f"{mn:.2f}"
                sort_v = mn
            out[code] = {"display": display, "sort": sort_v, "listed": True}
        break
    return out


def delta_cell(cur: float | None, prev: float | None) -> str:
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev):
        return '<td class="irt-num irt-delta irt-delta--na" data-sort="0">—</td>'
    d = float(cur) - float(prev)
    if abs(d) < 0.005:
        return f'<td class="irt-num irt-delta irt-delta--flat" data-sort="{d:.6f}">0.00</td>'
    cls = "up" if d > 0 else "down"
    sign = "+" if d > 0 else ""
    return (
        f'<td class="irt-num irt-delta irt-delta--{cls}" data-sort="{d:.6f}">'
        f"{sign}{d:.2f}</td>"
    )


def standard_cell(std: dict | None) -> str:
    if not std or not std.get("listed"):
        return '<td class="irt-num irt-std irt-std--na" data-sort="-1">—</td>'
    return (
        f'<td class="irt-num irt-std" data-sort="{std["sort"]:.6f}">'
        f'{std["display"]}</td>'
    )


def sparkline_svg(values: list[float | None], sort_key: float) -> str:
    pts = [(i, float(v)) for i, v in enumerate(values) if v is not None and not pd.isna(v)]
    if len(pts) < 2:
        return f'<td class="irt-spark" data-sort="{sort_key}">—</td>'
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w, h, pad = 72, 22, 2
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    yr = (ymax - ymin) or 0.01

    def sx(x: float) -> float:
        return pad + (x - xmin) / max(xmax - xmin, 1) * (w - 2 * pad)

    def sy(y: float) -> float:
        return h - pad - (y - ymin) / yr * (h - 2 * pad)

    poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
    lx, ly = sx(pts[-1][0]), sy(pts[-1][1])
    rising = pts[-1][1] >= pts[0][1]
    stroke = "#047857" if rising else "#b91c1c"
    svg = (
        f'<svg class="irt-spark__svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'aria-hidden="true" role="img">'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{poly}"></polyline>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.1" fill="{stroke}"></circle>'
        f"</svg>"
    )
    return f'<td class="irt-spark" data-sort="{sort_key}">{svg}</td>'


# Mini 1y-Δ ranks: exclude tiny states so small-N noise does not dominate.
# Verified from: state_quarterly_metrics.csv CY_Qtr=2026Q1 facility_count —
# clear cliff under 50 (PR 8, AK 15, DC 16, VT 33, WY 35, DE 42, HI 42);
# next is MT at 60. Cutoff excludes 7 of 52 rows.
MIN_FACILITIES_FOR_MINI_DELTA = 50


def fmt_signed(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    d = float(v)
    if abs(d) < 0.005:
        return "0.00"
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.2f}"


def delta_tone(v: float | None) -> str:
    if v is None or pd.isna(v) or abs(float(v)) < 0.005:
        return "flat"
    return "up" if float(v) > 0 else "down"


def mini_rank_rows_html(
    rows: list[tuple[int, str, float, float | None, float | None]],
) -> str:
    """Single-line table rows: (rank, state_code, d4q, current_hprd, d1q)."""
    out = []
    for rank, st, d4q, h_cur, d1q in rows:
        name = STATE_NAMES.get(st, st)
        href = f"/state/{slug_for(st)}"
        d4_cls = delta_tone(d4q)
        d1_cls = delta_tone(d1q)
        hprd_txt = fmt2(h_cur) if h_cur is not None and not pd.isna(h_cur) else "—"
        d4_txt = fmt_signed(d4q)
        out.append(
            "<tr>"
            f'<td class="insight-rank-mini-table__rank">{rank}</td>'
            f'<td class="insight-rank-mini-table__state">'
            f'<a href="{href}">{name}</a></td>'
            f'<td class="insight-rank-mini-table__combo" title="Q1 2026 HPRD / change since Q1 2025">'
            f'<span class="insight-rank-mini-table__combo-hprd">{hprd_txt}</span>'
            f'<span class="insight-rank-mini-table__combo-delta '
            f'insight-rank-mini-table__delta--{d4_cls}">{d4_txt}</span></td>'
            f'<td class="insight-rank-mini-table__num insight-rank-mini-table__col-hprd" '
            f'title="Q1 2026 Total Nurse HPRD">{hprd_txt}</td>'
            f'<td class="insight-rank-mini-table__num insight-rank-mini-table__delta '
            f'insight-rank-mini-table__col-d4 insight-rank-mini-table__delta--hero '
            f'insight-rank-mini-table__delta--{d4_cls}" '
            f'title="Change since Q1 2025">{d4_txt}</td>'
            f'<td class="insight-rank-mini-table__num insight-rank-mini-table__delta '
            f'insight-rank-mini-table__col-d1 insight-rank-mini-table__delta--{d1_cls}" '
            f'title="Change since Q4 2025">{fmt_signed(d1q)}</td>'
            "</tr>"
        )
    return "".join(out)


def build_mini_side_table(
    rows: list[tuple[int, str, float, float | None, float | None]],
    *,
    kind: str,
) -> str:
    """Single-line rows in a half-width card (gains or declines)."""
    title = "Biggest gains" if kind == "top" else "Biggest declines"
    return (
        f'<div class="insight-rank-mini insight-rank-mini--{kind}">'
        f'<h3 class="insight-rank-mini__title">{title}</h3>'
        f'<div class="insight-rank-mini-table__scroll" role="region" '
        f'aria-label="{title}" tabindex="0">'
        f'<table class="insight-rank-mini-table">'
        f"<thead><tr>"
        f'<th scope="col" class="insight-rank-mini-table__rank">#</th>'
        f'<th scope="col">State</th>'
        f'<th scope="col" class="insight-rank-mini-table__combo">Q1 · yr</th>'
        f'<th scope="col" class="insight-rank-mini-table__col-hprd">HPRD</th>'
        f'<th scope="col" class="insight-rank-mini-table__col-d4">4Q Δ</th>'
        f'<th scope="col" class="insight-rank-mini-table__col-d1">1Q Δ</th>'
        f"</tr></thead>"
        f"<tbody>{mini_rank_rows_html(rows)}</tbody>"
        f"</table></div></div>"
    )


def build_mini_delta_table(
    gains: list[tuple[int, str, float, float | None, float | None]],
    declines: list[tuple[int, str, float, float | None, float | None]],
) -> str:
    """Unified board: gains | declines, single-line rows; footnote centered under both."""
    return f"""<div class="insight-rank-board" id="state-rank-highlights">
  <div class="insight-rank-split">
    {build_mini_side_table(gains, kind="top")}
    {build_mini_side_table(declines, kind="bottom")}
  </div>
  <p class="insight-rank-mini__foot">* Excludes states with fewer than {MIN_FACILITIES_FOR_MINI_DELTA} facilities.</p>
</div>
"""


def build_metric_panel(
    metric: dict,
    pivot: dict[str, dict[str, dict]],
    standards: dict[str, dict],
    *,
    active: bool,
) -> str:
    mid = metric["id"]
    include_std = metric["include_standard"]
    rows = [
        (st, qs)
        for st, qs in pivot.items()
        if "2026Q1" in qs and qs["2026Q1"].get(mid) is not None
    ]
    rows.sort(key=lambda x: x[1]["2026Q1"][mid], reverse=True)

    body_rows = []
    for rank, (st, qs) in enumerate(rows, 1):
        name = STATE_NAMES.get(st, st)
        href = f"/state/{slug_for(st)}"
        h26 = qs["2026Q1"][mid]
        h_prior = (qs.get("2025Q4") or {}).get(mid)
        h_year = (qs.get("2025Q1") or {}).get(mid)
        series = [(qs.get(q) or {}).get(mid) for q in SPARK_QUARTERS]
        yoy = (h26 - h_year) if h_year is not None else 0.0
        cells = [
            f'<td class="irt-rank" data-sort="{rank}">{rank}</td>',
            f'<td class="irt-state" data-sort="{name.lower()}" data-abbr="{st.lower()}">'
            f'<a href="{href}">{name}</a></td>',
            sparkline_svg(series, yoy),
            f'<td class="irt-num" data-sort="{h26}">{fmt2(h26)}</td>',
            delta_cell(h26, h_prior),
            delta_cell(h26, h_year),
        ]
        if include_std:
            cells.append(standard_cell(standards.get(st)))
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    if include_std:
        head = """
        <tr>
          <th scope="col"><button type="button" class="irt-sort" data-col="0">#</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="1">State</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="2" data-default="desc" title="Sorted by change since Q1 2025">Trend</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="3" data-default="desc" aria-pressed="true">Q1 2026</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="4" title="Change since Q4 2025">vs prior qtr</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="5" title="Change since Q1 2025">vs year ago</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="6" data-default="desc" title="MACPAC estimated state staffing standard (HPRD), when listed">State standard</button></th>
        </tr>"""
        foot_extra = (
            ' <strong>State standard</strong> is a MACPAC-derived estimate when listed '
            "(floors under 1.0 HPRD omitted) — not a live legal citation "
            '(<a href="/state-standards">full table</a>).'
        )
    else:
        head = """
        <tr>
          <th scope="col"><button type="button" class="irt-sort" data-col="0">#</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="1">State</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="2" data-default="desc" title="Sorted by change since Q1 2025">Trend</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="3" data-default="desc" aria-pressed="true">Q1 2026</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="4" title="Change since Q4 2025">vs prior qtr</button></th>
          <th scope="col"><button type="button" class="irt-sort" data-col="5" title="Change since Q1 2025">vs year ago</button></th>
        </tr>"""
        foot_extra = " No state standard column for this staffing mix."

    hidden = "" if active else ' hidden="hidden"'
    aria_h = "false" if active else "true"
    return f"""
  <div class="insight-rankings__panel" data-panel="{mid}" role="tabpanel" id="irt-panel-{mid}" aria-labelledby="irt-tab-{mid}"{hidden} aria-hidden="{aria_h}">
    <div class="insight-rankings__scroll" role="region" aria-label="Q1 2026 {metric['foot_label']} by state" tabindex="0">
      <table class="insight-rankings__table" id="irt-table-{mid}">
        <thead>{head}
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>
    <p class="insight-rankings__foot"><strong>Q1 2026</strong> is {metric['foot_label']} (statewide hours ÷ resident days).{foot_extra} <strong>vs prior qtr</strong> = change since Q4 2025. <strong>vs year ago</strong> = change since Q1 2025. Sparklines show the last four quarters. <a href="/report?quarter=2026Q1">Full interactive map</a>.</p>
  </div>"""


def main() -> None:
    standards = load_macpac_standards()
    usecols = ["STATE", "CY_Qtr", "facility_count"] + [m["col"] for m in METRICS]
    df = pd.read_csv(ROOT / "state_quarterly_metrics.csv", usecols=usecols)

    # pivot[state][quarter][metric_id] = float
    pivot: dict[str, dict[str, dict]] = {}
    for _, r in df[df["CY_Qtr"].isin(LOAD_QUARTERS)].iterrows():
        st = str(r["STATE"])
        q = str(r["CY_Qtr"])
        slot = pivot.setdefault(st, {}).setdefault(q, {})
        for m in METRICS:
            val = r[m["col"]]
            if pd.isna(val):
                continue
            slot[m["id"]] = float(val)
            if m["id"] == "total":
                slot["n"] = int(r["facility_count"])

    # Mini ranks: Total Nurse HPRD 1y Δ (Q1 2025 → Q1 2026), excluding tiny states
    # Each row also carries Q1 2026 level + 1Q Δ (vs Q4 2025) for display.
    delta_rows: list[tuple[str, float, float, float | None]] = []
    excluded_tiny: list[tuple[str, int]] = []
    for st, qs in pivot.items():
        cur = qs.get("2026Q1") or {}
        yoy_q = qs.get("2025Q1") or {}
        prior_q = qs.get("2025Q4") or {}
        h26 = cur.get("total")
        h25 = yoy_q.get("total")
        h_q4 = prior_q.get("total")
        n_fac = cur.get("n")
        if h26 is None or h25 is None:
            continue
        if n_fac is None or int(n_fac) < MIN_FACILITIES_FOR_MINI_DELTA:
            excluded_tiny.append((st, int(n_fac or 0)))
            continue
        d4q = float(h26) - float(h25)
        d1q = (float(h26) - float(h_q4)) if h_q4 is not None else None
        delta_rows.append((st, d4q, float(h26), d1q))
    delta_rows.sort(key=lambda x: x[1], reverse=True)
    n_delta = len(delta_rows)
    gains = [
        (i, st, d4q, h, d1q)
        for i, (st, d4q, h, d1q) in enumerate(delta_rows[:5], 1)
    ]
    bottom_slice = list(reversed(delta_rows[-5:]))  # steepest declines first
    declines = [
        (i, st, d4q, h, d1q)
        for i, (st, d4q, h, d1q) in enumerate(bottom_slice, 1)
    ]
    mini_html = build_mini_delta_table(gains, declines)
    n = len(
        [
            st
            for st, qs in pivot.items()
            if "2026Q1" in qs and qs["2026Q1"].get("total") is not None
        ]
    )

    tab_btns = []
    for i, m in enumerate(METRICS):
        selected = "true" if i == 0 else "false"
        pressed = "true" if i == 0 else "false"
        cls = "insight-rankings__tab" + (" is-active" if i == 0 else "")
        tab_btns.append(
            f'<button type="button" class="{cls}" role="tab" id="irt-tab-{m["id"]}" '
            f'data-metric="{m["id"]}" aria-selected="{selected}" aria-pressed="{pressed}" '
            f'aria-controls="irt-panel-{m["id"]}">{m["label"]}</button>'
        )

    panels = [
        build_metric_panel(m, pivot, standards, active=(i == 0))
        for i, m in enumerate(METRICS)
    ]

    table_html = f"""<div class="insight-data-section" id="state-rankings">
  <div class="insight-data-section__head">
    <h2 class="insight-data-section__title">State staffing rankings, Q1 2026</h2>
  </div>
  <aside class="insight-note insight-note--inline" role="note">
    <p class="insight-note__body"><strong>Note:</strong> State staffing data is thin without context. Statewide HPRD should be used in context of other metrics including demographics, geography, and policy. For more, read “<a href="https://320insight.substack.com/p/2025-us-nursing-home-staffing-rankings">Why staffing HPRD is the batting average of nursing homes</a>”.</p>
  </aside>
  <div class="insight-rankings" id="insight-rankings-q1-2026" data-quarter="2026Q1">
  <div class="insight-rankings__toolbar">
    <div class="insight-rankings__tabs" role="tablist" aria-label="Staffing metric">
      {''.join(tab_btns)}
    </div>
    <label class="insight-rankings__search">
      <span class="visually-hidden">Filter states</span>
      <input type="search" id="irt-filter" placeholder="Filter by state…" autocomplete="off" enterkeyhint="search" title="Type a state name. Click column headers to sort." />
    </label>
    <span class="insight-rankings__meta">Click headers to sort · trend = last 4 quarters</span>
  </div>
  {''.join(panels)}
</div>
</div>
"""

    mini_out = ROOT / "insights_posts" / "_rankings_mini_q1_2026.fragment.html"
    table_out = ROOT / "insights_posts" / "_rankings_table_q1_2026.fragment.html"
    mini_out.write_text(mini_html, encoding="utf-8")
    table_out.write_text(table_html, encoding="utf-8")
    excl_lbl = ", ".join(f"{st}({n})" for st, n in sorted(excluded_tiny, key=lambda x: x[1]))
    print(
        f"Wrote {mini_out.name} + {table_out.name} "
        f"({n} states; mini delta eligible={n_delta}, "
        f"excluded n<{MIN_FACILITIES_FOR_MINI_DELTA}: {excl_lbl or 'none'}; "
        f"{len(standards)} MACPAC standards >= 1.0)"
    )
    if delta_rows:
        print(
            "Mini top5 (1y d):",
            ", ".join(
                f"{st} 4Q={d4q:+.2f} h={h:.2f} 1Q="
                f"{('n/a' if d1q is None else f'{d1q:+.2f}')}"
                for st, d4q, h, d1q in delta_rows[:5]
            ),
        )
        print(
            "Mini bottom5 (1y d):",
            ", ".join(
                f"{st} 4Q={d4q:+.2f} h={h:.2f} 1Q="
                f"{('n/a' if d1q is None else f'{d1q:+.2f}')}"
                for st, d4q, h, d1q in bottom_slice
            ),
        )


if __name__ == "__main__":
    main()
