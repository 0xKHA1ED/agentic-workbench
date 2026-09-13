"""Unit tests for tree_server."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import yaml
from project_tree import model
from tree_server import TreeHandler


class TestTreeServerPendingProposals(unittest.TestCase):
    """Tests for pending proposal detection in tree_server.TreeHandler._load_tree."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.tmp_dir.name)
        # Create minimal valid nodes.yaml
        self.nodes_file = self.proj_dir / "nodes.yaml"
        with self.nodes_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [{"id": "root", "title": "Root", "kind": "goal", "status": "active"}],
                },
                f,
            )
        self.patcher = patch.object(model, "project_dir", return_value=self.proj_dir)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp_dir.cleanup()

    def test_load_tree_no_proposals(self):
        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertFalse(data["pending"])
        self.assertEqual(data["pending_targets"], [])

    def test_load_tree_fragment_proposal(self):
        frag_dir = self.proj_dir / "fragments"
        frag_dir.mkdir(parents=True, exist_ok=True)
        (frag_dir / "sim.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("fragments/sim.yaml", data["pending_targets"])

    def test_load_tree_root_proposal(self):
        (self.proj_dir / "nodes.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("nodes.yaml", data["pending_targets"])

    def test_load_tree_multiple_proposals(self):
        (self.proj_dir / "nodes.yaml.proposed").touch()
        frag_dir = self.proj_dir / "fragments"
        frag_dir.mkdir(parents=True, exist_ok=True)
        (frag_dir / "sim.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("nodes.yaml", data["pending_targets"])
        self.assertIn("fragments/sim.yaml", data["pending_targets"])
        self.assertEqual(len(data["pending_targets"]), 2)

    def test_load_tree_nonexistent_project(self):
        handler = TreeHandler.__new__(TreeHandler)
        with patch.object(model, "project_dir", return_value=self.proj_dir / "nonexistent"):
            with self.assertRaises(FileNotFoundError):
                handler._load_tree("nonexistent")


if __name__ == "__main__":
    unittest.main()
