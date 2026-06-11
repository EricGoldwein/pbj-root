"""NY staffing report: metric scenario controls data + prose immutability."""



from __future__ import annotations



import json

import re

import unittest

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

HTML = ROOT / "insights-ny-minimum-staffing.html"





def _load_interactive(html: str) -> dict:

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

    raise AssertionError("interactive JSON not found")





def _curve_at(curve: list[dict], threshold: float) -> dict:

    return next(p for p in curve if abs(p["threshold"] - threshold) < 0.001)





class NyScenarioControlsTest(unittest.TestCase):

    @classmethod

    def setUpClass(cls) -> None:

        cls.html = HTML.read_text(encoding="utf-8")

        cls.interactive = _load_interactive(cls.html)



    def test_scenario_ui_markers_present(self) -> None:

        self.assertNotIn('id="ny-scenario-wrap"', self.html)

        self.assertNotIn('id="ny-scenario-panel"', self.html)

        self.assertIn('chart-pbj-toggle-dock', self.html)

        self.assertIn('chart-pbj-toggle-btn', self.html)

        self.assertIn('chart-pbj-toggle-panel', self.html)

        self.assertNotIn('id="pbj-standard-dock"', self.html)

        self.assertNotIn('id="pbj-standard-fab"', self.html)

        self.assertNotIn('id="pick-your-standard"', self.html)

        self.assertIn("PBJ Standard", self.html)

        self.assertNotIn('class="ny-scenario-config-btn"', self.html)

        self.assertIn('class="hprd-slider chart-hprd-slider"', self.html)

        self.assertIn('min="3"', self.html)

        self.assertIn('max="4.1"', self.html)

        self.assertIn('name="ny-metric-mode"', self.html)

        self.assertIn('data-scenario-scope="dow"', self.html)

        self.assertIn('data-scenario-scope="provider-days"', self.html)

        self.assertIn('data-scenario-scope="ownership"', self.html)

        self.assertIn('data-scenario-scope="geography"', self.html)

        self.assertIn('scenarioByScope', self.html)

        self.assertIn('activeInteractiveForScope', self.html)

        self.assertIn("Reset", self.html)

        self.assertIn('data-scenario-surface', self.html)

        self.assertNotIn('id="quarterly-pbj-toggle"', self.html)

        self.assertIn('report-standard-callout', self.html)

        self.assertIn('report-standard-callout-lead', self.html)

        self.assertIn('data-statute-modal-open="ny-standard-compliance"', self.html)

        self.assertIn('data-statute-modal-open="chart-definitions"', self.html)

        self.assertIn('report-standard-callout-links', self.html)

        self.assertIn('>NY state law</button>', self.html)

        self.assertIn('>report methodology</button>', self.html)

        self.assertNotIn('report-ref-btn', self.html)

        self.assertIn('chart-pbj-controls--daily', self.html)

        self.assertIn('pbj-standard-fixed', self.html)

        self.assertNotIn("Toggle HPRD threshold", self.html)

        self.assertNotIn('id="hprd-control"', self.html)



    def test_apply_threshold_skips_fixed_reference_tables(self) -> None:

        apply_fn = self.html.split("function applyThreshold(threshold, opts)")[1][:2200]

        self.assertNotIn("updateWtBreakdownRows", apply_fn)

        self.assertNotIn("PBJ320FacilitiesTable.applyThreshold", apply_fn)

        self.assertNotIn("updateDowChart(currentThreshold)", apply_fn)

        self.assertIn("scope === 'dow'", apply_fn)

        self.assertIn("scope === 'geography'", apply_fn)



    def test_default_regression_values(self) -> None:

        mode = self.interactive["modes"]["ny_mapped_non_admin_hprd"]

        all_pt = _curve_at(mode["curves"]["all_ny"], 3.5)

        wk_pt = _curve_at(mode["curves"]["weekend"], 3.5)

        nyc_wk = _curve_at(mode["curves"]["weekend_nyc"], 3.5)

        self.assertEqual(all_pt["below"], 123428)

        self.assertAlmostEqual(all_pt["pct_below"], 57.11, places=2)

        self.assertEqual(wk_pt["below"], 48302)

        self.assertAlmostEqual(wk_pt["pct_below"], 78.43, places=2)

        self.assertEqual(nyc_wk["below"], 14162)

        self.assertAlmostEqual(nyc_wk["pct_below"], 83.41, places=2)



        facilities = json.loads(

            re.search(r"window\.PBJ_REPORT_FACILITIES\s*=\s*(\{.*?\});", self.html, re.DOTALL).group(1)

        )

        idx = round((3.5 - facilities["threshold_start"]) / facilities["threshold_step"])

        counts = [0, 0]

        for fac in facilities["facilities"]:

            below = fac["below_curve"][idx]

            fd = fac["facility_days"]

            if fd and below >= fd:

                counts[0] += 1

            elif fd and 100 * below / fd >= 90:

                counts[1] += 1

        self.assertEqual(counts[0], 58)

        self.assertEqual(counts[0] + counts[1], 158)



    def test_threshold_4_updates_statewide_curve(self) -> None:

        mode = self.interactive["modes"]["ny_mapped_non_admin_hprd"]

        pt = _curve_at(mode["curves"]["all_ny"], 4.0)

        self.assertEqual(pt["below"], 177424)

        self.assertAlmostEqual(pt["pct_below"], 82.09, places=2)



    def test_broad_mode_differs_at_default_threshold(self) -> None:

        ny = _curve_at(self.interactive["modes"]["ny_mapped_non_admin_hprd"]["curves"]["all_ny"], 3.5)

        broad = _curve_at(self.interactive["modes"]["broad_pbj_total_hprd"]["curves"]["all_ny"], 3.5)

        self.assertNotEqual(ny["pct_below"], broad["pct_below"])

        self.assertAlmostEqual(broad["pct_below"], 47.09, places=2)



    def test_include_don_mode_has_full_curves(self) -> None:

        inc = self.interactive["modes"]["ny_mapped_include_don_sensitivity"]

        self.assertIn("curves_by_dow", inc)

        self.assertEqual(len(inc["curves_by_dow"]), 7)

        self.assertEqual(len(inc.get("curves_by_county") or {}), 60)

        pt = _curve_at(inc["curves"]["all_ny"], 3.5)

        self.assertAlmostEqual(pt["pct_below"], 54.45, places=2)



    def test_facilities_include_don_curve_field(self) -> None:

        self.assertIn("below_curve_include_don", self.html)

        self.assertIn("ny_mapped_include_don_sensitivity", self.html)

        self.assertIn("function curveFieldForMode", self.html)

        self.assertIn("below_curve_include_don", self.html.split("function curveFieldForMode")[1][:400])



    def test_narrative_lead_not_mutated_by_js(self) -> None:

        self.assertIn('id="provider-days-below-lead"', self.html)

        lead_block = self.html.split('id="provider-days-below-lead"')[1][:700]

        self.assertIn("3.50 HPRD", lead_block)

        self.assertIn("six in ten", lead_block)

        self.assertIn("one-quarter", lead_block)

        self.assertIn("one in seven", lead_block)

        update_fn = self.html.split("function updateProviderDaysBelowChart")[1][:2500]

        self.assertNotIn("provider-days-below-lead", update_fn)



    def test_scenario_controls_wired_in_init(self) -> None:

        self.assertIn("PBJ320ScenarioControls", self.html)

        self.assertIn("PBJ320ScenarioControls.init", self.html)



    def test_metric_radios_bound_after_dom_insert(self) -> None:

        block = self.html.split("function injectDailyChartControls")[1].split("function closePbjTogglePanel")[0]

        bind_pos = block.index("bindMetricRadios")

        insert_pos = block.index("insertBefore")

        self.assertGreater(bind_pos, insert_pos)



    def test_staff_mix_control_order(self) -> None:

        tpl = self.html.split('id="chart-daily-controls-tpl"')[1].split("</template>")[0]

        direct = tpl.index('value="ny_mapped_non_admin_hprd"')

        total = tpl.index('value="broad_pbj_total_hprd"')

        don = tpl.index('value="ny_mapped_include_don_sensitivity"')

        self.assertLess(direct, total)

        self.assertLess(total, don)

        self.assertIn("incl. Admin/DON", tpl)



    def test_threshold_above_staff_mix_in_panel(self) -> None:

        tpl = self.html.split('id="chart-daily-controls-tpl"')[1].split("</template>")[0]

        thresh = tpl.index("HPRD threshold")

        staff = tpl.index("Staff mix")

        self.assertLess(thresh, staff)



    def test_county_map_has_scenario_controls_host(self) -> None:

        block = self.html.split('id="county-map-title"')[0].split("county-map-wrap")[-1]

        self.assertIn("data-scenario-controls-host", block)





if __name__ == "__main__":

    unittest.main()

