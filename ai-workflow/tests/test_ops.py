"""Unit tests for project_tree.ops."""

import copy
import sys
import unittest
from pathlib import Path

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import ops
from project_tree.model import find_node_in_tree
from project_tree.ops import (
    add_child,
    add_group,
    apply_batch,
    apply_op,
    attach_subtree,
    clear_stale,
    mark_stale,
    rename,
    reparent,
    set_all_weak,
    set_constraint,
    set_data,
    set_status,
)


class BaseOpsTestCase(unittest.TestCase):
    """Base test fixture providing a standardized tree for ops testing."""

    def setUp(self):
        self.tree = {
            "project": "test-project",
            "updated": "2026-09-13",
            "constraints": {"daily-loop": ["orient", "implement"]},
            "nodes": [
                {
                    "id": "root",
                    "title": "Root Node",
                    "kind": "group",
                    "status": "strong",
                    "children": [
                        {
                            "id": "group-a",
                            "title": "Group A",
                            "kind": "group",
                            "status": "weak",
                            "data": {"meta_key": "val1"},
                            "children": [
                                {
                                    "id": "leaf-1",
                                    "title": "Leaf 1",
                                    "kind": "work",
                                    "status": "weak",
                                }
                            ],
                        },
                        {
                            "id": "group-b",
                            "title": "Group B",
                            "kind": "group",
                            "status": "weak",
                            "children": [],
                        },
                    ],
                }
            ],
        }


class TestAddChild(BaseOpsTestCase):
    """Tests for add_child, add_group, and attach_subtree."""

    def test_add_child_to_root(self):
        original = copy.deepcopy(self.tree)
        new_tree = add_child(self.tree, "root", "new-node", "New Node")

        # Immutability check
        self.assertEqual(self.tree, original)

        # Result verification
        node = find_node_in_tree(new_tree, "new-node")
        self.assertIsNotNone(node)
        self.assertEqual(node["id"], "new-node")
        self.assertEqual(node["title"], "New Node")
        self.assertEqual(node["kind"], "work")
        self.assertEqual(node["status"], "weak")

        # Verify it is attached to root
        root = find_node_in_tree(new_tree, "root")
        child_ids = [c["id"] for c in root["children"]]
        self.assertIn("new-node", child_ids)

    def test_add_child_custom_kind_and_status(self):
        new_tree = add_child(
            self.tree,
            "root",
            "spec-node",
            "Spec Node",
            kind="spec",
            status="strong",
        )
        node = find_node_in_tree(new_tree, "spec-node")
        self.assertIsNotNone(node)
        self.assertEqual(node["kind"], "spec")
        self.assertEqual(node["status"], "strong")

    def test_add_child_to_nested_group(self):
        new_tree = add_child(self.tree, "leaf-1", "sub-leaf", "Sub Leaf")
        parent = find_node_in_tree(new_tree, "leaf-1")
        child = find_node_in_tree(new_tree, "sub-leaf")
        self.assertIsNotNone(child)
        self.assertEqual([c["id"] for c in parent["children"]], ["sub-leaf"])

    def test_add_child_parent_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            add_child(self.tree, "nonexistent-parent", "c1", "Child 1")
        self.assertIn("Parent node not found", str(ctx.exception))

    def test_add_child_duplicate_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            add_child(self.tree, "root", "group-a", "Duplicate Group A")
        self.assertIn("Child already exists", str(ctx.exception))

    def test_add_group(self):
        new_tree = add_group(self.tree, "root", "group-c", "Group C")
        node = find_node_in_tree(new_tree, "group-c")
        self.assertIsNotNone(node)
        self.assertEqual(node["kind"], "group")
        self.assertEqual(node["status"], "weak")

    def test_attach_subtree(self):
        new_tree = attach_subtree(
            self.tree,
            "root",
            "frag-stub",
            "Fragment Stub",
            "fragments/demo.yaml",
        )
        node = find_node_in_tree(new_tree, "frag-stub")
        self.assertIsNotNone(node)
        self.assertEqual(node["kind"], "group")
        self.assertEqual(node.get("data"), {"subtree": "fragments/demo.yaml"})


class TestSetData(BaseOpsTestCase):
    """Tests for set_data."""

    def test_set_data_new_dictionary(self):
        original = copy.deepcopy(self.tree)
        new_tree = set_data(self.tree, "leaf-1", {"author": "alice", "priority": 1})

        # Immutability check
        self.assertEqual(self.tree, original)

        node = find_node_in_tree(new_tree, "leaf-1")
        self.assertEqual(node["data"], {"author": "alice", "priority": 1})

    def test_set_data_merge_existing(self):
        new_tree = set_data(
            self.tree,
            "group-a",
            {"meta_key": "updated_val", "new_key": "added"},
        )
        node = find_node_in_tree(new_tree, "group-a")
        self.assertEqual(
            node["data"],
            {"meta_key": "updated_val", "new_key": "added"},
        )

    def test_set_data_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            set_data(self.tree, "nonexistent", {"key": "val"})
        self.assertIn("Node not found", str(ctx.exception))


