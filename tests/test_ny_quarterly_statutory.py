"""Quarterly statutory-style workbook reconciliation tests."""

import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs"


class NyQuarterlyStatutoryTest(unittest.TestCase):
    def test_quarterly_workbook_reconciles(self):
        fq = pd.read_csv(CSV_DIR / "facility_quarter_summary.csv")
        fac = pd.read_csv(CSV_DIR / "facility_summary.csv")
        recon = pd.read_csv(CSV_DIR / "reconciliation_checks.csv")

        self.assertTrue(recon["passed"].all(), msg=recon.loc[~recon["passed"], "check"].tolist())
        self.assertLessEqual(int(fq.groupby("ccn")["quarter"].count().max()), 4)

        logic = (
            fq["missing_any_floor"]
            == (fq["below_350_total"] | fq["below_220_cna_side"] | fq["below_110_licensed"])
        ).all()
        self.assertTrue(logic)
        self.assertTrue((fq["met_all_three"] == ~fq["missing_any_floor"]).all())

        roll = fq.groupby("ccn", observed=True).agg(
            quarters_below_350_total=("below_350_total", "sum"),
            quarters_missing_any_floor=("missing_any_floor", "sum"),
        )
        chk = fac.merge(roll, on="ccn", suffixes=("_fac", "_calc"))
        self.assertTrue(
            (chk["quarters_below_350_total_fac"] == chk["quarters_below_350_total_calc"]).all()
        )
        self.assertTrue(
            (chk["quarters_missing_any_floor_fac"] == chk["quarters_missing_any_floor_calc"]).all()
        )

        if "qtrs_below_350_display" in fac.columns:
            for _, row in fac.iterrows():
                qa = int(row["quarters_analyzed"])
                qb = int(row["quarters_below_350_total"])
                expected = f"{qb}/{qa}"
                self.assertEqual(
                    row["qtrs_below_350_display"],
                    expected,
                    msg=f"ccn {row['ccn']}: {row['qtrs_below_350_display']} != {expected}",
                )
                self.assertEqual(
                    row["qtrs_missing_floor_display"],
                    f"{int(row['quarters_missing_any_floor'])}/{qa}",
                    msg=f"ccn {row['ccn']} missing floor display",
                )

    def test_denominator_uses_quarters_analyzed_not_four(self):
        fq = pd.read_csv(CSV_DIR / "facility_quarter_summary.csv")
        fac = pd.read_csv(CSV_DIR / "facility_summary.csv")
        self.assertEqual(len(fq), 2369)
        self.assertEqual(int(fac["quarters_analyzed"].sum()), 2369)

        partial = fac[fac["quarters_analyzed"] < 4]
        self.assertGreater(len(partial), 0, "expected partial-year facilities in audit sample")
        bad = partial[partial["qtrs_below_350_display"].astype(str).str.endswith("/4")]
        self.assertTrue(bad.empty, msg=bad[["ccn", "quarters_analyzed", "qtrs_below_350_display"]].to_dict())

    def test_four_quarters_below_means_four_analyzed(self):
        fac = pd.read_csv(CSV_DIR / "facility_summary.csv")
        at_four = fac[fac["quarters_below_350_total"] == 4]
        self.assertTrue((at_four["quarters_analyzed"] == 4).all())
        self.assertEqual(len(at_four), 284)

    def test_facilities_by_quarters_analyzed_distribution(self):
        fac = pd.read_csv(CSV_DIR / "facility_summary.csv")
        dist = fac["quarters_analyzed"].value_counts().sort_index().to_dict()
        self.assertEqual(dist.get(4, 0), 583)
        self.assertEqual(dist.get(3, 0), 11)
        self.assertEqual(dist.get(2, 0), 2)

    def test_verify_workbook_script_passes(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_ny_verification_workbook.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
