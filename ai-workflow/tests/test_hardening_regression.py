"""Regression tests for production-hardening fixes.

Each test pins a specific bug that was fixed:
  * Fragment path-traversal containment (sibling-prefix bypass).
  * Diamond fragment reuse no longer reported as a circular reference.
  * True circular subtree references are still detected.
  * assemble spec_path computation robust for shallow/custom output paths.
  * project_dir rejects traversal-style project names.
  * load_tree tolerates an empty nodes.yaml.
  * propose sub-commands report usage instead of raw tracebacks on missing args.
  * CLI commands report a clean error for unknown projects.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import fragments, model
from spec_discovery import assemble

CLI_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_tree.py"


def _write_fragment(base: Path, rel: str, body: str) -> None:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


class TestFragmentPathTraversal(unittest.TestCase):
    def test_sibling_prefix_path_is_blocked(self):
        base = model.project_dir("meta").resolve()
        sibling = f"../{base.name}-evil/secret.yaml"
        with self.assertRaises(ValueError):
            fragments.resolve_fragment_path("meta", sibling)

    def test_absolute_path_is_blocked(self):
        with self.assertRaises(ValueError):
            fragments.resolve_fragment_path("meta", "/etc/passwd")

    def test_legitimate_fragment_resolves(self):
        resolved = fragments.resolve_fragment_path("meta", "fragments/orient.yaml")
        self.assertEqual(resolved.name, "orient.yaml")
        self.assertIn("meta", resolved.parts)


class TestFragmentComposition(unittest.TestCase):
    def test_diamond_reuse_is_not_circular(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_fragment(
                base,
                "fragments/shared.yaml",
                "nodes:\n- id: s\n  title: S\n  kind: work\n  status: weak\n",
            )
            tree = {
                "project": "x",
                "nodes": [
                    {"id": "a", "title": "A", "kind": "group", "status": "weak",
                     "data": {"subtree": "fragments/shared.yaml"}},
                    {"id": "b", "title": "B", "kind": "group", "status": "weak",
                     "data": {"subtree": "fragments/shared.yaml"}},
                ],
            }
            with patch.object(model, "project_dir", return_value=base):
                composed = fragments.compose_tree(tree, "x")
            child_ids = [n["children"][0]["id"] for n in composed["nodes"]]
            self.assertEqual(child_ids, ["s", "s"])

    def test_true_cycle_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_fragment(
                base,
                "fragments/a.yaml",
                "nodes:\n- id: an\n  title: AN\n  kind: group\n  status: weak\n"
                "  data:\n    subtree: fragments/b.yaml\n",
            )
            _write_fragment(
                base,
                "fragments/b.yaml",
                "nodes:\n- id: bn\n  title: BN\n  kind: group\n  status: weak\n"
                "  data:\n    subtree: fragments/a.yaml\n",
            )
            tree = {
                "project": "y",
                "nodes": [
                    {"id": "r", "title": "R", "kind": "group", "status": "weak",
                     "data": {"subtree": "fragments/a.yaml"}},
                ],
            }
            with patch.object(model, "project_dir", return_value=base):
                with self.assertRaises(ValueError):
                    fragments.compose_tree(tree, "y")


class TestAssembleSpecPath(unittest.TestCase):
    def test_shallow_path_falls_back_to_absolute(self):
        result = assemble._display_spec_path(Path("/tmp/bare_spec_x.md"))
        self.assertEqual(result, "/tmp/bare_spec_x.md")

    def test_in_package_path_is_repo_relative(self):
        out = model.PACKAGE_ROOT / "meta" / "specs" / "node.md"
        self.assertEqual(assemble._display_spec_path(out), "meta/specs/node.md")


class TestProjectNameValidation(unittest.TestCase):
    def test_traversal_name_rejected(self):
        for name in ("../../etc", "..", "foo/bar", "a\\b", ""):
            with self.assertRaises(ValueError):
                model.project_dir(name)

    def test_legitimate_names_allowed(self):
        # Should not raise
        model.project_dir("meta")
        model.project_dir("my-project")
        model.project_dir("fragment-demo")


class TestLoadTreeEmptyFile(unittest.TestCase):
    def test_empty_tree_file_returns_empty_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "nodes.yaml"
            empty.write_text("")
            with patch.object(model, "nodes_path", return_value=empty):
                tree = model.load_tree("whatever")
            self.assertIsInstance(tree, dict)
            self.assertEqual(tree.get("nodes"), [])


class TestCliArgumentGuards(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_set_status_missing_args_shows_usage(self):
        result = self._run("propose", "meta", "set-status")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage: propose", result.stderr)

    def test_set_data_missing_args_shows_usage(self):
        result = self._run("propose", "meta", "set-data", "foo")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage: propose", result.stderr)

    def test_add_group_missing_args_shows_usage(self):
        result = self._run("propose", "meta", "add-group", "root")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Usage: propose", result.stderr)

    def test_unknown_project_reports_clean_error(self):
        result = self._run("show", "definitely-not-a-real-project-xyz")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_batch_file_reports_clean_error(self):
        result = self._run("propose", "meta", "batch", "--file", "/tmp/no-such-batch-xyz.json")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
