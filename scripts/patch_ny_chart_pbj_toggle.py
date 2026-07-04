#!/usr/bin/env python3
"""Move NY report PBJ Standard controls to top-right favicon toggles on charts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
TESTS = ROOT / "tests" / "test_ny_scenario_controls.py"

OLD_DOCK_CSS = """/* ── PBJ Standard: floating dock + scenario chart markers ── */
.pbj-standard-dock {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  width: min(22rem, calc(100vw - 24px));
  touch-action: none;
}
.pbj-standard-fab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 10px 14px 10px 10px;
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 999px;
  background: #fff;
  color: var(--pbj-brand-ink);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  line-height: 1.2;
  cursor: pointer;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.14);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.pbj-standard-fab:hover,
.pbj-standard-fab:focus-visible {
  border-color: var(--pbj-brand);
  background: var(--pbj-brand-light);
  outline: none;
  box-shadow: 0 6px 22px rgba(99, 102, 241, 0.22);
}
.pbj-standard-fab[hidden] { display: none !important; }
.pbj-standard-fab--scenario {
  border-color: rgba(217, 119, 6, 0.45);
  background: var(--accent-warn-light);
  color: #92400e;
}
.pbj-standard-fab-favicon {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  object-fit: contain;
  flex-shrink: 0;
}
.pbj-standard-fab-chip {
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 8px;
  letter-spacing: 0.04em;
  background: #fff;
  color: #92400e;
  border: 1px solid rgba(217, 119, 6, 0.35);
}
.pbj-standard-fab-chip[hidden] { display: none !important; }
.pbj-standard-panel {
  width: 100%;
  border: 1px solid var(--paper-rule);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 10px 36px rgba(15, 23, 42, 0.16);
  overflow: hidden;
}
.pbj-standard-panel[hidden] { display: none !important; }
.pbj-standard-panel-drag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--paper-rule);
  background: var(--paper-warm);
  cursor: grab;
  user-select: none;
  touch-action: none;
}
.pbj-standard-panel-drag:active { cursor: grabbing; }
.pbj-standard-panel-drag img {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  flex-shrink: 0;
}
.pbj-standard-panel-drag-title {
  flex: 1;
  min-width: 0;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.pbj-standard-panel-collapse {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  margin: 0;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: #fff;
  color: var(--ink-muted);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}
.pbj-standard-panel-body {
  padding: 12px 14px 14px;
  max-height: min(70vh, 28rem);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}"""

NEW_TOGGLE_CSS = """/* ── PBJ Standard: per-chart favicon toggle (top-right) ── */
.chart-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 12px;
  margin-bottom: 12px;
}
.chart-header .chart-title {
  margin-bottom: 0;
  flex: 1;
  min-width: 0;
}
.data-table-wrap[data-scenario-surface] {
  position: relative;
  padding-top: 2.75rem;
}
.data-table-wrap[data-scenario-surface] > .chart-pbj-toggle-dock {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 2;
}
.county-map-wrap[data-scenario-surface] {
  position: relative;
}
.chart-pbj-toggle-dock {
  position: relative;
  flex-shrink: 0;
}
.chart-pbj-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 6px 10px 6px 6px;
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 999px;
  background: #fff;
  color: var(--pbj-brand-ink);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  line-height: 1.2;
  cursor: pointer;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.chart-pbj-toggle-btn:hover,
