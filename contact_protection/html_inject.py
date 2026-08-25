"""HTML snippets and placeholder injection for contact forms."""

from __future__ import annotations

from contact_protection.config import HONEYPOT_FIELD, TURNSTILE_ACTION, public_site_key

TURNSTILE_SITE_KEY_PLACEHOLDER = '__TURNSTILE_SITE_KEY_PLACEHOLDER__'
CONTACT_PROTECT_JS_VERSION = '1'


def honeypot_field_html(*, field_id: str) -> str:
    """Accessibility-safe honeypot: offscreen text input, not type=hidden."""
    return (
        f'<div class="pbj-hp-field" aria-hidden="true" '
        f'style="position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden;">'
        f'<label for="{field_id}">Company website</label>'
        f'<input type="text" name="{HONEYPOT_FIELD}" id="{field_id}" value="" '
        f'tabindex="-1" autocomplete="off">'
        f'</div>'
    )


def turnstile_widget_html(*, widget_id: str | None = None) -> str:
    attrs = [
        'class="cf-turnstile pbj-turnstile"',
        f'data-sitekey="{TURNSTILE_SITE_KEY_PLACEHOLDER}"',
        f'data-action="{TURNSTILE_ACTION}"',
        'data-appearance="interaction-only"',
    ]
    if widget_id:
        attrs.append(f'id="{widget_id}"')
    return f'<div {" ".join(attrs)}></div>'


def contact_protect_assets_html() -> str:
    """Script tags for Turnstile API + shared form protect JS (load once per page)."""
    return (
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>\n'
        f'<script src="/contact-form-protect.js?v={CONTACT_PROTECT_JS_VERSION}" defer></script>'
    )


def inject_contact_form_tokens(html: str) -> str:
    """Replace Turnstile site-key placeholder. Safe when key is empty (widget inert)."""
    key = public_site_key()
    return html.replace(TURNSTILE_SITE_KEY_PLACEHOLDER, key)
