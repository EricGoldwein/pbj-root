"""State high-risk table metric trend sparklines."""
from __future__ import annotations

import unittest


class StateHrMetricTrendTests(unittest.TestCase):
    def test_latest_n_cy_qtrs_rolls_with_anchor(self) -> None:
        from app import _latest_n_cy_qtrs

        self.assertEqual(
            _latest_n_cy_qtrs("2025Q4"),
            ["2025Q1", "2025Q2", "2025Q3", "2025Q4"],
        )
        self.assertEqual(
            _latest_n_cy_qtrs("2026Q1"),
            ["2025Q2", "2025Q3", "2025Q4", "2026Q1"],
        )

    def test_metric_trend_cell_requires_four_points(self) -> None:
        from app import _state_hr_metric_trend_cell_html

        plain = _state_hr_metric_trend_cell_html("426", [400, 410, None, 426], kind="census")
        self.assertIn("state-hr-metric-cell--plain", plain)
        self.assertNotIn("<svg", plain)

    def test_flat_series_renders_four_points(self) -> None:
        from app import _state_hr_metric_trend_cell_html, _state_hr_trend_spark_svg

        svg = _state_hr_trend_spark_svg([3.01, 3.01, 3.01, 3.01], kind="hprd")
        self.assertEqual(svg.count("<circle"), 4)
        self.assertIn("<polyline", svg)
        rich = _state_hr_metric_trend_cell_html("3.01", [3.0, 3.01, 3.01, 3.01], kind="hprd")
        self.assertIn("state-hr-trend-spark--hprd", rich)
        self.assertEqual(rich.count("<circle"), 4)

    def test_spark_dimensions(self) -> None:
        from app import _STATE_HR_TREND_SPARK_H, _STATE_HR_TREND_SPARK_W, _state_hr_trend_spark_svg

        svg = _state_hr_trend_spark_svg([1, 2, 3, 4], kind="census")
        self.assertIn(f'width="{_STATE_HR_TREND_SPARK_W}"', svg)
        self.assertIn(f'height="{_STATE_HR_TREND_SPARK_H}"', svg)


if __name__ == "__main__":
    unittest.main()
