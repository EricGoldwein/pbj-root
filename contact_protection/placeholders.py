"""HTML placeholders / widget snippets for contact forms."""

from __future__ import annotations

from contact_protection.config import TURNSTILE_ACTION, turnstile_site_key

TURNSTILE_SITE_KEY_PLACEHOLDER = '__TURNSTILE_SITE_KEY_PLACEHOLDER__'


def honeypot_field_html(*, field_id: str) -> str:
    # Visually offscreen text input; not type=hidden. Neutral name bots often fill.
    return (
        f'<div class="pbj-contact-hp" aria-hidden="true" '
        f'style="position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden;">'
        f'<label for="{field_id}">Website</label>'
        f'<input type="text" id="{field_id}" name="website_url" value="" '
        f'tabindex="-1" autocomplete="off">'
        f'</div>'
    )


def turnstile_widget_html(*, widget_id: str = '') -> str:
    id_attr = f' id="{widget_id}"' if widget_id else ''
    return (
        f'<div class="cf-turnstile" data-sitekey="{TURNSTILE_SITE_KEY_PLACEHOLDER}" '
        f'data-action="{TURNSTILE_ACTION}" data-appearance="interaction-only"'
        f'{id_attr}></div>'
    )


def turnstile_script_tags() -> str:
    return (
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
        '<script src="/contact-form-protect.js" defer></script>'
    )


def inject_contact_protection_html(html_content: str) -> str:
    """Replace Turnstile site-key placeholder in served HTML."""
    if TURNSTILE_SITE_KEY_PLACEHOLDER not in html_content:
        return html_content
    key = turnstile_site_key()
    return html_content.replace(TURNSTILE_SITE_KEY_PLACEHOLDER, key)
