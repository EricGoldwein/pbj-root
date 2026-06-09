"""Tests for quarter-aligned NY provider attribution."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NyProviderAttributionTest(unittest.TestCase):
    def test_attribution_audit_exits_zero(self):
        script = ROOT / "scripts" / "audit_ny_provider_attribution.py"
        self.assertTrue(script.is_file())
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