.chart-pbj-toggle-btn:focus-visible {
  border-color: var(--pbj-brand);
  background: var(--pbj-brand-light);
  outline: none;
}
.chart-pbj-toggle-btn--scenario {
  border-color: rgba(217, 119, 6, 0.45);
  background: var(--accent-warn-light);
  color: #92400e;
}
.chart-pbj-toggle-btn[aria-expanded="true"] {
  border-color: var(--pbj-brand);
  background: var(--pbj-brand-light);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.18);
}
.chart-pbj-toggle-favicon {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  object-fit: contain;
  flex-shrink: 0;
}
.chart-pbj-toggle-label {
  max-width: 5.5rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chart-pbj-toggle-chip {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 8px;
  letter-spacing: 0.04em;
  background: #fff;
  color: #92400e;
  border: 1px solid rgba(217, 119, 6, 0.35);
}
.chart-pbj-toggle-chip[hidden] { display: none !important; }
.chart-pbj-toggle-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 24;
  width: min(18.5rem, calc(100vw - 28px));
  border: 1px solid var(--paper-rule);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 10px 32px rgba(15, 23, 42, 0.14);
}
.chart-pbj-toggle-panel[hidden] { display: none !important; }
.chart-pbj-toggle-panel .chart-pbj-controls {
  margin: 0;
  border: 0;
  border-radius: 10px;
  background: #fff;
  padding: 12px 14px 10px;
}
.chart-pbj-toggle-panel .ny-scenario-live-badge {
  margin: 0 0 10px;
}
.chart-pbj-toggle-panel .ny-scenario-reset {
  width: 100%;
}"""

OLD_CHART_CONTROLS_CSS = """.chart-pbj-controls {
  margin: 0 0 14px;
  padding: 12px 14px 10px;
  border: 1px solid var(--paper-rule);
  border-radius: 8px;
  background: var(--paper-warm);
}
.chart-pbj-controls--quarterly {
  margin-top: 10px;
  margin-bottom: 14px;
}"""

NEW_CHART_CONTROLS_CSS = """.chart-pbj-controls {
  margin: 0 0 14px;
  padding: 12px 14px 10px;
  border: 1px solid var(--paper-rule);
  border-radius: 8px;
  background: var(--paper-warm);
}
.chart-pbj-controls--in-panel {
  margin: 0;
  border: 0;
  background: transparent;
  padding: 0;
}
.chart-pbj-controls--quarterly {
  margin-top: 0;
  margin-bottom: 0;
}"""

OLD_INJECT_FN = """  function injectDailyChartControls() {
    var tpl = document.getElementById('chart-daily-controls-tpl');
    if (!tpl || !tpl.content) return;
    document.querySelectorAll('[data-scenario-surface]').forEach(function (wrap) {
      if (wrap.querySelector('.chart-pbj-controls--daily')) return;
      var node = tpl.content.cloneNode(true);
      var ribbon = wrap.querySelector('[data-scenario-ribbon]');
      var title = wrap.querySelector('.chart-title');
      if (ribbon) wrap.insertBefore(node, ribbon.nextSibling);
      else if (title) wrap.insertBefore(node, title);
      else wrap.insertBefore(node, wrap.firstChild);
    });
  }"""

NEW_INJECT_FN = """  function injectDailyChartControls() {
    var tpl = document.getElementById('chart-daily-controls-tpl');
    if (!tpl || !tpl.content) return;
    var firstSlider = true;
    document.querySelectorAll('[data-scenario-surface]').forEach(function (wrap) {
      if (wrap.closest('.quarterly-statutory-block')) return;
      if (wrap.querySelector('.chart-pbj-toggle-dock')) return;
      var node = tpl.content.cloneNode(true);
      if (!firstSlider) {
        var slider = node.querySelector('#hprd-slider');
        if (slider) slider.removeAttribute('id');
        var out = node.querySelector('#hprd-value');
        if (out) out.removeAttribute('id');
      }
      firstSlider = false;
      var title = wrap.querySelector('.chart-title');
      if (title && !title.closest('.chart-header')) {
        var header = document.createElement('div');
        header.className = 'chart-header';
        title.parentNode.insertBefore(header, title);
        header.appendChild(title);
        header.appendChild(node);
      } else {
        var ribbon = wrap.querySelector('[data-scenario-ribbon]');
        if (ribbon) wrap.insertBefore(node, ribbon.nextSibling);
        else wrap.insertBefore(node, wrap.firstChild);
      }
    });
  }

  function closeAllPbjTogglePanels(except) {
    document.querySelectorAll('.chart-pbj-toggle-panel').forEach(function (panel) {
      if (except && panel === except) return;
      panel.hidden = true;
      var dock = panel.closest('.chart-pbj-toggle-dock');
      var btn = dock ? dock.querySelector('.chart-pbj-toggle-btn') : null;
      if (btn) btn.setAttribute('aria-expanded', 'false');
    });
  }

  function initChartPbjToggles() {
    document.querySelectorAll('.chart-pbj-toggle-dock').forEach(function (dock) {
      var btn = dock.querySelector('.chart-pbj-toggle-btn');
      var panel = dock.querySelector('.chart-pbj-toggle-panel');
      if (!btn || !panel) return;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = panel.hidden;
        closeAllPbjTogglePanels(open ? panel : null);
        panel.hidden = !open;
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
    document.addEventListener('click', function () { closeAllPbjTogglePanels(null); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllPbjTogglePanels(null);
    });
    document.querySelectorAll('.chart-pbj-toggle-panel').forEach(function (panel) {
      panel.addEventListener('click', function (e) { e.stopPropagation(); });
    });
    document.querySelectorAll('.ny-scenario-reset').forEach(function (btn) {
      btn.addEventListener('click', function () { resetScenario(); });
    });
  }"""

OLD_SYNC_UI = """    ['dock-threshold-field', 'pick-threshold-field'].forEach(function (id) {
      var wrap = document.getElementById(id);
      if (wrap) wrap.classList.toggle('is-locked', locked);
    });"""

NEW_SYNC_UI = """    document.querySelectorAll('.chart-pbj-threshold-field, #pick-threshold-field').forEach(function (wrap) {
      wrap.classList.toggle('is-locked', locked);
    });"""

OLD_UPDATE_CHROME_FAB = """    var fab = document.getElementById('pbj-standard-fab');
    var fabChip = document.getElementById('pbj-standard-fab-chip');
    if (fab) fab.classList.toggle('pbj-standard-fab--scenario', !def);
    if (fabChip) {
      if (def || !chipText) {
        fabChip.hidden = true;
        fabChip.textContent = '';
      } else {
        fabChip.hidden = false;
        fabChip.textContent = chipText;
      }
    }"""

NEW_UPDATE_CHROME_TOGGLE = """    document.querySelectorAll('.chart-pbj-toggle-dock').forEach(function (dock) {
      var btn = dock.querySelector('.chart-pbj-toggle-btn');
      var chip = dock.querySelector('.chart-pbj-toggle-chip');
      if (btn) btn.classList.toggle('chart-pbj-toggle-btn--scenario', !def);
      if (chip) {
        if (def || !chipText) {
          chip.hidden = true;
          chip.textContent = '';
        } else {
          chip.hidden = false;
          chip.textContent = chipText;
        }
      }
    });"""

OLD_INIT_SCENARIO = """  function initScenarioControls() {
    var root = activeRoot();
    if (!root) return;
    global.PBJ_REPORT_METRIC_MODE = primaryModeKey(root);

    injectDailyChartControls();
    bindMetricRadios(root, 'ny-metric-mode');
    bindBelowTestRadios('below-test');
    bindChartSliders();
    updateChrome();
  }"""

NEW_INIT_SCENARIO = """  function initScenarioControls() {
    var root = activeRoot();
    if (!root) return;
    global.PBJ_REPORT_METRIC_MODE = primaryModeKey(root);

    injectDailyChartControls();
    initChartPbjToggles();
    bindMetricRadios(root, 'ny-metric-mode');
    bindBelowTestRadios('below-test');
    bindChartSliders();
    updateChrome();
  }"""

OLD_SCENARIO_EXPORT = """  global.PBJ320ScenarioControls = {
    init: initScenarioControls,
    updateChrome: updateChrome,
    setDockOpen: setDockOpen,
    sliderUiMin: SLIDER_UI_MIN,
    sliderUiMax: SLIDER_UI_MAX,
  };"""

NEW_SCENARIO_EXPORT = """  global.PBJ320ScenarioControls = {
    init: initScenarioControls,
    updateChrome: updateChrome,
    closeAllPanels: closeAllPbjTogglePanels,
    sliderUiMin: SLIDER_UI_MIN,
    sliderUiMax: SLIDER_UI_MAX,
  };"""

OLD_TEMPLATE = """<template id="chart-daily-controls-tpl">
  <div class="chart-pbj-controls chart-pbj-controls--daily">
    <div class="chart-pbj-controls-grid">
      <fieldset class="chart-pbj-fieldset">
        <legend>Staff mix</legend>
        <div class="ny-scenario-modes ny-scenario-modes--row chart-pbj-modes" role="radiogroup" aria-label="Staff mix">
          <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
            <input type="radio" name="ny-metric-mode" value="ny_mapped_non_admin_hprd" checked>
            <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Direct</span></span>
          </label>
          <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
            <input type="radio" name="ny-metric-mode" value="ny_mapped_include_don_sensitivity">
            <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Direct</span><span class="ny-scenario-mode-title--sub">incl. DON</span></span>
          </label>
          <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
            <input type="radio" name="ny-metric-mode" value="broad_pbj_total_hprd">
            <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Total</span><span class="ny-scenario-mode-title--sub">nurse</span></span>
          </label>
        </div>
      </fieldset>
      <div class="chart-pbj-fieldset chart-pbj-threshold-field">
        <label class="chart-pbj-threshold-label">HPRD threshold</label>
        <div class="ny-scenario-threshold-row">
          <input type="range" class="hprd-slider chart-hprd-slider" min="3" max="4.1" step="0.05" value="3.5" aria-valuemin="3" aria-valuemax="4.1" aria-valuenow="3.5">
          <output class="hprd-value chart-hprd-value">3.50</output>
        </div>
      </div>
    </div>
    <p class="chart-pbj-standard-line" data-pbj-standard-line aria-live="polite"></p>
  </div>
</template>"""

NEW_TEMPLATE = """<template id="chart-daily-controls-tpl">
  <div class="chart-pbj-toggle-dock" data-pbj-toggle-dock>
    <button type="button" class="chart-pbj-toggle-btn" aria-expanded="false" aria-label="PBJ Standard settings">
      <img src="/pbj_favicon.png" width="22" height="22" alt="" class="chart-pbj-toggle-favicon" decoding="async" aria-hidden="true">
      <span class="chart-pbj-toggle-label">Standard</span>
      <span class="chart-pbj-toggle-chip" hidden></span>
    </button>
    <div class="chart-pbj-toggle-panel" hidden>
      <div class="chart-pbj-controls chart-pbj-controls--daily chart-pbj-controls--in-panel">
        <p class="ny-scenario-live-badge" aria-live="polite" hidden></p>
        <div class="chart-pbj-controls-grid">
          <fieldset class="chart-pbj-fieldset">
            <legend>Staff mix</legend>
            <div class="ny-scenario-modes ny-scenario-modes--row chart-pbj-modes" role="radiogroup" aria-label="Staff mix">
              <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
                <input type="radio" name="ny-metric-mode" value="ny_mapped_non_admin_hprd" checked>
                <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Direct</span></span>
              </label>
              <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
                <input type="radio" name="ny-metric-mode" value="ny_mapped_include_don_sensitivity">
                <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Direct</span><span class="ny-scenario-mode-title--sub">incl. DON</span></span>
              </label>
              <label class="ny-scenario-mode ny-scenario-mode--row ny-scenario-mode--compact">
                <input type="radio" name="ny-metric-mode" value="broad_pbj_total_hprd">
                <span class="ny-scenario-mode-body"><span class="ny-scenario-mode-title--main">Total</span><span class="ny-scenario-mode-title--sub">nurse</span></span>
              </label>
            </div>
          </fieldset>
          <div class="chart-pbj-fieldset chart-pbj-threshold-field" id="dock-threshold-field">
            <label class="chart-pbj-threshold-label" for="hprd-slider">HPRD threshold</label>
            <div class="ny-scenario-threshold-row">
              <input type="range" class="hprd-slider chart-hprd-slider" id="hprd-slider" min="3" max="4.1" step="0.05" value="3.5" aria-valuemin="3" aria-valuemax="4.1" aria-valuenow="3.5">
              <output class="hprd-value chart-hprd-value" id="hprd-value" for="hprd-slider">3.50</output>
            </div>
          </div>
        </div>
        <p class="chart-pbj-standard-line" data-pbj-standard-line aria-live="polite"></p>
        <div class="ny-scenario-actions">
          <button type="button" class="ny-scenario-reset">Reset to defaults</button>
        </div>
      </div>
    </div>
  </div>
</template>"""

OLD_QUARTERLY_HEADER = """      <div class="quarterly-chart-header">
        <div class="quarterly-chart-heading">
          <span class="pbj-standard-pill">Quarterly</span>
          <h3 id="quarterly-statutory-heading">Statutory-style mapping · 2025</h3>
          <p class="quarterly-chart-dek">PBJ role-hour rollups by facility-quarter. Descriptive mapping, not NY DOH enforcement.</p>
        </div>
      </div>
      <div class="chart-pbj-controls chart-pbj-controls--quarterly" id="quarterly-chart-controls">"""

NEW_QUARTERLY_HEADER = """      <div class="quarterly-chart-header">
        <div class="quarterly-chart-heading">
          <span class="pbj-standard-pill">Quarterly</span>
          <h3 id="quarterly-statutory-heading">Statutory-style mapping · 2025</h3>
          <p class="quarterly-chart-dek">PBJ role-hour rollups by facility-quarter. Descriptive mapping, not NY DOH enforcement.</p>
        </div>
        <div class="chart-pbj-toggle-dock chart-pbj-toggle-dock--quarterly" id="quarterly-pbj-toggle">
          <button type="button" class="chart-pbj-toggle-btn" aria-expanded="false" aria-controls="quarterly-pbj-panel" aria-label="Quarterly PBJ Standard settings">
            <img src="/pbj_favicon.png" width="22" height="22" alt="" class="chart-pbj-toggle-favicon" decoding="async" aria-hidden="true">
            <span class="chart-pbj-toggle-label">Standard</span>
            <span class="chart-pbj-toggle-chip" hidden></span>
          </button>
          <div class="chart-pbj-toggle-panel" id="quarterly-pbj-panel" hidden>
            <div class="chart-pbj-controls chart-pbj-controls--quarterly chart-pbj-controls--in-panel" id="quarterly-chart-controls">"""

OLD_QUARTERLY_CLOSE = """        <p class="chart-pbj-standard-line" id="quarterly-standard-line" aria-live="polite"></p>
      </div>
      <div class="quarterly-charts-grid">"""

NEW_QUARTERLY_CLOSE = """        <p class="chart-pbj-standard-line" id="quarterly-standard-line" aria-live="polite"></p>
            </div>
          </div>
        </div>
      </div>
      <div class="quarterly-charts-grid">"""

OLD_FACILITIES_LEAD = """          <p class="facilities-explorer-lead">Search and sort all <strong>596</strong> homes by daily % below <strong>3.50</strong> HPRD. Quarterly columns use statutory-style PBJ mapping; <strong>floor</strong> counts quarters below the CNA-side (<strong>2.20</strong>) or licensed-nurse (<strong>1.10</strong>) minima.</p>"""

NEW_FACILITIES_LEAD = """          <p class="facilities-explorer-lead">Search and sort all <strong>596</strong> homes by daily % below <strong>3.50</strong> HPRD. Quarterly columns use statutory-style PBJ mapping; floor is <strong>3.50</strong> Direct HPRD, including <strong>2.20</strong> CNA-side HPRD and <strong>1.10</strong> licensed-nurse HPRD.</p>"""

OLD_METHODS_CHARTS = """      <p><strong>Charts:</strong> Daily scenario charts include inline <strong>PBJ Standard</strong> controls; quarterly charts have their own floor scope toggle.</p>"""

NEW_METHODS_CHARTS = """      <p><strong>Charts:</strong> Daily and quarterly scenario charts include a <strong>PBJ Standard</strong> favicon toggle at the top right.</p>"""

OLD_PICK_DIALOG = """          <p><strong>Daily charts</strong> (day of week, provider bands, ownership, county map): use the controls inside each chart&mdash;<strong>HPRD threshold</strong> and <strong>staff mix</strong> (Direct, Direct incl. DON, Total nurse).</p>
          <p><strong>Quarterly charts</strong> below the facility table: default to <strong>any mapped floor</strong> (3.50 total + 2.20 CNA-side + 1.10 licensed nurse). Switch to <strong>3.50 total only</strong> or change staff mix in that block.</p>"""

NEW_PICK_DIALOG = """          <p><strong>Daily charts</strong> (day of week, provider bands, ownership, county map): open the <strong>PBJ favicon</strong> at the top right of each chart for <strong>HPRD threshold</strong> and <strong>staff mix</strong> (Direct, Direct incl. DON, Total nurse).</p>
          <p><strong>Quarterly charts</strong> below the facility table: use the same favicon toggle for <strong>any mapped floor</strong> (3.50 total + 2.20 CNA-side + 1.10 licensed nurse) vs. <strong>3.50 total only</strong>.</p>"""

DOCK_HTML_PATTERN = re.compile(
    r"<div id=\"pbj-standard-dock\".*?</div>\s*</body>",
    re.DOTALL,
)

MOBILE_DOCK_CSS = """@media (max-width: 640px) {
  .pbj-standard-dock {
    right: 12px;
    bottom: 12px;
    width: min(20rem, calc(100vw - 20px));
  }
  .pbj-standard-fab {
    padding: 8px 12px 8px 8px;
    font-size: 9px;
  }"""

MOBILE_TOGGLE_CSS = """@media (max-width: 640px) {
  .chart-pbj-toggle-label { display: none; }
  .chart-pbj-toggle-panel {
    right: 0;
    left: auto;
    width: min(18rem, calc(100vw - 24px));
  }"""

TEST_OLD = """        self.assertIn('id="pbj-standard-dock"', self.html)

        self.assertIn('id="pbj-standard-fab"', self.html)"""

TEST_NEW = """        self.assertIn('chart-pbj-toggle-dock', self.html)

        self.assertIn('chart-pbj-toggle-btn', self.html)

        self.assertIn('chart-pbj-toggle-panel', self.html)

        self.assertNotIn('id="pbj-standard-dock"', self.html)

        self.assertNotIn('id="pbj-standard-fab"', self.html)"""

TEST_INJECT_OLD = """        self.assertIn('chart-pbj-controls--daily', self.html)"""

TEST_INJECT_NEW = """        self.assertIn('chart-pbj-controls--daily', self.html)

        self.assertIn('id="quarterly-pbj-toggle"', self.html)"""


def _replace(html: str, old: str, new: str, label: str) -> str:
    if old not in html:
        raise RuntimeError(f"Missing patch anchor: {label}")
    return html.replace(old, new, 1)


def patch_html(html: str) -> str:
    html = _replace(html, OLD_DOCK_CSS, NEW_TOGGLE_CSS, "dock css")
    html = _replace(html, OLD_CHART_CONTROLS_CSS, NEW_CHART_CONTROLS_CSS, "chart controls css")
    html = _replace(html, OLD_INJECT_FN, NEW_INJECT_FN, "injectDailyChartControls")
    html = _replace(html, OLD_SYNC_UI, NEW_SYNC_UI, "syncBelowTestUi")
    html = _replace(html, OLD_UPDATE_CHROME_FAB, NEW_UPDATE_CHROME_TOGGLE, "updateChrome fab")
    html = _replace(html, OLD_INIT_SCENARIO, NEW_INIT_SCENARIO, "initScenarioControls")
    html = _replace(html, OLD_SCENARIO_EXPORT, NEW_SCENARIO_EXPORT, "scenario export")
    html = _replace(html, OLD_TEMPLATE, NEW_TEMPLATE, "template")
    html = _replace(html, OLD_QUARTERLY_HEADER, NEW_QUARTERLY_HEADER, "quarterly header")
    html = _replace(html, OLD_QUARTERLY_CLOSE, NEW_QUARTERLY_CLOSE, "quarterly close")
    html = _replace(html, OLD_FACILITIES_LEAD, NEW_FACILITIES_LEAD, "facilities lead")
    html = _replace(html, OLD_METHODS_CHARTS, NEW_METHODS_CHARTS, "methods charts")
    html = _replace(html, OLD_PICK_DIALOG, NEW_PICK_DIALOG, "pick dialog")
    if MOBILE_DOCK_CSS in html:
        html = html.replace(MOBILE_DOCK_CSS, MOBILE_TOGGLE_CSS, 1)
    html = DOCK_HTML_PATTERN.sub("</body>", html)
    # Remove unused dock helpers if still present.
    for fn_block in (
        """  function dockOpen() {
    var panel = document.getElementById('pbj-standard-panel');
    return !!(panel && !panel.hidden);
  }

  function setDockOpen(open) {
    var panel = document.getElementById('pbj-standard-panel');
    var fab = document.getElementById('pbj-standard-fab');
    if (!panel || !fab) return;
    panel.hidden = !open;
    fab.hidden = !!open;
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

""",
        """  function initDockDrag() {
    var dock = document.getElementById('pbj-standard-dock');
    var handle = document.getElementById('pbj-standard-panel-drag');
    if (!dock || !handle) return;
    var dragging = false;
    var startX = 0;
    var startY = 0;
    var startLeft = 0;
    var startTop = 0;
    handle.addEventListener('pointerdown', function (e) {
      if (e.target.closest('.pbj-standard-panel-collapse')) return;
      dragging = true;
      var rect = dock.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startLeft = rect.left;
      startTop = rect.top;
      dock.style.right = 'auto';
      dock.style.bottom = 'auto';
      dock.style.left = startLeft + 'px';
      dock.style.top = startTop + 'px';
      handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener('pointerdown', function (e) {
      if (e.target.closest('.pbj-standard-panel-collapse')) return;
      dragging = true;
      var rect = dock.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startLeft = rect.left;
      startTop = rect.top;
      dock.style.right = 'auto';
      dock.style.bottom = 'auto';
      dock.style.left = startLeft + 'px';
      dock.style.top = startTop + 'px';
      handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      dock.style.left = (startLeft + e.clientX - startX) + 'px';
      dock.style.top = (startTop + e.clientY - startY) + 'px';
    });
    function endDrag() { dragging = false; }
    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);
  }

""",
    ):
        html = html.replace(fn_block, "")
    # Fix duplicate pointerdown if only partial block matched - use regex for initDockDrag
    html = re.sub(
        r"  function dockOpen\(\) \{.*?fab\.setAttribute\('aria-expanded', open \? 'true' : 'false'\);\n  \}\n\n",
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"  function initDockDrag\(\) \{.*?handle\.addEventListener\('pointercancel', endDrag\);\n  \}\n\n",
        "",
        html,
        flags=re.DOTALL,
    )
    # Badge sync: also update badges inside toggle panels
    if "document.querySelectorAll('.ny-scenario-live-badge')" not in html:
        html = html.replace(
            """    ['ny-scenario-live-badge', 'dock-scenario-live-badge'].forEach(function (id) {
      var badge = document.getElementById(id);
      if (!badge) return;
      if (def) {
        badge.hidden = true;
        badge.textContent = '';
      } else {
        badge.hidden = false;
        badge.textContent = statusText;
      }
      badge.classList.toggle('ny-scenario-live-badge--scenario', !def);
    });""",
            """    document.querySelectorAll('.ny-scenario-live-badge').forEach(function (badge) {
      if (def) {
        badge.hidden = true;
        badge.textContent = '';
      } else {
        badge.hidden = false;
        badge.textContent = statusText;
      }
      badge.classList.toggle('ny-scenario-live-badge--scenario', !def);
    });""",
        )
    return html


def patch_tests(tests: str) -> str:
    tests = _replace(tests, TEST_OLD, TEST_NEW, "test dock markers")
    tests = _replace(tests, TEST_INJECT_OLD, TEST_INJECT_NEW, "test toggle ids")
    return tests


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    html = patch_html(html)
    HTML.write_text(html, encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")
    tests = patch_tests(tests)
    TESTS.write_text(tests, encoding="utf-8")
    print(f"Patched {HTML.name} and {TESTS.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
