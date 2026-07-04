"""Restore d08bb0a case-mix UI into app.py with desktop left/right split."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
D08 = subprocess.check_output(["git", "show", "d08bb0a:app.py"], text=True, errors="replace")

# --- HTML from d08bb0a (ui=14), wrapped for desktop split ---
html_m = re.search(
    r"(<!-- pbj-casemix-ui:14 -->.*?</div>\s*</div>\s*</div>\s*)\n''' \+ chart_block",
    D08,
    re.S,
)
if not html_m:
    raise SystemExit("d08bb0a casemix HTML not found")
d08_html = html_m.group(1).rstrip() + "\n"
# Fix summary/hero wrapper for split layout
d08_html = d08_html.replace(
    '<div class="pbj-casemix-card-body">\n  <div class="pbj-casemix-summary">\n    <div class="pbj-casemix-hero">\n      <div id="pbjCaseMixHeroBars" class="pbj-casemix-bars"></div>\n    </div>\n  </div>\n  <details class="pbj-casemix-details" id="pbjCaseMixSkillMix">',
    '<div class="pbj-casemix-card-body pbj-casemix-card-body--d08split">\n  <div class="pbj-casemix-split-v19">\n    <div class="pbj-casemix-split-col pbj-casemix-split-col--primary">\n      <div class="pbj-casemix-summary">\n        <div class="pbj-casemix-hero">\n          <div id="pbjCaseMixHeroBars" class="pbj-casemix-bars"></div>\n        </div>\n      </div>\n    </div>\n    <div class="pbj-casemix-split-col pbj-casemix-split-col--roles">\n  <details class="pbj-casemix-details pbj-casemix-details--adaptive" id="pbjCaseMixSkillMix">',
)
d08_html = d08_html.replace(
    "  </details>\n  <p class=\"pbj-casemix-caveat-foot\"",
    "  </details>\n    </div>\n  </div>\n  <p class=\"pbj-casemix-caveat-foot\"",
)
d08_html = d08_html.replace("data-pbj-casemix-ui=\"14\"", 'data-pbj-casemix-ui="14-split"')
new_html_block = d08_html + "\n"

# --- JS from d08bb0a: renderCaseMixCmiStrip through renderCaseMixCmiStrip(rc); ---
js_m = re.search(
    r"(  function renderCaseMixCmiStrip\(rc\) \{.*?  renderCaseMixCmiStrip\(rc\);\n)",
    D08,
    re.S,
)
if not js_m:
    raise SystemExit("d08bb0a casemix JS not found")
d08_js = js_m.group(1)
# Desktop: keep position breakdown open (same as v19 adaptive CSS)
d08_js += "  if (skillMixDetails && window.matchMedia('(min-width: 769px)').matches) skillMixDetails.setAttribute('open', '');\n"

app_text = APP.read_text(encoding="utf-8")

html_pat = re.compile(
    r"<!-- pbj-casemix-ui:\d+.*?-->\s*<div class=\"pbj-chart-container pbj-casemix-card\".*?</div>\s*</div>\s*</div>\s*\n''' \+ staffing_role_chart_block",
    re.S,
)
if not html_pat.search(app_text):
    raise SystemExit("current casemix HTML block not found")
app_text = html_pat.sub(new_html_block + "''' + staffing_role_chart_block", app_text, count=1)

js_pat = re.compile(
    r"  function appendRefRatioBar\(parent, actual, caseMix, barVariant\) \{.*?  renderCaseMixAcuity\(rc, skipCmiInAcuity\);\n  var skillMixDetails = document\.getElementById\('pbjCaseMixSkillMix'\);\n  if \(skillMixDetails && window\.matchMedia\('\(min-width: 769px\)'\)\.matches\) skillMixDetails\.setAttribute\('open', ''\);\n",
    re.S,
)
if not js_pat.search(app_text):
    raise SystemExit("current casemix JS block not found")
app_text = js_pat.sub(d08_js, app_text, count=1)

app_text = app_text.replace("PBJ_CASEMIX_UI_REV = '19'", "PBJ_CASEMIX_UI_REV = '14-split'")
# Invalidate provider cache entries missing new marker
old_hit = """    if 'pbj-staffing-role-chart' in body and 'data-pbj-staffing-charts=\"1\"' not in body:
        return False
    return True"""
new_hit = old_hit.replace(
    "return True",
    """if 'data-pbj-casemix-ui=\"14-split\"' not in body and 'pbj-casemix-card' in body:
        return False
    return True""",
)
if old_hit in app_text:
    app_text = app_text.replace(old_hit, new_hit)

APP.write_text(app_text, encoding="utf-8")
print("restored d08bb0a casemix with desktop split")
