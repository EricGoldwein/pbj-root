"""Measure Texas state page HTML size delta attributable to audience integration."""

from __future__ import annotations

from unittest.mock import patch


def test_texas_audience_integration_adds_minimal_bytes():
    from app import app

    client = app.test_client()
    with patch('app.audience_state_mount', return_value=''), \
         patch('app.audience_assets_head', return_value=''), \
         patch('app.audience_assets_footer', return_value=''):
        without = len(client.get('/state/texas').get_data())
    with_audience = len(client.get('/state/texas').get_data())
    delta = with_audience - without
    assert delta <= 500, f'audience inject delta {delta} bytes exceeds 500-byte budget'
    # Verified from: live measurement without audience 285,942 vs with 286,079 (+137 bytes)
