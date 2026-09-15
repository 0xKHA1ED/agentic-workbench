"""Tests for executable execution schema on VERIFY claims."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from spec_discovery.assemble import build_markdown
from spec_discovery.model import normalize_document


def _base_doc(**overrides):
    doc = {
        "goal_approved": True,
        "title": "Execution Test",
        "goal": "Verify execution schema support",
        "claims": [
            {
                "id": "c1",
                "kind": "verify",
                "text": "Echo succeeds",
                "decision": "approved",
                "execution": {
                    "type": "command",
                    "command": "echo ok",
                },
            }
        ],
    }
    doc.update(overrides)
    return doc


class TestExecutionValidation(unittest.TestCase):
    def test_valid_command_execution_passes(self):
        doc = _base_doc()
        result = normalize_document(doc)
        self.assertEqual(result["claims"][0]["execution"]["type"], "command")

    def test_missing_command_raises(self):
        doc = _base_doc()
        doc["claims"][0]["execution"] = {"type": "command"}
        with self.assertRaises(ValueError) as ctx:
            normalize_document(doc)
        self.assertIn("command", str(ctx.exception).lower())

    def test_invalid_execution_type_raises(self):
        doc = _base_doc()
        doc["claims"][0]["execution"] = {
            "type": "manual_sensory",
            "command": "echo ok",
        }
        with self.assertRaises(ValueError) as ctx:
            normalize_document(doc)
        self.assertIn("type", str(ctx.exception).lower())

    def test_execution_on_non_verify_claim_raises(self):
        doc = _base_doc()
        doc["claims"][0]["kind"] = "must"
        with self.assertRaises(ValueError) as ctx:
            normalize_document(doc)
        self.assertIn("verify", str(ctx.exception).lower())


class TestExecutionAssembly(unittest.TestCase):
    def test_build_markdown_includes_executable_syntax(self):
        markdown = build_markdown(_base_doc())
        self.assertIn("check_type: command | `echo ok`", markdown)
        verify_section = markdown.split("## VERIFY")[1].split("## ACCEPTANCE")[0]
        self.assertIn("check_type: command | `echo ok`", verify_section)


class TestAssembleContractLink(unittest.TestCase):
    """Epic F — assemble stages (never auto-applies) a set-contract link."""

    def _make_project(self, tmp: Path):
        import yaml

        nodes = {
            "project": "linktest",
            "nodes": [
                {
                    "id": "root",
                    "title": "Root",
                    "kind": "group",
                    "status": "weak",
                    "data": {"subtree": "fragments/f.yaml"},
                }
            ],
        }
        (tmp / "nodes.yaml").write_text(yaml.safe_dump(nodes))
        frag_dir = tmp / "fragments"
        frag_dir.mkdir()
        frag = {"nodes": [{"id": "node-x", "title": "Node X", "kind": "work", "status": "weak"}]}
        (frag_dir / "f.yaml").write_text(yaml.safe_dump(frag))

    def test_propose_contract_link_stages_fragment_proposal(self):
        import tempfile
        from unittest.mock import patch

        from project_tree import model
        from spec_discovery.assemble import propose_contract_link

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            self._make_project(tmp)
            with patch.object(model, "project_dir", return_value=tmp):
                pending = propose_contract_link("linktest", "node-x", "meta/specs/node-x.md")
            self.assertTrue(pending.exists())
            self.assertIn("meta/specs/node-x.md", pending.read_text())
            # Staging never mutates the live fragment (human still applies).
            self.assertNotIn("contract", (tmp / "fragments" / "f.yaml").read_text())

    def test_propose_contract_link_unknown_node_raises(self):
        import tempfile
        from unittest.mock import patch

        from project_tree import model
        from spec_discovery.assemble import propose_contract_link

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            self._make_project(tmp)
            with patch.object(model, "project_dir", return_value=tmp):
                with self.assertRaises(ValueError):
                    propose_contract_link("linktest", "no-such-node", "meta/specs/x.md")


if __name__ == "__main__":
    unittest.main()
