"""NY staffing report pre-publication preview (noindex, token gate)."""

import os
import unittest
from pathlib import Path

from app import app
from site_public_config import (
    GOOGLE_ANALYTICS_MEASUREMENT_ID,
    NY_PREVIEW_DEFINITIONS_HEADING,
    inject_google_analytics_head,
    inject_ny_staffing_report_preview,
    is_ny_staffing_report_preview_path,
    ny_staffing_report_preview_path,
    ny_staffing_report_preview_redirect_to_public,
    ny_staffing_report_preview_token,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = ROOT / "insights-ny-minimum-staffing.html"


class NyStaffingPreviewTest(unittest.TestCase):
    def test_preview_path_requires_token(self):
        self.assertEqual(
            ny_staffing_report_preview_path(),
            f'/preview/ny-staffing-compliance-2025/{ny_staffing_report_preview_token()}',
        )

    def test_preview_path_detection(self):
        tok = ny_staffing_report_preview_token()
        self.assertTrue(is_ny_staffing_report_preview_path(f'/preview/ny-staffing-compliance-2025/{tok}'))
        self.assertFalse(is_ny_staffing_report_preview_path('/insights/ny-minimum-staffing'))

    def test_inject_adds_noindex_and_banner(self):
        html = (
            '<html><head><meta name="viewport" content="width=device-width"></head>'
            '<body class="x"><main></main></body></html>'
        )
        preview_path = '/preview/ny-staffing-compliance-2025/testtok'
        out = inject_ny_staffing_report_preview(html, preview_path)
        self.assertIn('noindex, nofollow', out)
        self.assertIn('class="ny-staffing-preview-banner"', out)
        self.assertIn('ny-staffing-preview-chrome', out)
        self.assertIn(
            'Preview report. May be updated before publication.',
            out,
        )
        self.assertIn('position: sticky', out)
        self.assertIn('0.9rem * 1.35', out)
        self.assertNotIn(':root {\n  --ny-preview-banner-offset: calc(0.65rem * 2 + 1.35em', out)

    def test_inject_wraps_site_header_and_progress_in_preview_chrome(self):
        html = REPORT_HTML.read_text(encoding='utf-8')
        out = inject_ny_staffing_report_preview(
            html,
            '/preview/ny-staffing-compliance-2025/testtok',
        )
        self.assertIn('class="report-site-header"', out)
        self.assertIn(
            'class="ny-staffing-preview-chrome">'
            '<div class="ny-staffing-preview-banner"',
            out,
        )
        self.assertIn(
            'report-mobile-jump-progress-fill"></span></div>\n</div>\n\n</div><header class="hero"',
            out,
        )

    def test_inject_replaces_definitions_heading_only_on_preview(self):
        html = REPORT_HTML.read_text(encoding="utf-8")
        self.assertIn('id="definitions-heading"', html)
        self.assertNotIn(NY_PREVIEW_DEFINITIONS_HEADING, html)
        out = inject_ny_staffing_report_preview(
            html,
            '/preview/ny-staffing-compliance-2025/testtok',
        )
        self.assertIn(
            f'<h2 id="definitions-heading">{NY_PREVIEW_DEFINITIONS_HEADING}</h2>',
            out,
        )
        self.assertIn(
            'New York nursing homes reported staffing below the 3.50 HPRD standard on',
            out,
        )

    def test_custom_token_from_env(self):
        prev = os.environ.get('NY_STAFFING_REPORT_PREVIEW_TOKEN')
        try:
            os.environ['NY_STAFFING_REPORT_PREVIEW_TOKEN'] = 'MyToken9'
            self.assertEqual(ny_staffing_report_preview_token(), 'mytoken9')
        finally:
            if prev is None:
                os.environ.pop('NY_STAFFING_REPORT_PREVIEW_TOKEN', None)
            else:
                os.environ['NY_STAFFING_REPORT_PREVIEW_TOKEN'] = prev

    def test_preview_redirects_to_public_by_default(self):
        prev = os.environ.pop('NY_STAFFING_REPORT_PREVIEW_REDIRECT', None)
        try:
            self.assertTrue(ny_staffing_report_preview_redirect_to_public())
        finally:
            if prev is not None:
                os.environ['NY_STAFFING_REPORT_PREVIEW_REDIRECT'] = prev

    def test_preview_redirect_can_be_disabled(self):
        prev = os.environ.get('NY_STAFFING_REPORT_PREVIEW_REDIRECT')
        try:
            os.environ['NY_STAFFING_REPORT_PREVIEW_REDIRECT'] = 'false'
            self.assertFalse(ny_staffing_report_preview_redirect_to_public())
        finally:
            if prev is None:
                os.environ.pop('NY_STAFFING_REPORT_PREVIEW_REDIRECT', None)
            else:
                os.environ['NY_STAFFING_REPORT_PREVIEW_REDIRECT'] = prev

    def test_inject_google_analytics_once(self):
        html = '<html><head><title>x</title></head><body></body></html>'
        out = inject_google_analytics_head(html)
        self.assertIn(GOOGLE_ANALYTICS_MEASUREMENT_ID, out)
        self.assertEqual(out, inject_google_analytics_head(out))

    def test_report_editorial_copy_updates(self):
        html = REPORT_HTML.read_text(encoding='utf-8')
        self.assertIn('chart-title-short">% days &lt; std</span></div>', html)
        self.assertIn('Any given Sunday: four in five were below 3.50 HPRD', html)
        self.assertIn('Use the', html)
        self.assertIn('controls on the charts to see how compliance changes', html)
        self.assertIn('Staffing below 3.50 HPRD was far more common on weekends', html)
        self.assertIn('For many homes, sub-3.50 staffing was routine', html)

    def test_report_section_nav_breakpoints(self):
        html = REPORT_HTML.read_text(encoding='utf-8')
        self.assertIn('@media (min-width: 1404px)', html)
        self.assertIn('@media (min-width: 769px) and (max-width: 1403px)', html)
        self.assertIn('.report-body-layout > .report-mobile-jump {\n    display: block;', html)

    def test_mobile_pbj_panel_threshold_grid(self):
        html = REPORT_HTML.read_text(encoding='utf-8')
        self.assertIn('.chart-pbj-controls--in-panel .chart-pbj-threshold-label {\n    display: none;', html)
        self.assertIn('.chart-pbj-controls--in-panel .ny-scenario-threshold-row {\n    display: flex;', html)
        self.assertIn('content: " HPRD threshold";', html)
        self.assertIn('.chart-pbj-toggle-panel {\n    left: 0;\n    right: 0;', html)
        self.assertIn('.chart-pbj-controls--in-panel .ny-scenario-modes--row.chart-pbj-modes', html)
        self.assertIn('.ny-scenario-modes--row:not(.chart-pbj-modes)', html)

    def test_report_and_insights_hub_include_ga(self):
        client = app.test_client()
        report = client.get('/insights/ny-minimum-staffing')
        self.assertEqual(report.status_code, 200)
        self.assertIn(GOOGLE_ANALYTICS_MEASUREMENT_ID, report.get_data(as_text=True))
        hub = client.get('/insights')
        self.assertEqual(hub.status_code, 200)
        self.assertIn(GOOGLE_ANALYTICS_MEASUREMENT_ID, hub.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
