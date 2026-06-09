"""Quarterly LPN columns: state/national/region full + direct care, plus medians."""
from __future__ import annotations

import os
import sys
import unittest

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

LPN_COLS = ("LPN_HPRD", "LPN_Care_HPRD")
LPN_MEDIAN_COLS = ("LPN_HPRD_Median", "LPN_Care_HPRD_Median")


class TestQuarterlyLpnCoverage(unittest.TestCase):
    def test_state_quarterly_has_lpn_columns(self):
        path = os.path.join(REPO_ROOT, "state_quarterly_metrics.csv")
        self.assertTrue(os.path.isfile(path))
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        for col in LPN_COLS:
            self.assertIn(col, cols)
        for col in LPN_MEDIAN_COLS:
            self.assertIn(col, cols)

    def test_national_quarterly_has_lpn_columns(self):
        path = os.path.join(REPO_ROOT, "national_quarterly_metrics.csv")
        self.assertTrue(os.path.isfile(path))
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        for col in LPN_COLS:
            self.assertIn(col, cols)

    def test_region_quarterly_has_lpn_columns(self):
        path = os.path.join(REPO_ROOT, "cms_region_quarterly_metrics.csv")
        self.assertTrue(os.path.isfile(path))
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        for col in LPN_COLS:
            self.assertIn(col, cols)
        for col in LPN_MEDIAN_COLS:
            self.assertIn(col, cols)

    def test_fl_lpn_populated_for_recent_quarter(self):
        path = os.path.join(REPO_ROOT, "state_quarterly_metrics.csv")
        df = pd.read_csv(path, usecols=["STATE", "CY_Qtr", "LPN_HPRD", "LPN_Care_HPRD"])
        df["STATE"] = df["STATE"].astype(str).str.strip().str.upper()
        latest = str(df["CY_Qtr"].max())
        fl = df[(df["STATE"] == "FL") & (df["CY_Qtr"] == latest)]
        self.assertFalse(fl.empty, f"no FL row for {latest}")
        self.assertGreater(float(fl.iloc[0]["LPN_HPRD"]), 0.1)
        self.assertGreater(float(fl.iloc[0]["LPN_Care_HPRD"]), 0.05)

    def test_national_lpn_populated_for_recent_quarter(self):
        path = os.path.join(REPO_ROOT, "national_quarterly_metrics.csv")
        df = pd.read_csv(path, usecols=["CY_Qtr", "LPN_HPRD", "LPN_Care_HPRD"])
        latest = str(df["CY_Qtr"].max())
        row = df[df["CY_Qtr"] == latest]
        self.assertFalse(row.empty)
        self.assertGreater(float(row.iloc[0]["LPN_HPRD"]), 0.1)
        self.assertGreater(float(row.iloc[0]["LPN_Care_HPRD"]), 0.05)

    def test_get_state_historical_data_includes_lpn(self):
        from app import get_pd, get_state_historical_data

        self.assertIsNotNone(get_pd())
        data = get_state_historical_data("FL")
        self.assertIsNotNone(data)
        self.assertTrue(data.get("lpn"))
        self.assertTrue(any(v is not None for v in data["lpn"]))
        self.assertTrue(data.get("lpn_care"))
        self.assertTrue(any(v is not None for v in data["lpn_care"]))


if __name__ == "__main__":
    unittest.main()
