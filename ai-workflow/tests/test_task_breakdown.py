"""Tests for task_breakdown: phased tasks.md generation and scoped implement parsing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from task_breakdown.cli import main as tasks_main
from task_breakdown.model import (
    TaskBreakdownError,
    generate_tasks_markdown,
    parse_tasks_markdown,
    scope_tasks,
    tasks_paths,
    write_tasks,
)


def _claims_doc(node: str = "demo-node") -> dict:
    return {
        "project": "p",
        "node": node,
        "node_id": node,
        "title": "Demo feature",
        "goal": "Ship a demo CLI that lists nodes",
        "in": ["scripts/demo.py", "tests/test_demo.py"],
        "out": ["tools/tree-viewer/"],
        "goal_approved": True,
        "claims": [
            {
                "id": "c1",
                "kind": "verify",
                "text": "pytest tests/test_demo.py -q exits 0",
                "decision": "approved",
                "check_command": "pytest tests/test_demo.py -q",
                "source": "scripts/demo.py",
            },
            {
                "id": "c2",
                "kind": "must",
                "text": "CLI prints node ids one per line",
                "decision": "approved",
                "source": "scripts/demo.py",
            },
            {
                "id": "c3",
                "kind": "must_not",
                "text": "Write tree YAML from the demo CLI",
                "decision": "approved",
                "source": "scripts/demo.py",
            },
            {
                "id": "c4",
                "kind": "verify",
                "text": "python3 scripts/demo.py --json emits a JSON array",
                "decision": "approved",
                "check_command": "python3 scripts/demo.py --json",
                "source": "scripts/demo.py",
            },
        ],
    }


def _spec_md(node: str = "demo-node") -> str:
    return (
        f"# Scope Contract: Demo feature\n\n"
        "## GOAL\n"
        "Ship a demo CLI that lists nodes\n\n"
        "## IN\n"
        "- scripts/demo.py\n"
        "- tests/test_demo.py\n\n"
        "## OUT\n"
        "- tools/tree-viewer/\n\n"
        "## MUST\n"
        "- CLI prints node ids one per line\n\n"
        "## MUST NOT\n"
        "- Write tree YAML from the demo CLI\n\n"
        "## VERIFY\n"
        "- [ ] pytest tests/test_demo.py -q exits 0\n"
        "- [ ] python3 scripts/demo.py --json emits a JSON array\n"
    )


class TestTasksPaths(unittest.TestCase):
    def test_paths_under_project_tasks_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                paths = tasks_paths("p", "demo-node")
            self.assertEqual(paths["tasks_md"], str(base / "tasks" / "demo-node.md"))
            self.assertEqual(paths["tasks_dir"], str(base / "tasks"))
            self.assertEqual(paths["claims_json"], str(base / "claims" / "demo-node.json"))
            self.assertEqual(paths["spec_md"], str(base / "specs" / "demo-node.md"))


class TestGenerateFromClaims(unittest.TestCase):
    def test_phased_template_from_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "claims").mkdir()
            (base / "claims" / "demo-node.json").write_text(
                json.dumps(_claims_doc()), encoding="utf-8"
            )
            (base / "specs").mkdir()
            (base / "specs" / "demo-node.md").write_text(_spec_md(), encoding="utf-8")
            with patch("project_tree.model.project_dir", return_value=base):
                md = generate_tasks_markdown("p", "demo-node")
            self.assertIn("# Tasks: Demo feature", md)
            self.assertIn("## Phase 1: Setup", md)
            self.assertIn("<!-- task-phase: id=setup index=1 -->", md)
            self.assertIn("## Phase 2: Foundational", md)
            self.assertIn("<!-- task-phase: id=foundational index=2 -->", md)
            self.assertIn("<!-- task-phase: id=c1 index=3 -->", md)
            self.assertIn("<!-- task-phase: id=c4 index=4 -->", md)
            self.assertIn("<!-- task-phase: id=polish index=5 -->", md)
            self.assertIn("scripts/demo.py", md)
            self.assertIn("tests/test_demo.py", md)
            self.assertRegex(md, r"- \[ \] T001 ")
            self.assertIn("[C1]", md)
            self.assertIn("[C4]", md)
            self.assertNotIn("TXXX", md)
            self.assertNotIn("SAMPLE TASKS", md)
            parsed = parse_tasks_markdown(md)
            ids = [t["id"] for t in parsed["tasks"]]
            self.assertEqual(ids, sorted(ids, key=lambda x: int(x[1:])))
            self.assertTrue(all(t["path"] for t in parsed["tasks"]))

    def test_generate_from_spec_when_claims_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "specs").mkdir()
            (base / "specs" / "solo.md").write_text(_spec_md("solo"), encoding="utf-8")
            with patch("project_tree.model.project_dir", return_value=base):
                md = generate_tasks_markdown("p", "solo")
            self.assertIn("## Phase 1: Setup", md)
            self.assertIn("<!-- task-phase:", md)
            self.assertIn("scripts/demo.py", md)

    def test_abort_writes_nothing_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                with self.assertRaises(TaskBreakdownError) as ctx:
                    write_tasks("p", "missing-node")
                self.assertRegex(str(ctx.exception).lower(), r"claims|spec|assemble")
            self.assertFalse((base / "tasks" / "missing-node.md").exists())

    def test_write_tasks_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "claims").mkdir()
            (base / "claims" / "demo-node.json").write_text(
                json.dumps(_claims_doc()), encoding="utf-8"
            )
            with patch("project_tree.model.project_dir", return_value=base):
                result = write_tasks("p", "demo-node")
            out = Path(result["tasks_md"])
            self.assertTrue(out.is_file())
            self.assertGreater(result["task_count"], 0)
            self.assertGreaterEqual(result["phase_count"], 3)


class TestParseAndScope(unittest.TestCase):
    SAMPLE = """# Tasks: Demo

