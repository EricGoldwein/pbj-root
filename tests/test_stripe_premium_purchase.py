"""Tests for provider-page compact Premium CTA (Stripe Payment Link)."""
from __future__ import annotations

import unittest

from app import (
    _premium_request_facility_short_name,
    _render_facility_premium_cta,
    _stripe_premium_payment_link_url,
    _valid_stripe_premium_ccn,
    render_custom_report_cta,
)


class TestStripePremiumPurchase(unittest.TestCase):
    def test_valid_stripe_premium_ccn(self) -> None:
        self.assertEqual(_valid_stripe_premium_ccn('335513'), '335513')
        self.assertEqual(_valid_stripe_premium_ccn('  015009  '), '015009')
        self.assertEqual(_valid_stripe_premium_ccn(335513), '335513')

    def test_invalid_stripe_premium_ccn(self) -> None:
        self.assertEqual(_valid_stripe_premium_ccn(''), '')
        self.assertEqual(_valid_stripe_premium_ccn(None), '')
        self.assertEqual(_valid_stripe_premium_ccn('33551'), '')
        self.assertEqual(_valid_stripe_premium_ccn('3355133'), '')
        self.assertEqual(_valid_stripe_premium_ccn('O15009'), '')
        self.assertEqual(_valid_stripe_premium_ccn('15009'), '')

    def test_payment_link_url(self) -> None:
        url = _stripe_premium_payment_link_url('335513')
        self.assertEqual(
            url,
            'https://buy.stripe.com/eVq7sE8KUaFrevvgLU7N600?client_reference_id=ccn_335513',
        )
        self.assertEqual(_stripe_premium_payment_link_url('O50009'), '')

    def test_premium_request_facility_short_name_seagate(self) -> None:
        short = _premium_request_facility_short_name(
            'Seagate Rehabilitation and Nursing Center'
        )
        self.assertEqual(short, 'Seagate Rehabilitation')

    def test_premium_request_facility_short_name_compact_cms_name(self) -> None:
        short = _premium_request_facility_short_name('Golden Gate Rehabilitation')
        self.assertEqual(short, 'Golden Gate Rehabilitation')

    def test_facility_cta_renders_borderless_premium_bridge(self) -> None:
        html = _render_facility_premium_cta(
            '335513',
            'Seagate Rehabilitation and Nursing Center',
        )
        self.assertIn('pbj-provider-premium-bridge', html)
        self.assertNotIn('pbj-provider-premium-band', html)
        self.assertNotIn('pbj-provider-premium-bridge__actions', html)
        self.assertNotIn('pbj-provider-premium-bridge__sep', html)
        self.assertIn('pbj-provider-premium-bridge__premium', html)
        self.assertIn('pbj-provider-premium-bridge__premium-title', html)
        self.assertNotIn('pbj-provider-premium-cta', html)
        self.assertNotIn('pbj-page-bottom-details', html)
        self.assertIn('PBJ320 Premium', html)
        self.assertIn('Daily PBJ, acuity analysis, employee detail, ownership', html)
        self.assertNotIn('Daily staffing, acuity analysis, ownership, employee-level detail', html)
        self.assertIn('href="/premium"', html)
        self.assertIn('/pbj_favicon.png', html)
        self.assertIn('data-pbj-premium-bridge="4"', html)
        self.assertIn('pbj-provider-premium-bridge__stack', html)
        self.assertIn('pbj-provider-premium-bridge__glyph', html)
        self.assertIn('pbj-provider-premium-bridge__unlock', html)
        self.assertIn(
            'Request PBJ320 Dashboard for Seagate Rehabilitation and Nursing Center',
            html,
        )
        self.assertIn('Request Seagate PBJ320 Dashboard', html)
        self.assertEqual(html.count('class="pbj-provider-premium-bridge__request"'), 1)
        self.assertNotIn('pbj-provider-premium-bridge__request--desktop', html)
        self.assertNotIn('pbj-provider-premium-bridge__request--mobile', html)
        self.assertNotIn('pbj-provider-premium-bridge__request-row', html)
        self.assertNotIn('Request dashboard for', html)
        self.assertNotIn('Request dashboard \u2192', html)
        self.assertNotRegex(html, r'Seagate Rehab(?!ilitation)')
        request_html = html.split('class="pbj-provider-premium-bridge__request">', 1)[1]
        self.assertEqual(request_html.count('\u2192'), 0)
        self.assertNotIn('$320', html)
        self.assertNotIn('Dive deeper', html)
        self.assertNotIn('Want a closer look', html)
        self.assertNotIn('What\u2019s included', html)
        self.assertIn(
            'href="https://buy.stripe.com/eVq7sE8KUaFrevvgLU7N600?client_reference_id=ccn_335513"',
            html,
        )
        self.assertNotIn('stripe-buy-button', html)
        self.assertNotIn('buy-button.js', html)

    def test_facility_cta_request_dashboard_fallback_without_short_name(self) -> None:
        html = _render_facility_premium_cta('335513', 'NH')
        self.assertIn('Request PBJ320 Dashboard</a>', html)
        self.assertNotIn('Request dashboard', html)

    def test_facility_cta_falls_back_without_valid_ccn(self) -> None:
        html = render_custom_report_cta(
            'facility',
            'https://pbj320.com/provider/O50009',
            facility_name='Example Facility',
            ccn='O50009',
        )
        self.assertNotIn('buy.stripe.com', html)
        self.assertIn('custom-report-cta', html)
        self.assertIn('Request PBJ320 Premium Dashboard', html)

    def test_state_cta_does_not_render_stripe_checkout_link(self) -> None:
        html = render_custom_report_cta(
            'state',
            'https://pbj320.com/state/new-york',
            state_name='New York',
        )
        self.assertNotIn('buy.stripe.com', html)
        self.assertIn('custom-report-cta', html)


if __name__ == '__main__':
    unittest.main()
