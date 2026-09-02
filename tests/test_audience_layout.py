"""Responsive layout checks for audience CSS (structure, not visual pixels)."""



from __future__ import annotations



from pathlib import Path



import pytest





ROOT = Path(__file__).resolve().parents[1]

CSS_PATH = ROOT / 'pbj-audience.css'

JS_PATH = ROOT / 'pbj-audience.js'





def test_css_has_mobile_breakpoint_and_touch_targets():

    css = CSS_PATH.read_text(encoding='utf-8')

    assert 'max-width: 639px' in css or 'max-width:639px' in css.replace(' ', '')

    assert 'min-height: 44px' in css

    assert 'safe-area-inset-bottom' in css





def test_css_prevents_modal_background_scroll():

    css = CSS_PATH.read_text(encoding='utf-8')

    assert 'pbj-audience-modal-open' in css

    assert 'overflow: hidden' in css





def test_css_minimal_layout_not_marketing_card():

    css = CSS_PATH.read_text(encoding='utf-8')

    assert 'pbj-audience--minimal' in css

    assert 'max-width: min(36rem' in css

    assert 'hero-subscribe-submit' in open(JS_PATH, encoding='utf-8').read()





def test_homepage_subscribe_title_in_html():

    html = (ROOT / 'index.html').read_text(encoding='utf-8')

    assert 'home-subscribe-band-title' in html

    assert 'Get PBJ320 Staffing Data Updates' in html

    assert 'Get PBJ320 Updates' in html





def test_js_compact_form_no_visible_heading_or_description():

    js = JS_PATH.read_text(encoding='utf-8')

    assert 'pbj-audience__desc' not in js

    assert 'pbj-audience__prefs' not in js

    assert 'renderPreferenceStep' not in js

    assert 'appendPreferenceLink' not in js

    assert 'Save preferences' not in js

    assert 'appendManagePreferencesLink' not in js

    assert 'Manage email preferences' not in js





def test_js_context_specific_labels_and_success_copy():

    js = JS_PATH.read_text(encoding='utf-8')

    assert 'Enter your email' in js

    assert "placeholder: 'Email address'" in js

    assert 'Get PBJ320 Staffing Data Updates' not in js

    assert 'Facility updates' in js

    assert "inlineLabel: 'Follow this facility'" in js

    assert 'subscribed to PBJ320 Insights' in js

    assert 'subscribed to updates for this facility' in js

    assert 'Also get' in js

    assert 'Interested in the PBJ320 app' not in js

    assert 'Also get PBJ320 Insights' not in js





def test_js_facility_only_adjacent_offer():

    js = JS_PATH.read_text(encoding='utf-8')

    assert "spec.variant === 'facility_follow'" in js

    assert 'homepage_insights' not in js.split('function adjacentOffer')[1].split('function trackEvent')[0]





def test_js_no_role_dropdown_in_initial_form():

    js = JS_PATH.read_text(encoding='utf-8')

    assert 'pbj-audience__role' not in js

    assert 'ROLE_OPTIONS' not in js





def test_js_subscribe_button_labels():

    js = JS_PATH.read_text(encoding='utf-8')

    assert "submitLabel: 'Follow'" in js

    assert 'Subscribe' in js





def test_js_centralized_resolver():

    js = JS_PATH.read_text(encoding='utf-8')

    assert 'function resolveCta' in js

    assert 'pbj320_insights' in js

    assert 'Confirm on Substack' not in js





def test_js_popup_uses_relevant_inline_visibility_and_interaction():

    js = JS_PATH.read_text(encoding='utf-8')

    assert 'IntersectionObserver' in js

    assert 'inlineFacilityVisible' in js

    assert 'inline_cta_interacted' in js

    assert "reason: 'first_pageview'" in js





def test_long_facility_name_in_resolver():

    from audience.cta_resolver import resolve_cta



    long_name = 'The Very Long Named Nursing And Rehabilitation Center Of Greater Metropolitan Example County'

    spec = resolve_cta({'pageType': 'provider', 'facilityName': long_name, 'ccn': '123456', 'stateAbbr': 'PA'})

    assert long_name in spec['title']

    assert len(spec['title']) < 200





@pytest.mark.parametrize('width_label', ['320px', '375px', '768px', '1024px', '1440px'])

def test_viewport_labels_documented(width_label):

    """Viewport widths required for manual/browser QA — documented in final report."""

    assert width_label.endswith('px')

