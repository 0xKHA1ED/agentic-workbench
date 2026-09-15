"""End-to-end sanity tests for project_tree CLI subprocess execution."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import yaml
from project_tree import model

CLI_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_tree.py"


class TestProjectTreeCliE2E(unittest.TestCase):
    """End-to-end tests executing actual project_tree.py subprocess commands."""

    @classmethod
    def setUpClass(cls):
        """Ensure projects/tik fixture exists for environments without local sandbox checkout."""
        cls._created_tik_dir = None
        cls._created_tik_file = None
        tik_dir = model.project_dir("tik")
        nodes_file = tik_dir / "nodes.yaml"
        if not nodes_file.exists():
            # Check if main repo has projects/tik (e.g. when in git worktree)
            git_file = model.host_root() / ".git"
            main_tik_nodes = None
            if git_file.is_file():
                try:
                    content = git_file.read_text()
                    for line in content.splitlines():
                        if line.startswith("gitdir:"):
                            gitdir_path = Path(line.split("gitdir:", 1)[1].strip()).resolve()
                            candidate = gitdir_path.parents[2] / "projects" / "tik" / "nodes.yaml"
                            if candidate.exists():
                                main_tik_nodes = candidate
                                break
                except Exception:
                    pass

            tik_dir.mkdir(parents=True, exist_ok=True)
            if main_tik_nodes and main_tik_nodes.exists():
                try:
                    nodes_file.symlink_to(main_tik_nodes)
                except OSError:
                    nodes_file.write_text(main_tik_nodes.read_text())
            else:
                nodes_file.write_text(
                    "project: tik\n"
                    "nodes:\n"
                    "  - id: root\n"
                    "    title: WHICH ONE WINS (tik)\n"
                    "    kind: group\n"
                    "    status: weak\n"
                )
            cls._created_tik_dir = tik_dir
            cls._created_tik_file = nodes_file

    @classmethod
    def tearDownClass(cls):
        """Clean up any fixture created for tik if applicable."""
        if cls._created_tik_file and cls._created_tik_file.exists():
            if cls._created_tik_file.is_symlink() or cls._created_tik_file.is_file():
                cls._created_tik_file.unlink()
        if cls._created_tik_dir and cls._created_tik_dir.exists():
            import shutil

            shutil.rmtree(cls._created_tik_dir, ignore_errors=True)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run project_tree.py CLI as a subprocess and return the completed process."""
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_show_meta(self):
        """project_tree.py show meta exits 0 and stdout contains 'AI Workflow'."""
        result = self._run_cli("show", "meta")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")
        self.assertIn("AI Workflow", result.stdout)

    def test_show_meta_status_weak_prunes_tree(self):
        """--status weak shows only weak branches, not the full composed tree."""
        result = self._run_cli("show", "meta", "--status", "weak")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")
        self.assertIn("Roleplay demo", result.stdout)
        self.assertIn("Fictional: cement silent fallbacks", result.stdout)
        self.assertNotIn("Orient [group] strong", result.stdout)

    def test_compose_meta(self):
        """project_tree.py compose meta exits 0 and stdout parses as valid yaml with 'nodes'."""
        result = self._run_cli("compose", "meta")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")
        parsed = yaml.safe_load(result.stdout)
        self.assertIsInstance(parsed, dict)
        self.assertIn("nodes", result.stdout.lower())
        self.assertTrue(
            "nodes" in parsed
            or "Composed nodes" in parsed
            or any("nodes" in str(k).lower() for k in parsed),
            f"Expected 'nodes' key in parsed YAML or summary: {parsed}",
        )

    def test_list_fragments_meta(self):
        """project_tree.py list-fragments meta exits 0 and stdout contains 'fragments/'."""
        result = self._run_cli("list-fragments", "meta")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")
        self.assertIn("fragments/", result.stdout)

    def test_validate_patterns_meta_recursive(self):
        """project_tree.py validate-patterns meta --recursive exits 0."""
        result = self._run_cli("validate-patterns", "meta", "--recursive")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")

    def test_show_tik(self):
        """project_tree.py show tik exits 0 and stdout contains 'WHICH ONE WINS'."""
        result = self._run_cli("show", "tik")
        self.assertEqual(result.returncode, 0, f"Command failed with stderr:\n{result.stderr}")
        self.assertIn("WHICH ONE WINS", result.stdout)


class TestFragmentReverseIndex(unittest.TestCase):
    """Epic G — node_id → fragment reverse index (no --fragment needed)."""

    def test_root_defined_node_resolves_to_none(self):
        from project_tree import fragments

        self.assertIsNone(fragments.fragment_for_node("meta", "root"))
        self.assertIsNone(fragments.fragment_for_node("meta", "orient"))
        self.assertIsNone(fragments.fragment_for_node("meta", "platform"))

    def test_fragment_defined_node_resolves_to_fragment(self):
        from project_tree import fragments

        self.assertEqual(
            fragments.fragment_for_node("meta", "viewer-server"),
            "fragments/orient.yaml",
        )
        self.assertEqual(
            fragments.fragment_for_node("meta", "platform-ops"),
            "fragments/platform.yaml",
        )
        self.assertEqual(
            fragments.fragment_for_node("meta", "ref-sp-tdd"),
            "fragments/reference-improvements.yaml",
        )

    def test_unknown_node_raises(self):
        from project_tree import fragments

        with self.assertRaises(ValueError):
            fragments.fragment_for_node("meta", "no-such-node-xyz")

    def test_cli_auto_resolves_fragment_target(self):
        """_primary_target_node + _auto_resolve_fragment infer the fragment."""
        import argparse

        from project_tree import cli

        args = argparse.Namespace(
            project="meta",
            operation="set-status",
            rest=["viewer-server", "strong"],
            fragment=None,
            json=None,
            file=None,
        )
        cli._auto_resolve_fragment(args)
        self.assertEqual(args.fragment, "fragments/orient.yaml")


if __name__ == "__main__":
    unittest.main()