class TestSetStatus(BaseOpsTestCase):
    """Tests for set_status."""

    def test_set_status_success(self):
        original = copy.deepcopy(self.tree)
        new_tree = set_status(self.tree, "leaf-1", "strong")

        # Immutability check
        self.assertEqual(self.tree, original)

        node = find_node_in_tree(new_tree, "leaf-1")
        self.assertEqual(node["status"], "strong")

        newer_tree = set_status(new_tree, "leaf-1", "discussing")
        node2 = find_node_in_tree(newer_tree, "leaf-1")
        self.assertEqual(node2["status"], "discussing")

    def test_set_status_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            set_status(self.tree, "nonexistent", "strong")
        self.assertIn("Node not found", str(ctx.exception))


class TestReparent(BaseOpsTestCase):
    """Tests for reparent."""

    def test_reparent_success(self):
        original = copy.deepcopy(self.tree)
        # Move leaf-1 from group-a to group-b
        new_tree = reparent(self.tree, "leaf-1", "group-b")

        # Immutability check
        self.assertEqual(self.tree, original)

        old_parent = find_node_in_tree(new_tree, "group-a")
        new_parent = find_node_in_tree(new_tree, "group-b")
        moved_node = find_node_in_tree(new_tree, "leaf-1")

        self.assertEqual(old_parent.get("children"), [])
        self.assertEqual([c["id"] for c in new_parent["children"]], ["leaf-1"])
        self.assertEqual(moved_node["title"], "Leaf 1")

    def test_reparent_nested_to_root(self):
        new_tree = reparent(self.tree, "leaf-1", "root")
        root = find_node_in_tree(new_tree, "root")
        group_a = find_node_in_tree(new_tree, "group-a")

        self.assertEqual(group_a.get("children"), [])
        self.assertIn("leaf-1", [c["id"] for c in root["children"]])

    def test_reparent_under_itself_raises(self):
        with self.assertRaises(ValueError) as ctx:
            reparent(self.tree, "group-a", "group-a")
        self.assertIn("cannot reparent node under itself", str(ctx.exception))

    def test_reparent_under_descendant_raises(self):
        with self.assertRaises(ValueError) as ctx:
            reparent(self.tree, "group-a", "leaf-1")
        self.assertIn("cannot reparent under a descendant", str(ctx.exception))

    def test_reparent_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            reparent(self.tree, "nonexistent", "group-b")
        self.assertIn("Node not found", str(ctx.exception))

    def test_reparent_target_parent_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            reparent(self.tree, "leaf-1", "nonexistent")
        self.assertIn("Parent node not found", str(ctx.exception))

    def test_reparent_child_already_exists_under_target(self):
        # Add a node named leaf-1 under group-b first
        tree_with_duplicate = add_child(self.tree, "group-b", "leaf-1", "Existing Leaf")
        with self.assertRaises(ValueError) as ctx:
            reparent(tree_with_duplicate, "leaf-1", "group-b")
        self.assertIn("Child already exists under group-b", str(ctx.exception))


class TestMarkAndClearStale(BaseOpsTestCase):
    """Tests for mark_stale and clear_stale."""

    def test_mark_stale_without_notes(self):
        original = copy.deepcopy(self.tree)
        new_tree = mark_stale(self.tree, "leaf-1")

        # Immutability check
        self.assertEqual(self.tree, original)

        node = find_node_in_tree(new_tree, "leaf-1")
        self.assertTrue(node.get("stale"))
        self.assertNotIn("notes", node)

    def test_mark_stale_with_notes(self):
        new_tree = mark_stale(self.tree, "leaf-1", notes="deprecated by v2")
        node = find_node_in_tree(new_tree, "leaf-1")
        self.assertTrue(node.get("stale"))
        self.assertEqual(node.get("notes"), "deprecated by v2")

    def test_mark_stale_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            mark_stale(self.tree, "nonexistent")
        self.assertIn("Node not found", str(ctx.exception))

    def test_clear_stale(self):
        stale_tree = mark_stale(self.tree, "leaf-1", notes="stale note")
        cleared_tree = clear_stale(stale_tree, "leaf-1")

        node = find_node_in_tree(cleared_tree, "leaf-1")
        self.assertFalse(node.get("stale"))
        self.assertNotIn("notes", node)

    def test_clear_stale_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            clear_stale(self.tree, "nonexistent")
        self.assertIn("Node not found", str(ctx.exception))


