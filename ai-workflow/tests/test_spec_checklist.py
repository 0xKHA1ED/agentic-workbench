"""Tests for spec_checklist generate / validate / implement-gate status."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spec_checklist.cli import main as checklist_main
from spec_checklist.model import (
    checklist_blocks_implement,
    generate_checklist,
    parse_checklist_items,
    scan_checklist_status,
    validate_checklist_text,
)


class TestGenerateAndValidate(unittest.TestCase):
    def test_generate_from_claims_is_unchecked_with_chk_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            claims_dir = base / "claims"
            claims_dir.mkdir()
            claims_dir.joinpath("n1.json").write_text(
                json.dumps(
                    {
                        "project": "p",
                        "node": "n1",
                        "title": "Demo node",
                        "goal": "Ship checklist gate",
                        "in": ["scripts/spec_checklist/"],
                        "out": ["Cockpit UI"],
                        "claims": [
                            {
                                "id": "c1",
                                "kind": "verify",
                                "text": "pytest tests/test_spec_checklist.py exits 0",
                                "decision": "approved",
                                "check_command": "python3 -m pytest tests/test_spec_checklist.py -q",
                            },
                            {
                                "id": "c2",
                                "kind": "must",
                                "text": "Leave generated checkboxes unchecked",
                                "decision": "approved",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    result = generate_checklist("p", "n1")
            self.assertTrue(result["created"])
            self.assertEqual(result["checked"], 0)
            text = Path(result["path"]).read_text(encoding="utf-8")
            items = validate_checklist_text(text, require_unchecked=True)
            self.assertGreaterEqual(len(items), 8)
            self.assertTrue(all(it["id"] and it["id"].startswith("CHK") for it in items))
            self.assertIn("Claim c1", text)
            self.assertNotRegex(text, r"^- \[x\]", "generation must not pre-check boxes")

    def test_generate_from_assembled_spec_without_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            specs = base / "specs"
            specs.mkdir()
            specs.joinpath("n2.md").write_text(
                "# Scope Contract: n2\n\n## GOAL\n\nObservable outcome\n",
                encoding="utf-8",
            )
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    result = generate_checklist("p", "n2")
            text = Path(result["path"]).read_text(encoding="utf-8")
            self.assertIn("assembled spec", text)
            validate_checklist_text(text, require_unchecked=True)

    def test_append_preserves_user_checked_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    first = generate_checklist("p", "n3")
                    path = Path(first["path"])
                    original = path.read_text(encoding="utf-8")
                    flipped = original.replace("- [ ] CHK001 ", "- [x] CHK001 ", 1)
                    path.write_text(flipped, encoding="utf-8")
                    claims_dir = base / "claims"
                    claims_dir.mkdir()
                    claims_dir.joinpath("n3.json").write_text(
                        json.dumps(
                            {
                                "goal": "Add a claim later",
                                "claims": [
                                    {
                                        "id": "c9",
                                        "kind": "must_not",
                                        "text": "Toggle checklist markers from the agent",
                                        "decision": "approved",
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    second = generate_checklist("p", "n3")
            self.assertFalse(second["created"])
            self.assertGreater(second["appended"], 0)
            text = path.read_text(encoding="utf-8")
            items = parse_checklist_items(text)
            chk001 = next(it for it in items if it["id"] == "CHK001")
            self.assertTrue(chk001["checked"])
            new_ids = [it for it in items if it["id"] != "CHK001"]
            self.assertTrue(any(not it["checked"] for it in new_ids))
            self.assertIn("Claim c9", text)


class TestStatusGate(unittest.TestCase):
    def test_custom_unchecked_blocks_implement(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    generate_checklist("p", "n4", domain="ux")
                    status = scan_checklist_status("p", "n4")
                    self.assertTrue(status["read_only"])
                    self.assertTrue(status["blocks_implement"])
                    self.assertGreater(status["unchecked_custom"], 0)
                    self.assertIsNotNone(checklist_blocks_implement("p", "n4"))
                    path = Path(status["checklists"][0]["path"])
                    checked = path.read_text(encoding="utf-8").replace("- [ ] ", "- [x] ")
                    path.write_text(checked, encoding="utf-8")
                    status2 = scan_checklist_status("p", "n4")
                    self.assertFalse(status2["blocks_implement"])
                    self.assertIsNone(checklist_blocks_implement("p", "n4"))

    def test_absent_checklists_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("spec_checklist.model.project_dir", return_value=base):
                status = scan_checklist_status("p", "missing")
            self.assertEqual(status["overall"], "absent")
            self.assertFalse(status["blocks_implement"])


class TestChecklistCLI(unittest.TestCase):
    def test_generate_status_validate_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    rc = checklist_main(["generate", "p", "n5", "--json"])
                    self.assertEqual(rc, 0)
                    rc = checklist_main(["status", "p", "n5", "--json", "--gate"])
                    self.assertEqual(rc, 2)
                    req = base / "checklists" / "n5" / "requirements.md"
                    rc = checklist_main(["validate", str(req), "--require-unchecked"])
                    self.assertEqual(rc, 0)
                    req.write_text(req.read_text().replace("- [ ] CHK001 ", "- [x] CHK001 ", 1))
                    rc = checklist_main(["validate", str(req), "--require-unchecked"])
                    self.assertEqual(rc, 1)
                    rc = checklist_main(["validate", str(req)])
                    self.assertEqual(rc, 0)


class TestMcpChecklistStatus(unittest.TestCase):
    def test_workflow_checklist_status_is_read_only(self):
        import workflow_mcp

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("spec_checklist.model.project_dir", return_value=base):
                with patch("spec_discovery.model.project_dir", return_value=base):
                    generate_checklist("p", "n6")
                    before = (base / "checklists" / "n6" / "requirements.md").read_text()
                    payload = workflow_mcp.workflow_checklist_status("p", "n6")
                    after = (base / "checklists" / "n6" / "requirements.md").read_text()
            self.assertTrue(payload["read_only"])
            self.assertTrue(payload["blocks_implement"])
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
