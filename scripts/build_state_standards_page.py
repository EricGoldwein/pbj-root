"""Build static /state-standards HTML from macpac_state_standards_clean.csv."""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "macpac_state_standards_clean.csv"
OUT = ROOT / "state-standards.html"

MACPAC_URL = (
    "https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/"
)

STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}


def state_slug(state_name: str) -> str:
    return state_name.strip().lower().replace(" ", "-")


def display_hprd(row: pd.Series) -> str:
    """Numbers only — strip wrappers and redundant 'HPRD' (header already says Estimated HPRD)."""
    raw = str(row.get("Total_Estimated_Staffing_Requirements") or "").strip()
    display = raw
    if not display:
        display = str(row.get("Display_Text") or "").strip()
        display = re.sub(r"(?i)^state\s+standard:\s*", "", display)
        display = re.sub(r"(?i)^federal\s+minimum\s*\(?\s*", "", display)
        display = display.rstrip(")")
    display = re.sub(r"(?i)\s*HPRD\s*$", "", display).strip()
    return display or "—"


def main() -> None:
    df = pd.read_csv(CSV)
    df = df.copy()
    df["_sort"] = df["State"].astype(str).str.strip().str.lower()
    df = df.sort_values("_sort", kind="mergesort")

    rows = []
    for _, r in df.iterrows():
        state = str(r.get("State") or "").strip()
        if not state:
            continue
        slug = state_slug(state)
        value = display_hprd(r)
        is_fed = str(r.get("Is_Federal_Minimum", "")).strip().lower() in ("true", "1", "yes")
        fed_note = (
            ' <span class="ss-fed-tag" title="MACPAC federal-floor framing (~0.30 HPRD)">*</span>'
            if is_fed
            else ""
        )
        rows.append(
            f'<tr class="{"ss-row--fed" if is_fed else "ss-row--state"}">'
            f'<td><a class="ss-state-link" href="/state/{html.escape(slug)}">'
            f"{html.escape(state)}</a></td>"
            f'<td class="ss-val">{html.escape(value)}{fed_note}</td>'
            f"</tr>"
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>State staffing standards | PBJ320</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="MACPAC-cited nursing facility staffing standards by state, compiled for PBJ320 context. Estimates, not live legal citations.">
  <link rel="canonical" href="https://www.pbj320.com/state-standards">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://www.pbj320.com/state-standards">
  <meta property="og:title" content="State staffing standards | PBJ320">
  <meta property="og:description" content="MACPAC-cited nursing facility staffing standards by state. Estimates for context on PBJ320.">
  <meta property="og:site_name" content="PBJ320">
  <link rel="icon" type="image/png" href="/pbj_favicon.png">
  <link rel="stylesheet" href="/public-trust.css">
  <style>
    @font-face {{
      font-family: "DM Sans";
      src: url("/static/brand/fonts/DMSans-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }}
    @font-face {{
      font-family: "DM Sans";
      src: url("/static/brand/fonts/DMSans-Bold.ttf") format("truetype");
      font-weight: 700;
      font-style: normal;
      font-display: swap;
    }}
    @font-face {{
      font-family: "Vollkorn";
      src: url("/static/brand/fonts/Vollkorn-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }}
    @font-face {{
      font-family: "DM Mono";
      src: url("/static/brand/fonts/DMMono-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }}
    .ss-page {{
      font-family: "DM Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
      color: #e2e8f0;
    }}
    .ss-page .content {{ max-width: 820px; }}
    .ss-page .content-box h1 {{
      font-family: "Vollkorn", Georgia, "Times New Roman", serif;
      font-weight: 400;
      color: #f8fafc;
      font-size: 1.85rem;
      letter-spacing: -0.01em;
    }}
    .ss-page .content-box .meta {{
      color: #94a3b8;
      margin-bottom: 1rem;
    }}
    .ss-lede {{
      max-width: 42rem;
      color: #cbd5e1 !important;
      font-size: 1rem !important;
      line-height: 1.65;
    }}
    .ss-source-top {{
      margin: 0 0 1.1rem;
      font-size: 0.92rem;
      color: #94a3b8 !important;
    }}
    .ss-source-top a {{
      color: #93c5fd;
      font-weight: 600;
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .ss-source-top a:hover {{ color: #bfdbfe; }}
    .ss-note {{
      margin: 1.1rem 0 1.4rem;
      padding: 0.85rem 1rem;
      background: rgba(251, 146, 60, 0.12);
      border: 1px solid rgba(251, 146, 60, 0.35);
      border-radius: 10px;
      font-size: 0.92rem;
      line-height: 1.55;
      color: #fed7aa !important;
    }}
    .ss-note strong {{ color: #ffedd5; }}
    .ss-table-wrap {{
      overflow-x: auto;
      border: 1px solid rgba(148, 163, 184, 0.28);
      border-radius: 10px;
      background: #0f172a;
    }}
    .ss-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
      font-variant-numeric: tabular-nums;
      color: #e2e8f0;
    }}
    .ss-table th,
    .ss-table td {{
      padding: 0.7rem 0.95rem;
      text-align: left;
      border-bottom: 1px solid rgba(148, 163, 184, 0.18);
      vertical-align: middle;
      color: #e2e8f0;
    }}
    .ss-table th {{
      background: #1e293b;
      font-size: 0.72rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #94a3b8;
      font-weight: 700;
    }}
    .ss-table tbody tr:hover td {{ background: rgba(96, 165, 250, 0.06); }}
    .ss-table tr:last-child td {{ border-bottom: none; }}
    .ss-state-link {{
      color: #93c5fd !important;
      font-weight: 600;
      text-decoration: none;
    }}
    .ss-state-link:hover {{
      color: #bfdbfe !important;
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .ss-val {{
      font-family: "DM Mono", "DM Sans", ui-monospace, monospace;
      font-weight: 500;
      color: #f1f5f9 !important;
      white-space: nowrap;
    }}
    .ss-row--fed .ss-val {{ color: #cbd5e1 !important; }}
    .ss-fed-tag {{
      color: #94a3b8;
      font-size: 0.85em;
      margin-left: 0.15rem;
    }}
    .ss-foot {{
      margin-top: 1.25rem;
      font-size: 0.9rem;
      color: #94a3b8 !important;
    }}
    .ss-foot a {{ color: #93c5fd; }}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-NDPVY6TWBK"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-NDPVY6TWBK');
  </script>
</head>
<body class="ss-page">
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-brand">
        <a href="/">
          <img src="/pbj_favicon.png" alt="PBJ320" width="32" height="32" style="margin-right:8px;">
          <span><span style="color:white;">PBJ</span><span style="color:#818cf8;">320</span></span>
        </a>
      </div>
      <div class="nav-menu" id="navMenu">
        <a href="/about" class="nav-link">About</a>
        <a href="/report" class="nav-link">Report</a>
        <a href="/insights" class="nav-link">Insights</a>
        <a href="/phoebe" class="nav-link">PBJ Explained</a>
        <a href="/premium" class="nav-link">Premium</a>
      </div>
      <div class="nav-toggle" id="navToggle" aria-label="Menu"><span></span><span></span><span></span></div>
    </div>
  </nav>

  <main class="content">
    <div class="content-box">
      <h1>State staffing standards</h1>
      <p class="meta">MACPAC-cited estimates · sorted by state</p>

      <p class="ss-source-top">Primary source: <a href="{MACPAC_URL}" rel="noopener noreferrer" target="_blank">MACPAC — State Policies Related to Nursing Facility Staffing</a></p>

      <p class="ss-lede">PBJ320 shows estimated HPRD standards as policy context next to CMS Payroll-Based Journal (PBJ) staffing. Figures are drawn from MACPAC’s nursing facility staffing policy compendium — not a substitute for current statute or regulation.</p>

      <div class="ss-note" role="note">
        <strong>Estimates, not legal citations.</strong> Values are estimated total staffing HPRD. Rows marked with * use MACPAC’s federal-floor framing (~0.30 HPRD). Always verify against current state rules.
      </div>

      <div class="ss-table-wrap" role="region" aria-label="MACPAC state staffing standards" tabindex="0">
        <table class="ss-table">
          <thead>
            <tr>
              <th scope="col">State</th>
              <th scope="col">Estimated HPRD</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
      </div>

      <p class="ss-foot">Source: <a href="{MACPAC_URL}" rel="noopener noreferrer" target="_blank">MACPAC</a> state nursing facility staffing policies (compendium / derived estimates). Methodology: <a href="/data-sources">Data sources</a>. Related: <a href="/insights/2026-us-nursing-home-staffing-rankings">Q1 2026 staffing data</a>.</p>
    </div>
  </main>

  <script>
    (function () {{
      var t = document.getElementById('navToggle');
      var m = document.getElementById('navMenu');
      if (t && m) t.addEventListener('click', function () {{ m.classList.toggle('active'); }});
    }})();
  </script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