class TestRename(BaseOpsTestCase):
    """Tests for rename."""

    def test_rename_success(self):
        original = copy.deepcopy(self.tree)
        new_tree = rename(self.tree, "leaf-1", "  Renamed Leaf 1  ")

        # Immutability check
        self.assertEqual(self.tree, original)

        node = find_node_in_tree(new_tree, "leaf-1")
        self.assertEqual(node["title"], "Renamed Leaf 1")

    def test_rename_empty_title_raises(self):
        with self.assertRaises(ValueError) as ctx:
            rename(self.tree, "leaf-1", "   ")
        self.assertIn("title must be non-empty", str(ctx.exception))

    def test_rename_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            rename(self.tree, "nonexistent", "New Title")
        self.assertIn("Node not found", str(ctx.exception))


class TestBatchAndApplyOp(BaseOpsTestCase):
    """Tests for apply_op, apply_batch, set_constraint, and set_all_weak."""

    def test_apply_op(self):
        new_tree = apply_op(
            self.tree,
            "add-child",
            args=["root", "c3", "Child 3"],
            kwargs={"kind": "work", "status": "discussing"},
        )
        node = find_node_in_tree(new_tree, "c3")
        self.assertIsNotNone(node)
        self.assertEqual(node["status"], "discussing")

    def test_apply_op_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            apply_op(self.tree, "unregistered-op")
        self.assertIn("Unknown operation", str(ctx.exception))

    def test_apply_batch_atomic_sequence(self):
        operations = [
            {
                "op": "add-child",
                "args": ["root", "feature-x", "Feature X"],
                "kwargs": {"kind": "group", "status": "weak"},
            },
            {
                "op": "set-status",
                "args": ["feature-x", "strong"],
            },
            {
                "op": "set-data",
                "args": ["feature-x", {"owner": "team-core"}],
            },
            {
                "op": "add-child",
                "args": ["feature-x", "sub-task", "Sub Task 1"],
            },
            {
                "op": "mark-stale",
                "args": ["leaf-1"],
                "kwargs": {"notes": "superseded by Feature X"},
            },
        ]

        original = copy.deepcopy(self.tree)
        result = apply_batch(self.tree, operations)

        # Immutability of initial input tree
        self.assertEqual(self.tree, original)

        # Verify all batch steps applied
        fx = find_node_in_tree(result, "feature-x")
        self.assertIsNotNone(fx)
        self.assertEqual(fx["status"], "strong")
        self.assertEqual(fx.get("data"), {"owner": "team-core"})

        sub = find_node_in_tree(result, "sub-task")
        self.assertIsNotNone(sub)
        self.assertEqual([c["id"] for c in fx["children"]], ["sub-task"])

        stale_leaf = find_node_in_tree(result, "leaf-1")
        self.assertTrue(stale_leaf.get("stale"))
        self.assertEqual(stale_leaf.get("notes"), "superseded by Feature X")

    def test_apply_batch_empty(self):
        result = apply_batch(self.tree, [])
        self.assertEqual(result, self.tree)

    def test_apply_batch_missing_op_key(self):
        with self.assertRaises(ValueError) as ctx:
            apply_batch(self.tree, [{"args": ["root", "node", "title"]}])
        self.assertIn("Batch step 0: missing 'op'", str(ctx.exception))

    def test_apply_batch_unknown_op(self):
        with self.assertRaises(ValueError) as ctx:
            apply_batch(self.tree, [{"op": "invalid-op-name"}])
        self.assertIn("Unknown operation", str(ctx.exception))

    def test_set_constraint(self):
        new_tree = set_constraint(self.tree, "framework", "python", "yaml")
        self.assertEqual(
            new_tree["constraints"]["framework"],
            ["python", "yaml"],
        )

    def test_set_all_weak(self):
        # Initially root is strong, group-a is weak, leaf-1 is weak, group-b is weak
        # Set leaf-1 to strong, group-a to discussing
        t1 = set_status(self.tree, "leaf-1", "strong")
        t2 = set_status(t1, "group-a", "discussing")

        # set_all_weak preserves strong by default
        weakened = set_all_weak(t2)
        self.assertEqual(find_node_in_tree(weakened, "root")["status"], "strong")
        self.assertEqual(find_node_in_tree(weakened, "leaf-1")["status"], "strong")
        self.assertEqual(find_node_in_tree(weakened, "group-a")["status"], "weak")

        # Custom preserve set
        custom_weakened = set_all_weak(t2, "discussing")
        self.assertEqual(find_node_in_tree(custom_weakened, "group-a")["status"], "discussing")
        self.assertEqual(find_node_in_tree(custom_weakened, "root")["status"], "weak")
        self.assertEqual(find_node_in_tree(custom_weakened, "leaf-1")["status"], "weak")

    def test_dead_operations_removed(self):
        for op in ["include-meal", "exclude-meal", "add-allergies"]:
            with self.subTest(op=op):
                self.assertNotIn(op, ops.OP_HANDLERS)
                with self.assertRaises(ValueError):
                    ops.apply_op({"nodes": []}, op, ["test"])



if __name__ == "__main__":
    unittest.main()
