"""Stale prose guard for NY minimum staffing report copy."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_ny_staffing_prose_stale.py"


class NyStaffingProseStaleTest(unittest.TestCase):
    def test_no_stale_prose_in_public_copy(self):
        proc = subprocess.run(
            [sys.executable, str(AUDIT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=proc.stdout + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