## Phase 1: Setup (Shared Infrastructure)
<!-- task-phase: id=setup index=1 -->

- [ ] T001 Confirm claims JSON at claims/demo-node.json
- [x] T002 [P] Confirm spec at specs/demo-node.md

## Phase 2: Foundational (Blocking Prerequisites)
<!-- task-phase: id=foundational index=2 -->

- [ ] T003 Honor MUST: CLI prints node ids in scripts/demo.py

## Phase 3: Claim C1
<!-- task-phase: id=c1 index=3 -->

- [ ] T004 [C1] Implement verify in scripts/demo.py
- [ ] T005 [P] [C1] Add tests in tests/test_demo.py

## Phase 4: Polish & Cross-Cutting Concerns
<!-- task-phase: id=polish index=4 -->

- [ ] T006 [P] Honor MUST NOT in scripts/demo.py
"""

    def test_parse_phase_markers_and_checkboxes(self):
        parsed = parse_tasks_markdown(self.SAMPLE)
        self.assertEqual(len(parsed["phases"]), 4)
        self.assertEqual(parsed["phases"][0]["id"], "setup")
        self.assertEqual(parsed["phases"][1]["id"], "foundational")
        tasks = {t["id"]: t for t in parsed["tasks"]}
        self.assertFalse(tasks["T001"]["done"])
        self.assertTrue(tasks["T002"]["done"])
        self.assertTrue(tasks["T002"]["parallel"])
        self.assertEqual(tasks["T004"]["story"], "C1")
        self.assertEqual(tasks["T001"]["path"], "claims/demo-node.json")

    def test_scope_by_phase_index_and_id(self):
        parsed = parse_tasks_markdown(self.SAMPLE)
        by_index = scope_tasks(parsed, phase="2")
        self.assertEqual([t["id"] for t in by_index["tasks"]], ["T003"])
        by_id = scope_tasks(parsed, phase="setup")
        self.assertEqual([t["id"] for t in by_id["tasks"]], ["T001", "T002"])

    def test_scope_by_task_range(self):
        parsed = parse_tasks_markdown(self.SAMPLE)
        scoped = scope_tasks(parsed, tasks="T004-T005")
        self.assertEqual([t["id"] for t in scoped["tasks"]], ["T004", "T005"])
        self.assertEqual(scoped["phases"][0]["id"], "c1")


class TestTasksCLI(unittest.TestCase):
    def test_paths_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                with patch("sys.stdout") as _:
                    pass
            with patch("project_tree.model.project_dir", return_value=base):
                import io
                from contextlib import redirect_stdout

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = tasks_main(["paths", "p", "kid", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["tasks_md"].endswith("tasks/kid.md"))

    def test_generate_and_scope_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "claims").mkdir()
            (base / "claims" / "demo-node.json").write_text(
                json.dumps(_claims_doc()), encoding="utf-8"
            )
            import io
            from contextlib import redirect_stdout

            with patch("project_tree.model.project_dir", return_value=base):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = tasks_main(["generate", "p", "demo-node", "--json"])
                self.assertEqual(rc, 0)
                gen = json.loads(buf.getvalue())
                self.assertTrue(Path(gen["tasks_md"]).is_file())

                buf2 = io.StringIO()
                with redirect_stdout(buf2):
                    rc2 = tasks_main(["scope", "p", "demo-node", "--phase", "1", "--json"])
                self.assertEqual(rc2, 0)
                scoped = json.loads(buf2.getvalue())
                self.assertTrue(all(t["phase_id"] == "setup" for t in scoped["tasks"]))

    def test_generate_cli_aborts_without_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            import io
            from contextlib import redirect_stderr

            err = io.StringIO()
            with patch("project_tree.model.project_dir", return_value=base):
                with redirect_stderr(err):
                    rc = tasks_main(["generate", "p", "ghost"])
            self.assertEqual(rc, 1)
            self.assertFalse((base / "tasks" / "ghost.md").exists())


class TestWorkflowTasksPathsMCP(unittest.TestCase):
    def test_workflow_tasks_paths_registered(self):
        import workflow_mcp

        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        resp = workflow_mcp.default_server.handle_message(req)
        names = {t["name"] for t in resp.get("result", {}).get("tools", [])}
        self.assertIn("workflow_tasks_paths", names)

    def test_workflow_tasks_paths_call(self):
        import workflow_mcp

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch("project_tree.model.project_dir", return_value=base):
                resp = workflow_mcp.default_server.handle_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "workflow_tasks_paths",
                            "arguments": {"project": "p", "node_id": "n1"},
                        },
                    }
                )
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertTrue(data["tasks_md"].endswith("tasks/n1.md"))
        self.assertFalse(data["tasks_exists"])


if __name__ == "__main__":
    unittest.main()
