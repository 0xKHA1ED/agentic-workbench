"""Tests for idea_assess model and CLI."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from idea_assess.cli import main as assess_main
from idea_assess.model import (
    assessment_paths,
    handoff_for,
    init_assessment,
    normalize_slug,
    parse_verdict,
    slug_from_idea,
)


class TestSlug(unittest.TestCase):
    def test_normalize_kebab_and_strip_paths(self):
        self.assertEqual(normalize_slug("Offline Mode"), "offline-mode")
        self.assertEqual(normalize_slug("../etc/passwd"), "etc-passwd")
        self.assertEqual(normalize_slug("..."), "")

    def test_slug_from_idea_caps_words(self):
        self.assertEqual(
            slug_from_idea("Let users work offline and sync later"),
            "let-users-work-offline",
        )


class TestInitAndPaths(unittest.TestCase):
    def test_init_writes_intake_and_paths_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                doc = init_assessment("meta", "offline-mode", idea="Work offline")
                intake = Path(doc["intake_md"])
                self.assertTrue(intake.is_file())
                self.assertIn("Work offline", intake.read_text())
                self.assertTrue(doc["exists"]["intake"])
                self.assertFalse(doc["exists"]["decision"])
                self.assertIsNone(doc["verdict"])

                with self.assertRaises(FileExistsError):
                    init_assessment("meta", "offline-mode", idea="again")

                unique = init_assessment(
                    "meta", "offline-mode", idea="again", unique=True
                )
                self.assertEqual(unique["slug"], "offline-mode-2")

    def test_paths_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                init_assessment("meta", "cut-friction", idea="Cut onboarding")
                buf = StringIO()
                with redirect_stdout(buf):
                    rc = assess_main(["paths", "meta", "cut-friction", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["slug"], "cut-friction")
            self.assertTrue(payload["exists"]["intake"])
            self.assertIn("handoff", payload)

    def test_init_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                buf = StringIO()
                with redirect_stdout(buf):
                    rc = assess_main(
                        ["init", "meta", "demo-idea", "--idea", "Demo", "--json"]
                    )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())["slug"], "demo-idea")

    def test_empty_slug_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                with self.assertRaises(ValueError):
                    init_assessment("meta", "...", idea="")


class TestVerdictHandoff(unittest.TestCase):
    def test_parse_verdict(self):
        self.assertEqual(
            parse_verdict("- **Verdict**: go\n"),
            "go",
        )
        self.assertEqual(
            parse_verdict("**Verdict**: needs-clarification\n"),
            "needs-clarification",
        )
        self.assertIsNone(parse_verdict("# Decision\n\nnot yet\n"))

    def test_handoff_go_to_clarify_or_tree(self):
        attached = handoff_for("go", node_id="my-node")
        self.assertEqual(attached["skill"], "spec-clarify")
        fresh = handoff_for("go")
        self.assertEqual(fresh["skill"], "project-tree")
        self.assertIsNone(handoff_for("kill")["skill"])
        self.assertIsNone(handoff_for("needs-clarification")["skill"])

    def test_paths_reads_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                init_assessment("meta", "ship-it", idea="Ship it")
                paths = assessment_paths("meta", "ship-it")
                Path(paths["decision_md"]).write_text(
                    "# Decision\n\n- **Verdict**: go\n",
                    encoding="utf-8",
                )
                again = assessment_paths("meta", "ship-it")
                self.assertEqual(again["verdict"], "go")
                self.assertEqual(again["handoff"]["skill"], "project-tree")


class TestInitCliStdout(unittest.TestCase):
    def test_init_prints_intake_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                buf = StringIO()
                with redirect_stdout(buf):
                    rc = assess_main(["init", "meta", "cli-path", "--idea", "Hi"])
            self.assertEqual(rc, 0)
            self.assertIn("intake.md", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
