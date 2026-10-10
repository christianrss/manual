"""Compile the published C++17 example and run its native assertions in CI."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "cpp" / "token_bucket.cpp"

class NativeCppTest(unittest.TestCase):
    def test_compiles_and_executes(self):
        self.assertTrue(SOURCE.is_file())
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "manual-token-bucket"
            subprocess.run(
                ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra",
                 "-Werror", "-pthread", str(SOURCE), "-o", str(binary)],
                check=True, timeout=60, capture_output=True, text=True
            )
            subprocess.run([str(binary)], check=True, timeout=15,
                           capture_output=True, text=True)
