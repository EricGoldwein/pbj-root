"""NY 2025 verification workbook package tests."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
