"""Tests for plan_paths model and CLI."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from plan_paths.cli import main as plan_main
from plan_paths.model import init_plan, plan_paths, plan_rel, validate_node_id


class TestPlanRel(unittest.TestCase):
    def test_canonical_rel(self):
        self.assertEqual(plan_rel("ref-p2-technical-plan"), "plans/ref-p2-technical-plan.plan.md")

    def test_rejects_traversal(self):
        with self.assertRaises(ValueError):
            validate_node_id("../etc")
        with self.assertRaises(ValueError):
            plan_rel("foo/bar")


class TestPlanArtifacts(unittest.TestCase):
    def test_paths_and_init_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                paths = plan_paths("p", "my-node")
                self.assertFalse(paths["exists"])
                self.assertEqual(paths["plan_rel"], "plans/my-node.plan.md")
                self.assertEqual(Path(paths["plan_md"]), base / "plans" / "my-node.plan.md")

                first = init_plan("p", "my-node", title="Demo")
                self.assertTrue(first["created"])
                self.assertTrue(first["exists"])
                text = Path(first["plan_md"]).read_text(encoding="utf-8")
                self.assertIn("HOW only", text)
                self.assertIn("specs/my-node.md", text)
                self.assertIn("Technical Plan: Demo", text)
                self.assertNotIn("## GOAL", text)

                Path(first["plan_md"]).write_text("custom how\n", encoding="utf-8")
                second = init_plan("p", "my-node")
                self.assertFalse(second["created"])
                self.assertFalse(second["written"])
                self.assertEqual(Path(second["plan_md"]).read_text(encoding="utf-8"), "custom how\n")


class TestPlanCLI(unittest.TestCase):
    def test_paths_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta"
            meta.mkdir()
            (meta / "nodes.yaml").write_text(
                "project: meta\nnodes:\n- id: root\n  title: R\n  kind: group\n  children:\n"
                "  - id: kid\n    title: Kid\n    kind: work\n    data:\n"
                "      plan: plans/kid.plan.md\n",
                encoding="utf-8",
            )
            buf = StringIO()
            with patch("project_tree.model.PACKAGE_ROOT", Path(tmp)):
                with patch("project_tree.model.host_root", return_value=Path(tmp)):
                    with patch("sys.stdout", buf):
                        rc = plan_main(["paths", "meta", "kid", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["plan_rel"], "plans/kid.plan.md")
            self.assertEqual(payload["data_plan"], "plans/kid.plan.md")
            self.assertEqual(payload["link"], {"plan": "plans/kid.plan.md"})
            self.assertFalse(payload["exists"])

    def test_paths_rejects_slash(self):
        err = StringIO()
        with patch("sys.stderr", err):
            rc = plan_main(["paths", "meta", "a/b"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid node_id", err.getvalue())


if __name__ == "__main__":
    unittest.main()
