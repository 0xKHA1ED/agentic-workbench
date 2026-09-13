"""Tests for pattern fingerprinting and decay scanning."""

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import decay, model, patterns


def _fingerprint_for(node: dict, tree: dict, repo_root: Path) -> str:
    with patch.object(model, "REPO_ROOT", repo_root), patch.object(patterns, "REPO_ROOT", repo_root):
        return patterns.compute_pattern_fingerprint(node, tree)


class TestPatternFingerprint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.code_dir = self.repo / "code"
        self.code_dir.mkdir(parents=True)
        self.module = self.code_dir / "module.py"
        self.module.write_text("version = 1\n", encoding="utf-8")
        self.tree = {
            "project": "decay-test",
            "nodes": [
                {
                    "id": "n1",
                    "title": "Module",
                    "kind": "work",
                    "status": "verified_strong",
                    "data": {"pattern": "code/module.py"},
                }
            ],
        }
        self.node = self.tree["nodes"][0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_fingerprint_stable_across_reads(self):
        fp1 = _fingerprint_for(self.node, self.tree, self.repo)
        fp2 = _fingerprint_for(self.node, self.tree, self.repo)
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_fingerprint_changes_when_content_changes(self):
        fp1 = _fingerprint_for(self.node, self.tree, self.repo)
        self.module.write_text("version = 2\n", encoding="utf-8")
        fp2 = _fingerprint_for(self.node, self.tree, self.repo)
        self.assertNotEqual(fp1, fp2)


class TestScanDecay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.proj_name = "decay-test"
        self.proj_dir = self.repo / "projects" / self.proj_name
        self.proj_dir.mkdir(parents=True)
        self.code_dir = self.repo / "code"
        self.code_dir.mkdir(parents=True)
        self.module = self.code_dir / "module.py"
        self.module.write_text("version = 1\n", encoding="utf-8")
        self.nodes_path = self.proj_dir / "nodes.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_tree(self, tree: dict) -> None:
        import yaml

        with self.nodes_path.open("w", encoding="utf-8") as handle:
            yaml.dump(tree, handle, default_flow_style=False, sort_keys=False)

    def _base_tree(self, verification: dict) -> dict:
        node = {
            "id": "n1",
            "title": "Module",
            "kind": "work",
            "status": "verified_strong",
            "data": {
                "pattern": "code/module.py",
                "verification": verification,
            },
        }
        return {"project": self.proj_name, "nodes": [node]}

    def _run_scan(self, *, dry_run: bool = False) -> dict:
        with (
            patch.object(model, "REPO_ROOT", self.repo),
            patch.object(model, "host_root", return_value=self.repo),
            patch.object(patterns, "REPO_ROOT", self.repo),
            patch.object(decay, "REPO_ROOT", self.repo),
            patch.object(model, "project_dir", return_value=self.proj_dir),
            patch.object(model, "nodes_path", return_value=self.nodes_path),
        ):
            return decay.scan_decay(self.proj_name, dry_run=dry_run)

    def test_decay_on_fingerprint_change_with_failing_command(self):
        fp = _fingerprint_for(
            {"data": {"pattern": "code/module.py"}},
            {"project": self.proj_name},
            self.repo,
        )
        tree = self._base_tree(
            {
                "check_type": "command",
                "command": "python3 -c 'import sys; sys.exit(1)'",
                "fingerprint": fp,
            }
        )
        self._write_tree(tree)
        self.module.write_text("version = 2\n", encoding="utf-8")

        result = self._run_scan()
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["decayed"], 1)
        self.assertEqual(result["refreshed"], 0)
        self.assertEqual(result["nodes"][0]["action"], "decayed")

        import yaml

        saved = yaml.safe_load(self.nodes_path.read_text(encoding="utf-8"))
        node = saved["nodes"][0]
        self.assertEqual(node["status"], "decayed_unverified")
        self.assertTrue(node["data"]["decayed"])
        self.assertIn("decay_reason", node["data"])

    def test_refresh_on_fingerprint_change_with_passing_command(self):
        fp = _fingerprint_for(
            {"data": {"pattern": "code/module.py"}},
            {"project": self.proj_name},
            self.repo,
        )
        tree = self._base_tree(
            {
                "check_type": "command",
                "command": "echo refreshed",
                "fingerprint": fp,
            }
        )
        self._write_tree(tree)
        self.module.write_text("version = 2\n", encoding="utf-8")

        result = self._run_scan()
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["decayed"], 0)
        self.assertEqual(result["refreshed"], 1)
        self.assertEqual(result["nodes"][0]["action"], "refreshed")

        import yaml

        saved = yaml.safe_load(self.nodes_path.read_text(encoding="utf-8"))
        node = saved["nodes"][0]
        self.assertEqual(node["status"], "verified_strong")
        new_fp = _fingerprint_for(node, saved, self.repo)
        self.assertEqual(node["data"]["verification"]["fingerprint"], new_fp)
        self.assertEqual(node["data"]["verification"]["last_exit_code"], 0)
        self.assertIn("last_run_sha", node["data"]["verification"])

    def test_dry_run_does_not_write_files(self):
        fp = _fingerprint_for(
            {"data": {"pattern": "code/module.py"}},
            {"project": self.proj_name},
            self.repo,
        )
        tree = self._base_tree(
            {
                "check_type": "command",
                "command": "python3 -c 'import sys; sys.exit(1)'",
                "fingerprint": fp,
            }
        )
        self._write_tree(tree)
        before = self.nodes_path.read_text(encoding="utf-8")
        self.module.write_text("version = 2\n", encoding="utf-8")

        result = self._run_scan(dry_run=True)
        self.assertEqual(result["decayed"], 1)
        after = self.nodes_path.read_text(encoding="utf-8")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
