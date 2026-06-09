"""Statutory NY-mapped default metric audit."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_ny_statutory_role_mapping.py"


class NyStatutoryRoleMappingTest(unittest.TestCase):
    def test_statutory_role_mapping_audit_passes(self):
        proc = subprocess.run(
            [sys.executable, str(AUDIT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
