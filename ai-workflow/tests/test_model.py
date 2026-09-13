"""Unit tests for project_tree.model."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import model
from project_tree.model import (
    ascii_tree,
    contains_descendant,
    dump_tree,
    find_node,
    find_node_in_tree,
    find_parent,
    find_parent_in_tree,
    host_root,
    list_pending_proposals,
    list_projects,
    load_tree,
    nodes_path,
    project_dir,
    proposed_path,
    resolve_project_name,
    save_tree,
    walk_nodes,
    get_pending_proposal_diff,
    apply_pending_proposal,
    reject_pending_proposal,
)


class TestModelProjectResolution(unittest.TestCase):
    """Tests for resolve_project_name, project_dir, nodes_path, and proposed_path."""

    def test_resolve_project_name_alias(self):
        self.assertEqual(resolve_project_name("ai-workflow"), "meta")

    def test_resolve_project_name_non_alias(self):
        self.assertEqual(resolve_project_name("meta"), "meta")
        self.assertEqual(resolve_project_name("fragment-demo"), "fragment-demo")
        self.assertEqual(resolve_project_name("unknown-project"), "unknown-project")

    def test_project_dir_meta(self):
        expected = model.PACKAGE_ROOT / "meta"
        self.assertEqual(project_dir("meta"), expected)
        self.assertEqual(project_dir("ai-workflow"), expected)

    def test_project_dir_example(self):
        expected = model.PACKAGE_ROOT / "examples" / "fragment-demo"
        self.assertEqual(project_dir("fragment-demo"), expected)

    def test_project_dir_host(self):
        expected = model.host_root() / "projects" / "my-project"
        self.assertEqual(project_dir("my-project"), expected)

    def test_nodes_path(self):
        self.assertEqual(nodes_path("ai-workflow"), model.PACKAGE_ROOT / "meta" / "nodes.yaml")
        self.assertEqual(nodes_path("meta"), model.PACKAGE_ROOT / "meta" / "nodes.yaml")
        self.assertEqual(
            nodes_path("fragment-demo"),
            model.PACKAGE_ROOT / "examples" / "fragment-demo" / "nodes.yaml",
        )
        self.assertEqual(
            nodes_path("external"),
            model.host_root() / "projects" / "external" / "nodes.yaml",
        )

    def test_proposed_path(self):
        self.assertEqual(
            proposed_path("ai-workflow"),
            model.PACKAGE_ROOT / "meta" / "nodes.yaml.proposed",
        )
        self.assertEqual(
            proposed_path("meta"),
            model.PACKAGE_ROOT / "meta" / "nodes.yaml.proposed",
        )
        self.assertEqual(
            proposed_path("fragment-demo"),
            model.PACKAGE_ROOT / "examples" / "fragment-demo" / "nodes.yaml.proposed",
        )
        self.assertEqual(
            proposed_path("external"),
            model.host_root() / "projects" / "external" / "nodes.yaml.proposed",
        )


class TestListProjects(unittest.TestCase):
    """Tests for list_projects."""

    def test_list_projects_current_repo(self):
        projects = list_projects()
        self.assertIn("meta", projects)
        self.assertIn("fragment-demo", projects)
        self.assertEqual(projects, sorted(projects))

    def test_list_projects_mocked_discovery(self):
        with tempfile.TemporaryDirectory() as tmp_pkg, tempfile.TemporaryDirectory() as tmp_host:
            pkg_path = Path(tmp_pkg)
            host_path = Path(tmp_host)

            # Create meta project
            meta_dir = pkg_path / "meta"
            meta_dir.mkdir(parents=True)
            (meta_dir / "nodes.yaml").touch()

            # Create example projects
            examples_dir = pkg_path / "examples"
            ex1 = examples_dir / "example-alpha"
            ex1.mkdir(parents=True)
            (ex1 / "nodes.yaml").touch()
            # Example without nodes.yaml should be ignored
            ex_ignored = examples_dir / "not-a-project"
            ex_ignored.mkdir(parents=True)

            # Create host projects
            host_projects = host_path / "projects"
            p1 = host_projects / "host-beta"
            p1.mkdir(parents=True)
            (p1 / "nodes.yaml").touch()
            # Host project without nodes.yaml should be ignored
            p_ignored = host_projects / "ignored-host"
            p_ignored.mkdir(parents=True)

            with patch.object(model, "PACKAGE_ROOT", pkg_path), \
                 patch.object(model, "host_root", return_value=host_path):
                found = list_projects()
                self.assertEqual(found, ["example-alpha", "host-beta", "meta"])


class TestListPendingProposals(unittest.TestCase):
    """Tests for list_pending_proposals."""

    def test_list_pending_proposals_none(self):
        # By default, meta should have no staged proposals
        self.assertEqual(list_pending_proposals("meta"), [])

    def test_list_pending_proposals_staged(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_dir = Path(tmp_dir)
            root_prop = proj_dir / "nodes.yaml.proposed"
            frag_dir = proj_dir / "fragments"
            frag_dir.mkdir()
            frag1_prop = frag_dir / "alpha.yaml.proposed"
            frag2_prop = frag_dir / "beta.yaml.proposed"
            non_prop = frag_dir / "gamma.yaml"

            root_prop.touch()
            frag1_prop.touch()
            frag2_prop.touch()
            non_prop.touch()

            with patch.object(model, "project_dir", return_value=proj_dir), \
                 patch.object(model, "proposed_path", return_value=root_prop):
                proposals = list_pending_proposals("test-proj")
                self.assertEqual(
                    proposals,
                    [
                        (None, root_prop),
                        ("fragments/alpha.yaml", frag1_prop),
                        ("fragments/beta.yaml", frag2_prop),
                    ],
                )

    def test_list_pending_proposals_alias_resolution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_dir = Path(tmp_dir)
            with patch.object(model, "project_dir") as mock_dir, \
                 patch.object(model, "proposed_path", return_value=proj_dir / "nodes.yaml.proposed"):
                mock_dir.return_value = proj_dir
                list_pending_proposals("ai-workflow")
                mock_dir.assert_called_with("meta")


class TestTreeLoadingAndInspection(unittest.TestCase):
    """Tests for load_tree, find_node, find_node_in_tree, and traversal helpers."""

    def setUp(self):
        self.sample_tree = {
            "project": "sample",
            "updated": "2026-09-13",
            "constraints": {"daily-loop": ["orient", "implement"]},
            "nodes": [
                {
                    "id": "root",
                    "title": "Sample Root",
                    "kind": "group",
                    "status": "strong",
                    "data": {"key": "value"},
                    "children": [
                        {
                            "id": "child-1",
                            "title": "Child One",
                            "kind": "work",
                            "status": "weak",
                            "children": [
                                {
                                    "id": "grandchild-1",
                                    "title": "Grandchild One",
                                    "kind": "work",
                                    "status": "discussing",
                                }
                            ],
                        },
                        {
                            "id": "child-2",
                            "title": "Child Two",
                            "kind": "work",
                            "status": "weak",
                        },
                    ],
                }
            ],
        }

    def test_load_tree_real_projects(self):
        meta_tree = load_tree("meta")
        self.assertEqual(meta_tree.get("project"), "meta")
        self.assertIsInstance(meta_tree.get("nodes"), list)

        # Alias load
        alias_tree = load_tree("ai-workflow")
        self.assertEqual(alias_tree.get("project"), "meta")

    def test_load_tree_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_tree("nonexistent-project-404")

    def test_find_node_in_tree(self):
        root = find_node_in_tree(self.sample_tree, "root")
        self.assertIsNotNone(root)
        self.assertEqual(root["title"], "Sample Root")

        child = find_node_in_tree(self.sample_tree, "child-1")
        self.assertIsNotNone(child)
        self.assertEqual(child["title"], "Child One")

        grandchild = find_node_in_tree(self.sample_tree, "grandchild-1")
        self.assertIsNotNone(grandchild)
        self.assertEqual(grandchild["title"], "Grandchild One")

        missing = find_node_in_tree(self.sample_tree, "nonexistent")
        self.assertIsNone(missing)

    def test_find_parent_in_tree(self):
        # Root has no parent
        self.assertIsNone(find_parent_in_tree(self.sample_tree, "root"))

        # child-1's parent is root
        parent1 = find_parent_in_tree(self.sample_tree, "child-1")
        self.assertIsNotNone(parent1)
        self.assertEqual(parent1["id"], "root")

        # grandchild-1's parent is child-1
        parent2 = find_parent_in_tree(self.sample_tree, "grandchild-1")
        self.assertIsNotNone(parent2)
        self.assertEqual(parent2["id"], "child-1")

        # Nonexistent node
        self.assertIsNone(find_parent_in_tree(self.sample_tree, "nonexistent"))

    def test_contains_descendant(self):
        root = find_node_in_tree(self.sample_tree, "root")
        child = find_node_in_tree(self.sample_tree, "child-1")

        self.assertTrue(contains_descendant(root, "child-1"))
        self.assertTrue(contains_descendant(root, "grandchild-1"))
        self.assertTrue(contains_descendant(child, "grandchild-1"))
        self.assertFalse(contains_descendant(child, "child-2"))
        self.assertFalse(contains_descendant(root, "nonexistent"))

    def test_walk_nodes(self):
        nodes = list(walk_nodes(self.sample_tree["nodes"]))
        ids = [n["id"] for n in nodes]
        self.assertEqual(ids, ["root", "child-1", "grandchild-1", "child-2"])

    def test_dump_and_save_tree(self):
        yaml_str = dump_tree(self.sample_tree)
        self.assertIn("project: sample", yaml_str)
        self.assertIn("Sample Root", yaml_str)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_nodes.yaml"
            tree_to_save = copy.deepcopy(self.sample_tree)
            save_tree("sample", tree_to_save, path=out_file)
            self.assertTrue(out_file.exists())
            content = out_file.read_text()
            self.assertTrue(content.startswith("# Project tree — managed by scripts/project_tree.py"))
            self.assertIn("project: sample", content)
            self.assertIn("updated:", content)

    def test_ascii_tree(self):
        rendered = ascii_tree(self.sample_tree)
        self.assertIn("sample — updated 2026-09-13 (raw)", rendered)
        self.assertIn("Sample Root [group] strong", rendered)
        self.assertIn("Child One [work] weak", rendered)
        self.assertIn("Grandchild One [work] discussing", rendered)


class TestMultiProposalAndHelpers(unittest.TestCase):
    """Tests for fragment-independent pending proposals and programmatic apply/reject helpers."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.tmp_dir.name)
        self.frag_dir = self.proj_dir / "fragments"
        self.frag_dir.mkdir(parents=True)

        self.root_file = self.proj_dir / "nodes.yaml"
        self.root_tree = {
            "project": "multi-test",
            "updated": "2026-09-13",
            "nodes": [
                {
                    "id": "root",
                    "title": "Multi Root",
                    "kind": "group",
                    "status": "strong",
                    "children": [
                        {
                            "id": "frag-alpha",
                            "title": "Alpha Subtree",
                            "kind": "group",
                            "data": {"subtree": "fragments/alpha.yaml"},
                        },
                        {
                            "id": "frag-beta",
                            "title": "Beta Subtree",
                            "kind": "group",
                            "data": {"subtree": "fragments/beta.yaml"},
                        },
                    ],
                }
            ],
        }
        self.root_file.write_text(dump_tree(self.root_tree))

        self.alpha_file = self.frag_dir / "alpha.yaml"
        self.alpha_tree = {
            "nodes": [
                {
                    "id": "alpha-task",
                    "title": "Alpha Task",
                    "kind": "work",
                    "status": "weak",
                }
            ]
        }
        self.alpha_file.write_text(dump_tree(self.alpha_tree))

        self.beta_file = self.frag_dir / "beta.yaml"
        self.beta_tree = {
            "nodes": [
                {
                    "id": "beta-task",
                    "title": "Beta Task",
                    "kind": "work",
                    "status": "weak",
                }
            ]
        }
        self.beta_file.write_text(dump_tree(self.beta_tree))

        self.dir_patch = patch.object(model, "project_dir", return_value=self.proj_dir)
        self.dir_patch.start()

    def tearDown(self):
        self.dir_patch.stop()
        self.tmp_dir.cleanup()

    def test_simultaneous_fragment_pending_proposals(self):
        alpha_proposed = self.frag_dir / "alpha.yaml.proposed"
        beta_proposed = self.frag_dir / "beta.yaml.proposed"

        alpha_proposed.write_text(dump_tree({"nodes": [{"id": "alpha-task", "title": "Alpha Task", "kind": "work", "status": "strong"}]}))
        beta_proposed.write_text(dump_tree({"nodes": [{"id": "beta-task", "title": "Beta Task", "kind": "work", "status": "discussing"}]}))

        proposals = list_pending_proposals("multi-test")
        self.assertEqual(len(proposals), 2)
        proposal_targets = [p[0] for p in proposals]
        self.assertIn("fragments/alpha.yaml", proposal_targets)
        self.assertIn("fragments/beta.yaml", proposal_targets)

    def test_get_pending_proposal_diff(self):
        alpha_proposed = self.frag_dir / "alpha.yaml.proposed"
        alpha_proposed.write_text(dump_tree({"nodes": [{"id": "alpha-task", "title": "Alpha Task", "kind": "work", "status": "strong"}]}))

        diff = get_pending_proposal_diff("multi-test", "fragments/alpha.yaml")
        self.assertTrue(bool(diff))
        self.assertIn("-  status: weak", diff)
        self.assertIn("+  status: strong", diff)

        # Non-pending fragment returns empty diff
        empty_diff = get_pending_proposal_diff("multi-test", "fragments/beta.yaml")
        self.assertEqual(empty_diff, "")

        # Non-pending root returns empty diff
        root_empty_diff = get_pending_proposal_diff("multi-test", None)
        self.assertEqual(root_empty_diff, "")

    def test_apply_pending_proposal_fragment_isolation(self):
        alpha_proposed = self.frag_dir / "alpha.yaml.proposed"
        beta_proposed = self.frag_dir / "beta.yaml.proposed"

        alpha_data = {"nodes": [{"id": "alpha-task", "title": "Alpha Task", "kind": "work", "status": "strong"}]}
        beta_data = {"nodes": [{"id": "beta-task", "title": "Beta Task", "kind": "work", "status": "discussing"}]}

        alpha_proposed.write_text(dump_tree(alpha_data))
        beta_proposed.write_text(dump_tree(beta_data))

        # Apply only alpha
        result = apply_pending_proposal("multi-test", "fragments/alpha.yaml")
        self.assertEqual(result["nodes"][0]["status"], "strong")

        # alpha proposed file is removed, target file is updated
        self.assertFalse(alpha_proposed.exists())
        import yaml
        saved_alpha = yaml.safe_load(self.alpha_file.read_text())
        self.assertEqual(saved_alpha["nodes"][0]["status"], "strong")

        # beta proposed file is untouched and still pending
        self.assertTrue(beta_proposed.exists())
        saved_beta = yaml.safe_load(self.beta_file.read_text())
        self.assertEqual(saved_beta["nodes"][0]["status"], "weak")

    def test_reject_pending_proposal_fragment_isolation(self):
        alpha_proposed = self.frag_dir / "alpha.yaml.proposed"
        beta_proposed = self.frag_dir / "beta.yaml.proposed"

        alpha_proposed.write_text(dump_tree({"nodes": [{"id": "alpha-task", "title": "Alpha Task", "kind": "work", "status": "strong"}]}))
        beta_proposed.write_text(dump_tree({"nodes": [{"id": "beta-task", "title": "Beta Task", "kind": "work", "status": "discussing"}]}))

        # Reject only alpha
        reject_pending_proposal("multi-test", "fragments/alpha.yaml")

        self.assertFalse(alpha_proposed.exists())
        self.assertTrue(beta_proposed.exists())

        # Original files untouched
        import yaml
        saved_alpha = yaml.safe_load(self.alpha_file.read_text())
        self.assertEqual(saved_alpha["nodes"][0]["status"], "weak")

    def test_root_pending_proposal_lifecycle(self):
        root_proposed = self.proj_dir / "nodes.yaml.proposed"
        modified_tree = copy.deepcopy(self.root_tree)
        modified_tree["nodes"][0]["title"] = "Updated Multi Root"
        root_proposed.write_text(dump_tree(modified_tree))

        diff = get_pending_proposal_diff("multi-test", None)
        self.assertIn("Updated Multi Root", diff)

        # Apply root proposal
        applied = apply_pending_proposal("multi-test", None)
        self.assertEqual(applied["nodes"][0]["title"], "Updated Multi Root")
        self.assertFalse(root_proposed.exists())

        import yaml
        saved_root = yaml.safe_load(self.root_file.read_text())
        self.assertEqual(saved_root["nodes"][0]["title"], "Updated Multi Root")

        # Stage another root proposal and reject it
        root_proposed.write_text(dump_tree(modified_tree))
        self.assertTrue(root_proposed.exists())
        reject_pending_proposal("multi-test", None)
        self.assertFalse(root_proposed.exists())

    def test_apply_or_reject_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            apply_pending_proposal("multi-test", "fragments/nonexistent.yaml")
        with self.assertRaises(FileNotFoundError):
            reject_pending_proposal("multi-test", "fragments/nonexistent.yaml")
        with self.assertRaises(FileNotFoundError):
            apply_pending_proposal("multi-test", None)
        with self.assertRaises(FileNotFoundError):
            reject_pending_proposal("multi-test", None)


if __name__ == "__main__":
    unittest.main()

