"""Stage111Z31X local Python preflight synthetic smoke, no real original bytes."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "Preflight-GetSpectrum.py"


class GigaCodePreflightTests(unittest.TestCase):
    def test_python_selftest_passes(self) -> None:
        p = subprocess.run(
            [sys.executable, str(SCRIPT), "--self-test"],
            capture_output=True, text=True, timeout=30, check=False
        )
        self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)
        self.assertIn("SELF_TEST_PASS:", p.stdout)
        self.assertIn("(4/4)", p.stdout)

    def test_cli_rejects_missing_capture_folder(self) -> None:
        p = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, timeout=30, check=False
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("folder is required", p.stderr)


if __name__ == "__main__":
    unittest.main()
