"""Final proof — the composed meta tree is 100% strong and every node is certified.

This is the falsifiable VERIFY for the whole program: it fails the instant any
node is not `strong`, or any leaf is missing its contract / verify / dogfood
certification links or their files on disk.
"""

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import model
from project_tree.fragments import compose_tree, walk_nodes


def _nodes():
    composed = compose_tree(model.load_tree("meta"), "meta")
    return list(walk_nodes(composed.get("nodes") or []))


class TestMetaAllStrong(unittest.TestCase):
    def setUp(self):
        self.nodes = _nodes()

    def test_composed_node_count(self):
        self.assertEqual(len(self.nodes), 77)

    def test_zero_non_strong_nodes(self):
        non_strong = [n["id"] for n in self.nodes if n.get("status") != "strong"]
        self.assertEqual(non_strong, [], f"non-strong nodes remain: {non_strong}")

    def test_every_leaf_is_certified(self):
        missing = []
        for n in self.nodes:
            is_leaf = n.get("kind") != "group" and not n.get("children")
            if not is_leaf:
                continue
            data = n.get("data") or {}
            for key in ("contract", "verify", "dogfood"):
                if not data.get(key):
                    missing.append(f"{n['id']}:{key}")
        self.assertEqual(missing, [], f"leaves missing certification links: {missing}")

    def test_certification_files_exist(self):
        missing_files = []
        for n in self.nodes:
            data = n.get("data") or {}
            for key in ("contract", "dogfood"):
                rel = data.get(key)
                if rel and not (PACKAGE_ROOT / rel).is_file():
                    missing_files.append(rel)
        self.assertEqual(missing_files, [], f"missing certification files: {missing_files}")

    def test_every_group_has_rollup_evidence(self):
        for n in self.nodes:
            is_group = n.get("kind") == "group" or bool(n.get("children"))
            if not is_group:
                continue
            data = n.get("data") or {}
            self.assertTrue(data.get("verify"), f"group {n['id']} missing verify")
            self.assertTrue(data.get("dogfood"), f"group {n['id']} missing dogfood")


if __name__ == "__main__":
    unittest.main()
