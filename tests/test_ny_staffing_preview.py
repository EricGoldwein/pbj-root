"""NY staffing report pre-publication preview (noindex, token gate)."""

import os
import unittest

from site_public_config import (
    inject_ny_staffing_report_preview,
    is_ny_staffing_report_preview_path,
    ny_staffing_report_preview_path,
    ny_staffing_report_preview_token,
)


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
            'Pre-publication preview: Shared ahead of Tuesday\u2019s public release. '
            'Data and wording may still be updated.',
            out,
        )
        self.assertIn('position: sticky', out)
        self.assertIn('0.9rem * 1.35', out)
        self.assertNotIn(':root {\n  --ny-preview-banner-offset: calc(0.65rem * 2 + 1.35em', out)

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


if __name__ == '__main__':
    unittest.main()
