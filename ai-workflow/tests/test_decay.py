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


class TestDecayHook(unittest.TestCase):
    def test_main_skips_scan_when_no_changed_files(self):
        import decay_hook

        with (
            patch.object(decay_hook, "get_changed_files_from_latest_commit", return_value=[]),
            patch.object(decay_hook, "run_hook_scan") as mock_scan,
        ):
            self.assertEqual(decay_hook.main(), 0)
        mock_scan.assert_not_called()

    def test_main_runs_scan_with_changed_files(self):
        import decay_hook

        changed = [Path("/repo/code/module.py")]
        with (
            patch.object(decay_hook, "get_changed_files_from_latest_commit", return_value=changed),
            patch.object(decay_hook, "run_hook_scan") as mock_scan,
        ):
            self.assertEqual(decay_hook.main(), 0)
        mock_scan.assert_called_once_with(changed_files=changed)

    def test_run_hook_scan_skips_when_changed_files_empty(self):
        import decay_hook

        with patch.object(decay_hook.decay, "scan_decay") as mock_scan:
            result = decay_hook.run_hook_scan(changed_files=[])
        mock_scan.assert_not_called()
        self.assertTrue(result["skipped"])
        self.assertEqual(result["scanned"], 0)

    def test_run_hook_scan_calls_scan_decay_for_each_project(self):
        import decay_hook

        changed = [Path("/repo/code/module.py")]
        with (
            patch.object(decay_hook.model, "list_projects", return_value=["meta", "demo"]),
            patch.object(
                decay_hook.decay,
                "scan_decay",
                side_effect=[
                    {"scanned": 1, "decayed": 0, "refreshed": 0, "nodes": []},
                    {"scanned": 2, "decayed": 1, "refreshed": 0, "nodes": [{"id": "n1"}]},
                ],
            ) as mock_scan,
        ):
            result = decay_hook.run_hook_scan(changed_files=changed)

        self.assertEqual(mock_scan.call_count, 2)
        mock_scan.assert_any_call("meta", dry_run=False, changed_files=changed)
        mock_scan.assert_any_call("demo", dry_run=False, changed_files=changed)
        self.assertEqual(result["scanned"], 3)
        self.assertEqual(result["decayed"], 1)
        self.assertEqual(len(result["nodes"]), 1)

    def test_scan_decay_skips_when_changed_files_empty_list(self):
        with (
            patch.object(model, "REPO_ROOT", Path("/tmp")),
            patch.object(model, "load_tree") as mock_load,
        ):
            result = decay.scan_decay("meta", changed_files=[])
        mock_load.assert_not_called()
        self.assertEqual(result, {"scanned": 0, "decayed": 0, "refreshed": 0, "nodes": []})


class TestInstallDecayHook(unittest.TestCase):
    def setUp(self):
        import argparse

        self.argparse = argparse
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git_dir = self.repo / ".git"
        self.hooks_dir = self.git_dir / "hooks"
        self.hooks_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _run_install(self) -> int:
        from project_tree.cli import cmd_install_decay_hook

        with (
            patch.object(model, "REPO_ROOT", self.repo),
            patch.object(model, "PACKAGE_ROOT", self.repo / "ai-workflow"),
        ):
            return cmd_install_decay_hook(self.argparse.Namespace())

    def test_install_writes_executable_hook(self):
        import stat

        hook_script = self.repo / "ai-workflow" / "scripts" / "decay_hook.py"
        hook_script.parent.mkdir(parents=True)
        hook_script.write_text("# hook\n", encoding="utf-8")

        rc = self._run_install()
        self.assertEqual(rc, 0)

        hook_path = self.hooks_dir / "post-commit"
        self.assertTrue(hook_path.exists())
        content = hook_path.read_text(encoding="utf-8")
        self.assertIn("decay_hook.py", content)
        self.assertTrue(hook_path.stat().st_mode & stat.S_IXUSR)

    def test_install_is_idempotent(self):
        hook_script = self.repo / "ai-workflow" / "scripts" / "decay_hook.py"
        hook_script.parent.mkdir(parents=True)
        hook_script.write_text("# hook\n", encoding="utf-8")

        self._run_install()
        hook_path = self.hooks_dir / "post-commit"
        first = hook_path.read_text(encoding="utf-8")
        self._run_install()
        second = hook_path.read_text(encoding="utf-8")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
