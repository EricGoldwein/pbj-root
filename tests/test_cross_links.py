"""Tests for PBJ320 cross-link helpers."""
from __future__ import annotations

import unittest

from pbj_cross_links import cross_links_for_entity, render_cross_links_html


class TestCrossLinks(unittest.TestCase):
    def test_entity_cross_links_with_sff(self) -> None:
        html = cross_links_for_entity(
            entity_id=123,
            top_states=[('Pennsylvania', 'pennsylvania'), ('West Virginia', 'west-virginia')],
            has_sff=True,
        )
        self.assertIn('Staffing rankings', html)
        self.assertIn('Pennsylvania', html)
        self.assertIn('West Virginia', html)
        self.assertIn('Special Focus Facilities', html)
        self.assertIn('href="/sff"', html)

    def test_entity_cross_links_without_sff(self) -> None:
        html = cross_links_for_entity(
            entity_id=123,
            top_states=[('Pennsylvania', 'pennsylvania')],
            has_sff=False,
        )
        self.assertNotIn('/sff', html)

    def test_render_max_four_links(self) -> None:
        links = [(f'Link {i}', f'/l{i}') for i in range(6)]
        html = render_cross_links_html(links)
        self.assertEqual(html.count('href='), 4)
