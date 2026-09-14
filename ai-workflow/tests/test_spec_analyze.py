"""Tests for spec_analyze model and CLI (claims c1 abort_missing, c2 implement_gate)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spec_analyze.model import (
    AnalyzeAbort,
    analyze_blocks_implement,
    analyze_paths,
    complete_analyze,
    run_analyze,
    skip_analyze,
)
from spec_analyze.cli import main as analyze_main

IMPLEMENT_SKILL = (
    Path(__file__).resolve().parents[1] / ".cursor" / "skills" / "implement" / "SKILL.md"
)

CONTRACT = """# Scope Contract: Test

## GOAL
Ship the analyze gate with mapped claims.

## IN
- spec-analyze skill, MCP tools, and CLI

## OUT
- Cockpit findings UI

## MUST
- Persist run status under the project dir

## MUST NOT
- Modify claims JSON during an analyze run

## VERIFY
- [ ] python3 -m pytest tests/test_spec_analyze.py -q -k abort_missing
"""

CLAIMS = {
    "project": "p",
    "node": "n",
    "goal": "Ship the analyze gate with mapped claims.",
    "in": ["spec-analyze skill, MCP tools, and CLI"],
    "out": ["Cockpit findings UI"],
    "claims": [
        {
            "id": "c1",
            "kind": "verify",
            "text": "python3 -m pytest tests/test_spec_analyze.py -q -k abort_missing",
            "decision": "approved",
        },
        {
            "id": "c2",
            "kind": "must",
            "text": "Persist run status under the project dir",
            "decision": "approved",
        },
        {
            "id": "c3",
            "kind": "must_not",
            "text": "Modify claims JSON during an analyze run",
            "decision": "approved",
        },
    ],
    "goal_approved": True,
}


def _write_claims(base: Path, node: str = "n", extra: dict | None = None) -> Path:
    path = base / "claims" / f"{node}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(CLAIMS)
    doc["node"] = node
    if extra:
        doc.update(extra)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def _write_contract(base: Path, node: str = "n", text: str = CONTRACT) -> Path:
    path = base / "specs" / f"{node}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestAbortMissing(unittest.TestCase):
    """c1: missing claims JSON or assembled contract refuses complete."""

    def test_abort_missing_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_contract(base)
            with patch("project_tree.model.project_dir", return_value=base):
                with self.assertRaises(AnalyzeAbort) as ctx:
                    complete_analyze("p", "n")
                msg = str(ctx.exception).lower()
                self.assertIn("assemble", msg)
                self.assertIn("skip", msg)
                self.assertFalse((base / "analyze" / "n.findings.json").exists())
                self.assertFalse((base / "analyze" / "n.analyze.json").exists())

    def test_abort_missing_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_claims(base)
            with patch("project_tree.model.project_dir", return_value=base):
                with self.assertRaises(AnalyzeAbort) as ctx:
                    complete_analyze("p", "n")
                msg = str(ctx.exception).lower()
                self.assertIn("assemble", msg)
                self.assertIn("skip", msg)
                self.assertFalse((base / "analyze" / "n.findings.json").exists())

    def test_abort_missing_cli_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_contract(base)
            with patch("project_tree.model.project_dir", return_value=base):
                rc = analyze_main(["complete", "p", "n"])
            self.assertNotEqual(rc, 0)
            self.assertFalse((base / "analyze" / "n.findings.json").exists())


class TestImplementGate(unittest.TestCase):
    """c2: persist complete/skip; Phase 1 stops when missing or in_progress."""

    def test_implement_gate_blocks_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                msg = analyze_blocks_implement("p", "n")
                self.assertIsNotNone(msg)
                self.assertIn("missing", msg.lower())

    def test_implement_gate_blocks_in_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_claims(base)
            _write_contract(base)
            with patch("project_tree.model.project_dir", return_value=base):
                with patch("spec_analyze.model.constitution_path", return_value=None):
                    run_analyze("p", "n")
                status = json.loads((base / "analyze" / "n.analyze.json").read_text())
                self.assertEqual(status["status"], "in_progress")
                msg = analyze_blocks_implement("p", "n")
                self.assertIsNotNone(msg)
                self.assertIn("in_progress", msg.lower())

    def test_implement_gate_persists_complete_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                skip_analyze("p", "n")
                status_path = base / "analyze" / "n.analyze.json"
                self.assertTrue(status_path.is_file())
                self.assertEqual(json.loads(status_path.read_text())["status"], "skipped")
                self.assertIsNone(analyze_blocks_implement("p", "n"))

            _write_claims(base)
            _write_contract(base)
            with patch("project_tree.model.project_dir", return_value=base):
                with patch("spec_analyze.model.constitution_path", return_value=None):
                    complete_analyze("p", "n", status="complete")
                status_path = base / "analyze" / "n.analyze.json"
                self.assertTrue(status_path.is_file())
                self.assertEqual(json.loads(status_path.read_text())["status"], "complete")
                self.assertTrue((base / "analyze" / "n.findings.json").is_file())
                self.assertIsNone(analyze_blocks_implement("p", "n"))

    def test_implement_gate_allows_complete_with_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            analyze_dir = base / "analyze"
            analyze_dir.mkdir()
            (analyze_dir / "n.findings.json").write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "id": "f1",
                                "category": "constitution",
                                "severity": "CRITICAL",
                                "summary": "Constitution MUST conflict",
                            }
                        ],
                        "critical_count": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (analyze_dir / "n.analyze.json").write_text(
                json.dumps(
                    {
                        "project": "p",
                        "node_id": "n",
                        "status": "complete",
                        "critical_count": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("project_tree.model.project_dir", return_value=base):
                self.assertIsNone(analyze_blocks_implement("p", "n"))

    def test_implement_gate_skill_phase1(self):
        text = IMPLEMENT_SKILL.read_text(encoding="utf-8")
        self.assertIn("Analyze gate", text)
        self.assertIn("complete", text)
        self.assertIn("skipped", text)
        self.assertIn("in_progress", text)
        self.assertIn("missing", text)
        self.assertIn("CRITICAL", text)
        self.assertIn("do not hard-block", text.lower())


class TestAnalyzeRun(unittest.TestCase):
    def test_complete_without_plan_or_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            claims_path = _write_claims(base)
            contract_path = _write_contract(base)
            claims_before = claims_path.read_text()
            contract_before = contract_path.read_text()
            with patch("project_tree.model.project_dir", return_value=base):
                with patch("spec_analyze.model.constitution_path", return_value=None):
                    status = complete_analyze("p", "n")
            self.assertEqual(status["status"], "complete")
            findings = json.loads((base / "analyze" / "n.findings.json").read_text())
            self.assertIn("findings", findings)
            self.assertEqual(
                set(findings["checks"]),
                {"consistency", "coverage", "clarification", "constitution"},
            )
            for item in findings["findings"]:
                self.assertIn(item["severity"], {"CRITICAL", "HIGH", "MEDIUM", "LOW"})
                self.assertIn(
                    item["category"],
                    {"consistency", "coverage", "clarification", "constitution"},
                )
            self.assertEqual(claims_path.read_text(), claims_before)
            self.assertEqual(contract_path.read_text(), contract_before)
            self.assertFalse((base / "plan.md").exists())
            self.assertFalse((base / "tasks.md").exists())

    def test_skip_without_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                rc = analyze_main(["skip", "p", "n"])
            self.assertEqual(rc, 0)
            self.assertEqual(
                json.loads((base / "analyze" / "n.analyze.json").read_text())["status"],
                "skipped",
            )
            self.assertFalse((base / "analyze" / "n.findings.json").exists())

    def test_paths_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                rc = analyze_main(["paths", "p", "n", "--json"])
                self.assertEqual(rc, 0)
                paths = analyze_paths("p", "n")
                self.assertTrue(str(paths["findings_json"]).endswith("n.findings.json"))
                self.assertTrue(str(paths["status_json"]).endswith("n.analyze.json"))


if __name__ == "__main__":
    unittest.main()
