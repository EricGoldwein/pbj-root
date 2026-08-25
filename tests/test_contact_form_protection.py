"""Focused tests for PBJ320 contact / request form spam protections."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Configure before importing app / contact_protection store.
_TEST_DIR = tempfile.mkdtemp(prefix='pbj_contact_prot_')
os.environ['CONTACT_PROTECTION_DB_PATH'] = os.path.join(_TEST_DIR, 'contact_protection.db')
os.environ['TURNSTILE_SECRET_KEY'] = '1x0000000000000000000000000000000AA'
os.environ['TURNSTILE_SITE_KEY'] = '1x00000000000000000000AA'
os.environ['TURNSTILE_EXPECTED_HOSTNAMES'] = 'pbj320.com,www.pbj320.com,localhost'
os.environ.pop('PBJ_CONTACT_SKIP_TURNSTILE', None)
os.environ.pop('RENDER', None)
os.environ.pop('RENDER_SERVICE_ID', None)
os.environ['PBJ_ENV'] = 'test'
os.environ['SUBSCRIBE_NOTIFY_SMTP_HOST'] = 'smtp.test.local'
os.environ['SUBSCRIBE_NOTIFY_SMTP_PORT'] = '587'
os.environ['SUBSCRIBE_NOTIFY_SMTP_USER'] = 'user'
os.environ['SUBSCRIBE_NOTIFY_SMTP_PASSWORD'] = 'pass'
os.environ['SUBSCRIBE_NOTIFY_FROM'] = 'noreply@pbj320.com'
os.environ['SUBSCRIBE_NOTIFY_TO'] = 'ops@pbj320.com'
os.environ['WTF_CSRF_ENABLED'] = '0'
os.environ.setdefault('SECRET_KEY', 'test-contact-protection-secret')

from contact_protection import (  # noqa: E402
    TURNSTILE_TEST_SECRET_PASS,
    build_contact_email_parts,
    process_contact_submission,
    reset_store_for_tests,
    score_submission,
)
from contact_protection.store import set_store_path_for_tests  # noqa: E402
from contact_protection.turnstile import set_siteverify_post_for_tests  # noqa: E402


def _ok_siteverify(_url, data=None, timeout=None):
    resp = MagicMock()
    resp.json.return_value = {
        'success': True,
        'hostname': 'www.pbj320.com',
        'action': 'pbj_request',
    }
    return resp


def _fail_siteverify(_url, data=None, timeout=None):
    resp = MagicMock()
    resp.json.return_value = {
        'success': False,
        'error-codes': ['invalid-input-response'],
    }
    return resp


def _bad_action_siteverify(_url, data=None, timeout=None):
    resp = MagicMock()
    resp.json.return_value = {
        'success': True,
        'hostname': 'www.pbj320.com',
        'action': 'wrong_action',
    }
    return resp


def _bad_host_siteverify(_url, data=None, timeout=None):
    resp = MagicMock()
    resp.json.return_value = {
        'success': True,
        'hostname': 'evil.example',
        'action': 'pbj_request',
    }
    return resp


def _network_error_siteverify(_url, data=None, timeout=None):
    raise ConnectionError('cloudflare unreachable')


VALID_MESSAGE = (
    'Hello — I am researching staffing at a New York facility and would like '
    'background context for a story.'
)


def _form(**overrides):
    base = {
        'name': 'Alex Reporter',
        'email': 'alex.reporter@example.com',
        'message': VALID_MESSAGE,
        'press': '',
        'company_website': '',
        'csrf_token': 'test',
        'next': '/contact',
    }
    base.update(overrides)
    return base


class ContactProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        path = os.path.join(_TEST_DIR, f't_{self.id().split(".")[-1]}.db')
        set_store_path_for_tests(path)
        reset_store_for_tests()
        set_siteverify_post_for_tests(_ok_siteverify)
        os.environ['TURNSTILE_SECRET_KEY'] = TURNSTILE_TEST_SECRET_PASS
        # Use unique tokens per test by default.
        self.token = f'token-{self.id()}'

    def tearDown(self) -> None:
        set_siteverify_post_for_tests(None)

    def _decide(self, form=None, token=None, content_length=None, ip='203.0.113.10'):
        return process_contact_submission(
            form=form or _form(),
            content_type='application/x-www-form-urlencoded',
            content_length=content_length,
            client_ip=ip,
            turnstile_token=token if token is not None else self.token,
        )

    def test_valid_submission_accepts(self):
        d = self._decide()
        self.assertEqual(d.outcome, 'accept')
        self.assertEqual(d.reason, 'accepted')
        self.assertIsNotNone(d.validated)

    def test_media_yes_valid_still_works(self):
        d = self._decide(_form(press='yes'))
        self.assertEqual(d.outcome, 'accept')
        self.assertTrue(d.validated.is_press)

    def test_media_yes_does_not_bypass_validation(self):
        d = self._decide(_form(press='yes', message='short'))
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'validation_failed')

    def test_honeypot_soft_drops_no_accept(self):
        d = self._decide(_form(company_website='http://spam.example'))
        self.assertEqual(d.outcome, 'soft_drop')
        self.assertEqual(d.reason, 'honeypot_filled')

    def test_missing_turnstile_token(self):
        d = self._decide(token='')
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'turnstile_failed')

    def test_invalid_turnstile_token(self):
        set_siteverify_post_for_tests(_fail_siteverify)
        d = self._decide(token='bad-token')
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'turnstile_failed')

    def test_wrong_action(self):
        # Production-like secret so action is enforced (not Cloudflare test secret).
        os.environ['TURNSTILE_SECRET_KEY'] = '0x' + ('a' * 32)
        set_siteverify_post_for_tests(_bad_action_siteverify)
        d = self._decide(token='tok-action')
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'turnstile_failed')

    def test_wrong_hostname(self):
        os.environ['TURNSTILE_SECRET_KEY'] = '0x' + ('b' * 32)
        set_siteverify_post_for_tests(_bad_host_siteverify)
        d = self._decide(token='tok-host')
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'turnstile_failed')

    def test_reused_token(self):
        d1 = self._decide(token='reuse-me')
        self.assertEqual(d1.outcome, 'accept')
        d2 = self._decide(
            form=_form(email='other@example.com', message=VALID_MESSAGE + ' follow-up note.'),
            token='reuse-me',
            ip='203.0.113.11',
        )
        self.assertEqual(d2.outcome, 'reject')
        self.assertEqual(d2.reason, 'turnstile_failed')

    def test_rate_limited(self):
        for i in range(3):
            d = self._decide(
                form=_form(email=f'u{i}@example.com', message=VALID_MESSAGE + f' case {i}.'),
                token=f'rate-tok-{i}',
                ip='198.51.100.9',
            )
            self.assertEqual(d.outcome, 'accept', msg=d.reason)
        d4 = self._decide(
            form=_form(email='u9@example.com', message=VALID_MESSAGE + ' case overflow.'),
            token='rate-tok-overflow',
            ip='198.51.100.9',
        )
        self.assertEqual(d4.outcome, 'rate_limited')

    def test_header_injection_rejected(self):
        d = self._decide(_form(name='Evil\r\nBcc: spam@example.com'))
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'validation_failed')

    def test_oversized_body_rejected(self):
        d = self._decide(content_length=200_000)
        self.assertEqual(d.outcome, 'reject')
        self.assertEqual(d.reason, 'validation_failed')

    def test_one_ordinary_url_allowed(self):
        msg = (
            'Please look at https://www.pbj320.com/provider/015009 for context on this '
            'facility staffing trend. Happy to hop on a call.'
        )
        assessment = score_submission(name='Jane Doe', message=msg, is_press=True)
        self.assertFalse(assessment.high_confidence)
        d = self._decide(_form(name='Jane Doe', message=msg, press='yes'))
        self.assertEqual(d.outcome, 'accept')

    def test_seo_solicitation_suppressed(self):
        # Fixtures use example.invalid — no live promotional domains.
        msg = (
            'Dear webmaster, we can increase your Google ranking and boost your SEO '
            'with cheap guest posts and link building. Visit https://seo.example.invalid/offer '
            'and https://links.example.invalid/buy for packages.'
        )
        assessment = score_submission(name='SeoBot', message=msg)
        self.assertTrue(assessment.high_confidence)
        self.assertIn('seo_solicitation', assessment.reasons)
        d = self._decide(_form(name='SeoBot', email='seo@example.invalid', message=msg, press='yes'))
        self.assertEqual(d.outcome, 'soft_drop')
        self.assertEqual(d.reason, 'high_confidence_spam')

    def test_xevil_captcha_ad_suppressed(self):
        msg = (
            'XEvil captcha solver and 2captcha service — bypass captcha and turnstile solver '
            'available. Try https://solver.example.invalid/xevil and https://solver.example.invalid/api '
            'plus https://solver.example.invalid/pricing today.'
        )
        assessment = score_submission(name='x9k2mqpz', message=msg)
        self.assertTrue(assessment.high_confidence)
        self.assertIn('captcha_solver_ad', assessment.reasons)
        d = self._decide(_form(name='x9k2mqpz', email='bot@example.invalid', message=msg))
        self.assertEqual(d.outcome, 'soft_drop')
        self.assertEqual(d.reason, 'high_confidence_spam')

    def test_html_escaped_in_email(self):
        subject, plain, html = build_contact_email_parts(
            sender_name='<script>alert(1)</script>',
            sender_email='a@example.com',
            message_body='Hello <b>there</b> & friends',
            is_press=False,
        )
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;b&gt;there&lt;/b&gt;', html)
        self.assertIn('&amp;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('<script>alert(1)</script>', plain)
        self.assertNotIn('\r', subject)
        self.assertNotIn('\n', subject)

    def test_turnstile_network_error_retryable(self):
        set_siteverify_post_for_tests(_network_error_siteverify)
        d = self._decide(token='net-fail-token')
        self.assertEqual(d.outcome, 'retry')
        self.assertTrue(d.reason.startswith('turnstile'))

    def test_no_live_cloudflare_required(self):
        """Siteverify is mocked; Cloudflare test secret is used — no live credentials."""
        self.assertEqual(os.environ['TURNSTILE_SECRET_KEY'], TURNSTILE_TEST_SECRET_PASS)
        set_siteverify_post_for_tests(_ok_siteverify)
        d = self._decide()
        self.assertEqual(d.outcome, 'accept')


class ContactEmailGateTests(unittest.TestCase):
    """Route contract without importing app.py (avoids heavy pandas boot in this env)."""

    def setUp(self) -> None:
        path = os.path.join(_TEST_DIR, f'gate_{self.id().split(".")[-1]}.db')
        set_store_path_for_tests(path)
        reset_store_for_tests()
        set_siteverify_post_for_tests(_ok_siteverify)
        os.environ['TURNSTILE_SECRET_KEY'] = TURNSTILE_TEST_SECRET_PASS

    def tearDown(self) -> None:
        set_siteverify_post_for_tests(None)

    @staticmethod
    def _would_send(decision) -> bool:
        # Mirrors app.contact(): only outcome == accept sends email.
        return decision.outcome == 'accept'

    def test_valid_submission_sends_exactly_one_email(self):
        decision = process_contact_submission(
            form=_form(),
            content_type='application/x-www-form-urlencoded',
            content_length=None,
            client_ip='203.0.113.50',
            turnstile_token='gate-ok-1',
        )
        sends = [1] if self._would_send(decision) else []
        self.assertEqual(decision.outcome, 'accept')
        self.assertEqual(len(sends), 1)
        _subject, plain, html = build_contact_email_parts(
            sender_name=decision.validated.name,
            sender_email=decision.validated.email,
            message_body=decision.validated.message,
            is_press=decision.validated.is_press,
        )
        self.assertIn('Name:', plain)
        self.assertIn('<strong>Name:</strong>', html)

    def test_honeypot_sends_no_email(self):
        decision = process_contact_submission(
            form=_form(company_website='http://bot.example'),
            content_type='application/x-www-form-urlencoded',
            content_length=None,
            client_ip='203.0.113.51',
            turnstile_token='gate-hp',
        )
        self.assertEqual(decision.outcome, 'soft_drop')
        self.assertFalse(self._would_send(decision))

    def test_rate_limited_sends_no_email(self):
        for i in range(3):
            d = process_contact_submission(
                form=_form(email=f'g{i}@example.com', message=VALID_MESSAGE + f' g{i}'),
                content_type='application/x-www-form-urlencoded',
                content_length=None,
                client_ip='198.51.100.77',
                turnstile_token=f'gate-rl-{i}',
            )
            self.assertEqual(d.outcome, 'accept')
        d4 = process_contact_submission(
            form=_form(email='g9@example.com', message=VALID_MESSAGE + ' overflow'),
            content_type='application/x-www-form-urlencoded',
            content_length=None,
            client_ip='198.51.100.77',
            turnstile_token='gate-rl-overflow',
        )
        self.assertEqual(d4.outcome, 'rate_limited')
        self.assertFalse(self._would_send(d4))

    def test_production_bypass_impossible(self):
        from contact_protection.config import turnstile_required

        with patch.dict(
            os.environ,
            {
                'RENDER': 'true',
                'PBJ_CONTACT_SKIP_TURNSTILE': '1',
                'TURNSTILE_SECRET_KEY': TURNSTILE_TEST_SECRET_PASS,
            },
            clear=False,
        ):
            self.assertTrue(turnstile_required())


if __name__ == '__main__':
    unittest.main()
