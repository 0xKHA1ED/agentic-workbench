"""Unit tests for project_tree.resolver and host_root integration."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import model
from project_tree.resolver import find_repository_root


class TestFindRepositoryRoot(unittest.TestCase):
    """Tests for deterministic host repository root resolver."""

    def test_detect_workflow_config_in_ancestor(self):
        """Finds root when .workflow/config.yaml is present in an ancestor directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            deep_path = root / "pkg" / "nested" / "sub"
            deep_path.mkdir(parents=True)

            config_file = root / ".workflow" / "config.yaml"
            config_file.parent.mkdir(parents=True)
            config_file.write_text("version: 2\n")

            resolved = find_repository_root(deep_path)
            self.assertEqual(resolved, root)

    def test_detect_git_dir_in_ancestor(self):
        """Finds root when .git directory is present in an ancestor directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            deep_path = root / "services" / "app"
            deep_path.mkdir(parents=True)

            git_dir = root / ".git"
            git_dir.mkdir(parents=True)

            resolved = find_repository_root(deep_path)
            self.assertEqual(resolved, root)

    def test_detect_git_file_in_ancestor(self):
        """Finds root when .git is a file (e.g. in git worktrees or submodules)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            deep_path = root / "services" / "app"
            deep_path.mkdir(parents=True)

            git_file = root / ".git"
            git_file.write_text("gitdir: /path/to/main/.git/worktrees/v2\n")

            resolved = find_repository_root(deep_path)
            self.assertEqual(resolved, root)

    def test_workflow_config_precedence_over_git(self):
        """Precedence: .workflow/config.yaml is prioritized at the same directory level, and closer ancestor takes precedence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            git_root = root / "outer_git"
            (git_root / ".git").mkdir(parents=True)

            project_root = git_root / "inner_project"
            config_file = project_root / ".workflow" / "config.yaml"
            config_file.parent.mkdir(parents=True)
            config_file.write_text("version: 2\n")

            deep_path = project_root / "nested" / "component"
            deep_path.mkdir(parents=True)

            resolved = find_repository_root(deep_path)
            self.assertEqual(resolved, project_root)

    def test_fallback_to_start_path_when_neither_found(self):
        """Falls back to start path when neither marker is found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            nested = root / "no_markers" / "child"
            nested.mkdir(parents=True)

            # Ensure neither marker exists in temp hierarchy
            resolved = find_repository_root(nested)
            # Must return start_path (nested), not any parent
            self.assertEqual(resolved, nested)

    def test_fallback_to_cwd_when_start_path_none(self):
        """Falls back to cwd when start_path is None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_cwd = Path(tmp_dir).resolve() / "working_dir"
            temp_cwd.mkdir(parents=True)

            orig_cwd = os.getcwd()
            try:
                os.chdir(temp_cwd)
                resolved = find_repository_root(None)
                self.assertEqual(resolved, temp_cwd)
            finally:
                os.chdir(orig_cwd)

    def test_no_arbitrary_parent_guessing(self):
        """Ensures the resolver never guesses arbitrary parent directories without markers."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            parent = root / "some_parent"
            child = parent / "deep_child"
            child.mkdir(parents=True)

            resolved = find_repository_root(child)
            # It should not return parent or root
            self.assertEqual(resolved, child)
            self.assertNotEqual(resolved, parent)
            self.assertNotEqual(resolved, root)

    def test_host_root_integration(self):
        """model.host_root() uses find_repository_root(PACKAGE_ROOT)."""
        resolved = model.host_root()
        self.assertIsInstance(resolved, Path)
        # Should match finding repo root from PACKAGE_ROOT
        self.assertEqual(resolved, find_repository_root(model.PACKAGE_ROOT))
