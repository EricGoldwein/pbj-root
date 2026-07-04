#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

html = ROOT / "ownership" / "owner_profile_html.py"
t = html.read_text(encoding="utf-8")
t = t.replace(
    '<div class="owner-snapshot-label">Staffing (HPRD)</div>',
    '<div class="owner-snapshot-label" title="Resident-weighted mean from PBJ (verified facilities)">'
    "HPRD (weighted)</div>",
)
t = t.replace(
    "'<th data-sort=\"hprd\" class=\"sortable num owner-col-hprd\">HPRD <span class=\"sort-icon\"></span></th>'",
    "'<th data-sort=\"hprd\" class=\"sortable num owner-col-hprd\" title=\"Resident-weighted PBJ total nurse HPRD\">"
    "HPRD (wtd) <span class=\"sort-icon\"></span></th>'",
)
html.write_text(t, encoding="utf-8")

cfg = ROOT / "site_public_config.py"
st = cfg.read_text(encoding="utf-8")
st = st.replace(
    "- /owners/ — limited ownership research tool.",
    "- /owners/<10-digit PAC> — CMS ownership profiles (Connecticut and New York).\n"
    "- /owner/ — FEC political contributions search (not indexed).",
)
cfg.write_text(st, encoding="utf-8")
print("patched")
