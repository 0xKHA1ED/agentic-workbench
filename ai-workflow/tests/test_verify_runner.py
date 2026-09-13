"""Tests for shared verification runner."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree.verify_runner import normalize_verification_spec, run_verification


def _pytest_available() -> bool:
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class TestVerifyRunnerCommand(unittest.TestCase):
    def test_command_success(self):
        spec = normalize_verification_spec({"check_type": "command", "command": "echo hello"})
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_verification(spec, Path(tmpdir))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello", result["stdout"])
        self.assertEqual(result["command"], "echo hello")
        self.assertIsInstance(result["duration_seconds"], (int, float))

    def test_command_failure(self):
        spec = normalize_verification_spec(
            {"check_type": "command", "command": "python3 -c 'import sys; sys.exit(2)'"}
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_verification(spec, Path(tmpdir))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)


class TestVerifyRunnerPytest(unittest.TestCase):
    @unittest.skipUnless(_pytest_available(), "pytest not available")
    def test_pytest_runs_trivial_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            test_file = cwd / "test_sample.py"
            test_file.write_text(
                "def test_ok():\n"
                "    assert True\n"
            )
            spec = normalize_verification_spec(
                {"check_type": "pytest", "target": str(test_file)}
            )
            result = run_verification(spec, cwd)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("pytest", result["command"])


class TestVerifyRunnerAstSymbol(unittest.TestCase):
    def test_ast_symbol_detects_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            module = cwd / "sample.py"
            module.write_text("def exported_fn():\n    return 1\n\nclass ExportedClass:\n    pass\n")
            spec = normalize_verification_spec(
                {
                    "check_type": "ast_symbol",
                    "file": "sample.py",
                    "symbols": ["exported_fn", "ExportedClass"],
                }
            )
            result = run_verification(spec, cwd)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["exit_code"], 0)

    def test_ast_symbol_missing_symbol_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            module = cwd / "sample.py"
            module.write_text("def present():\n    pass\n")
            spec = normalize_verification_spec(
                {
                    "check_type": "ast_symbol",
                    "file": "sample.py",
                    "symbols": ["missing_symbol"],
                }
            )
            result = run_verification(spec, cwd)
        self.assertEqual(result["status"], "failed")
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("missing_symbol", result["stderr"].lower())


class TestVerifyRunnerLegacy(unittest.TestCase):
    def test_legacy_string_command(self):
        spec = normalize_verification_spec("echo legacy_ok")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_verification(spec, Path(tmpdir))
        self.assertEqual(result["status"], "passed")
        self.assertIn("legacy_ok", result["stdout"])
        self.assertEqual(spec["check_type"], "command")

    def test_legacy_command_dict_without_check_type(self):
        spec = normalize_verification_spec({"command": "echo dict_legacy"})
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_verification(spec, Path(tmpdir))
        self.assertEqual(result["status"], "passed")
        self.assertIn("dict_legacy", result["stdout"])

    def test_type_alias_for_check_type(self):
        spec = normalize_verification_spec({"type": "command", "command": "echo type_alias"})
        self.assertEqual(spec["check_type"], "command")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_verification(spec, Path(tmpdir))
        self.assertEqual(result["status"], "passed")
        self.assertIn("type_alias", result["stdout"])


if __name__ == "__main__":
    unittest.main()
