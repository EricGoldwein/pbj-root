"""HTML injection helpers for audience signup assets."""

from __future__ import annotations

import html

from site_public_config import PBJ_AUDIENCE_JS_VERSION


def audience_assets_head() -> str:
    """Link audience CSS in document head."""
    return f'<link rel="stylesheet" href="/pbj-audience.css?v={PBJ_AUDIENCE_JS_VERSION}">'


def audience_assets_footer() -> str:
    """Load audience JS after pbj-site-universal.js."""
    return f'<script src="/pbj-audience.js?v={PBJ_AUDIENCE_JS_VERSION}" defer></script>'


def audience_provider_mount(facility_name: str = '') -> str:
    """Inline mount point for facility follow CTA."""
    if facility_name:
        name_attr = f' data-facility-name="{html.escape(facility_name, quote=True)}"'
    else:
        name_attr = ''
    return f'<div id="pbj-audience-provider"{name_attr}></div>'


def audience_state_mount() -> str:
    return '<div id="pbj-audience-state"></div>'
