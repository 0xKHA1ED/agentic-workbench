"""Tests for spec_clarify model and CLI."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spec_clarify.model import (
    append_decision,
    clarify_blocks_claims,
    complete_clarify,
    infer_taxonomy_mode,
    load_decisions,
)
from spec_clarify.cli import main as clarify_main


class TestInferTaxonomy(unittest.TestCase):
    def test_tooling_from_pattern(self):
        self.assertEqual(
            infer_taxonomy_mode({"pattern": "scripts/spec_clarify/**"}),
            "tooling",
        )

    def test_full_default(self):
        self.assertEqual(infer_taxonomy_mode({"pattern": "services/foo/**"}), "full")

    def test_explicit_override(self):
        self.assertEqual(
            infer_taxonomy_mode({"clarify_taxonomy": "full", "pattern": "scripts/x"}),
            "full",
        )


class TestClarifyArtifacts(unittest.TestCase):
    def test_record_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = "testproj"
            node = "my-node"
            base = Path(tmp)

            with patch("project_tree.model.project_dir", return_value=base):
                doc = append_decision(
                    proj,
                    node,
                    question="What is OUT of scope?",
                    answer="Cockpit UI",
                    category="scope",
                    taxonomy_mode="tooling",
                )
                self.assertEqual(doc["questions_asked"], 1)

                done = complete_clarify(
                    proj,
                    node,
                    deferred_categories=["observability"],
                    outstanding_categories=[],
                    status="complete",
                )
                self.assertEqual(done["status"], "complete")

                decisions_path = base / "clarifications" / f"{node}.decisions.json"
                self.assertTrue(decisions_path.is_file())
                loaded = load_decisions(decisions_path)
                self.assertEqual(len(loaded["decisions"]), 1)

                md_path = base / "clarifications" / f"{node}.md"
                self.assertIn("Cockpit UI", md_path.read_text())
                self.assertIn("Deferred categories", md_path.read_text())

    def test_blocks_claims_when_needs_clarify(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                msg = clarify_blocks_claims("p", "n", {"needs_clarify": True})
                self.assertIsNotNone(msg)
                complete_clarify("p", "n", status="skipped")
                self.assertIsNone(clarify_blocks_claims("p", "n", {"needs_clarify": True}))


class TestClarifyCLI(unittest.TestCase):
    def test_paths_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta"
            meta.mkdir()
            (meta / "nodes.yaml").write_text(
                "project: meta\nnodes:\n- id: root\n  title: R\n  kind: group\n  children:\n"
                "  - id: kid\n    title: Kid\n    kind: work\n    data:\n      pattern: scripts/x\n",
                encoding="utf-8",
            )
            with patch("project_tree.model.PACKAGE_ROOT", Path(tmp)):
                with patch("project_tree.model.host_root", return_value=Path(tmp)):
                    rc = clarify_main(["paths", "meta", "kid", "--json"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
