"""Tests for constitution.md, constitution_path, and workflow_get_constitution."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import workflow_mcp
from spec_clarify.model import (
    CONSTITUTION_EXCERPT_LIMIT,
    constitution_excerpt,
    constitution_path,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION_MD = PACKAGE_ROOT / "meta" / "constitution.md"
CONSTITUTION_SKILL = PACKAGE_ROOT / ".cursor" / "skills" / "constitution" / "SKILL.md"

MUST_PRINCIPLES = (
    "Tree is memory",
    "Weak default",
    "Falsifiable VERIFY",
    "Clarify before claims",
    "Analyze before implement",
    "User-only strong",
    "MCP / CLI persistence",
)


class TestConstitutionDocument(unittest.TestCase):
    def test_constitution_md_exists_with_must_should(self):
        self.assertTrue(CONSTITUTION_MD.is_file())
        text = CONSTITUTION_MD.read_text(encoding="utf-8")
        self.assertIn("## MUST", text)
        self.assertIn("## SHOULD", text)
        self.assertIn("## Governance", text)
        self.assertIn("**Version**", text)
        for title in MUST_PRINCIPLES:
            self.assertIn(title, text)

    def test_constitution_skill_create_review_and_load_flows(self):
        self.assertTrue(CONSTITUTION_SKILL.is_file())
        text = CONSTITUTION_SKILL.read_text(encoding="utf-8")
        self.assertIn("## CREATE mode", text)
        self.assertIn("## REVIEW mode", text)
        self.assertIn("workflow_get_constitution", text)
        self.assertIn("`/spec-clarify`", text)
        self.assertIn("`/spec-analyze`", text)
        self.assertIn("`/implement`", text)


class TestConstitutionPath(unittest.TestCase):
    def test_meta_resolves_package_constitution(self):
        path = constitution_path("meta")
        self.assertIsNotNone(path)
        self.assertEqual(path.resolve(), CONSTITUTION_MD.resolve())

    def test_project_local_constitution_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            local = proj / "constitution.md"
            local.write_text("# Local Constitution\n\n## MUST\n", encoding="utf-8")
            with patch("spec_clarify.model.project_tree_model.project_dir", return_value=proj):
                resolved = constitution_path("any")
            self.assertEqual(resolved, local)

    def test_missing_returns_none_when_fallbacks_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            with patch("spec_clarify.model.project_tree_model.project_dir", return_value=empty):
                with patch("spec_clarify.model.PACKAGE_ROOT", empty):
                    with patch("spec_clarify.model.host_root", return_value=empty):
                        self.assertIsNone(constitution_path("ghost"))
                        self.assertIsNone(constitution_excerpt("ghost"))

    def test_excerpt_truncates(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            body = "x" * (CONSTITUTION_EXCERPT_LIMIT + 50)
            (proj / "constitution.md").write_text(body, encoding="utf-8")
            with patch("spec_clarify.model.project_tree_model.project_dir", return_value=proj):
                excerpt = constitution_excerpt("any")
            self.assertIsNotNone(excerpt)
            self.assertTrue(excerpt.endswith("…"))
            self.assertEqual(len(excerpt), CONSTITUTION_EXCERPT_LIMIT + 1)


class TestWorkflowGetConstitution(unittest.TestCase):
    def setUp(self):
        self.server = workflow_mcp.default_server

    def _call_tool(self, name: str, arguments: dict):
        req = {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        return self.server.handle_message(req)

    def test_tool_registered(self):
        req = {"jsonrpc": "2.0", "id": 301, "method": "tools/list"}
        resp = self.server.handle_message(req)
        tools = {t["name"]: t for t in resp.get("result", {}).get("tools", [])}
        self.assertIn("workflow_get_constitution", tools)
        schema = tools["workflow_get_constitution"]["inputSchema"]
        self.assertIn("project", schema["properties"])
        self.assertEqual(schema["required"], ["project"])

    def test_meta_returns_path_and_excerpt(self):
        payload = workflow_mcp.workflow_get_constitution("meta")
        self.assertTrue(payload["exists"])
        self.assertEqual(Path(payload["constitution_path"]).resolve(), CONSTITUTION_MD.resolve())
        self.assertIsNotNone(payload["constitution_excerpt"])
        self.assertIn("## MUST", payload["constitution_excerpt"])
        self.assertIn("Tree is memory", payload["constitution_excerpt"])
        self.assertIn("User-only strong", payload["constitution_excerpt"])

        resp = self._call_tool("workflow_get_constitution", {"project": "meta"})
        self.assertFalse(resp.get("result", {}).get("isError"))
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(data["project"], "meta")
        self.assertTrue(data["exists"])
        self.assertEqual(data["constitution_path"], payload["constitution_path"])

    def test_missing_is_not_error(self):
        with patch.object(workflow_mcp, "constitution_path", return_value=None):
            with patch.object(workflow_mcp, "constitution_excerpt", return_value=None):
                payload = workflow_mcp.workflow_get_constitution("ghost")
        self.assertEqual(
            payload,
            {
                "project": "ghost",
                "constitution_path": None,
                "constitution_excerpt": None,
                "exists": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
