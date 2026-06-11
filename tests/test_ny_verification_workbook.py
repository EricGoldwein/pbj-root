"""NY 2025 verification workbook package tests."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NyVerificationWorkbookDocsTest(unittest.TestCase):
    def test_readme_and_data_dictionary_doc_formulas_are_plain_text(self):
        from scripts.build_ny_verification_workbook import _build_data_dictionary, _build_readme_df

        readme = _build_readme_df()
        for val in readme["detail"].astype(str):
            if val and val != "nan":
                self.assertFalse(
                    val.startswith("="),
                    msg=f"README detail must not start with = (Excel treats it as a formula): {val[:80]}",
                )

        data_dict = _build_data_dictionary()
        for val in data_dict["formula_or_notes"].astype(str):
            if val and val != "nan":
                self.assertFalse(
                    val.startswith("="),
                    msg=f"Data dictionary formula_or_notes must not start with =: {val[:80]}",
                )


class NyVerificationWorkbookTest(unittest.TestCase):
    def test_verify_script_exits_zero(self):
        script = ROOT / "scripts" / "verify_ny_verification_workbook.py"
        self.assertTrue(script.is_file(), "run scripts/build_ny_verification_workbook.py first")
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
