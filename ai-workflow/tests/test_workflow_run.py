"""Epic E — resumable workflow runner: gates, resume, reject-abort, overlays, hooks, feature dirs."""

import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import workflow_run

WORKFLOW = PACKAGE_ROOT / "meta" / "workflows" / "daily-loop.yaml"


class TestWorkflowRunner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.feature_root = Path(self._tmp.name) / "specs"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, path="full", node="node-x"):
        return workflow_run.run(
            "p", node, WORKFLOW, path=path,
            state_dir=self.state_dir, feature_root=self.feature_root,
        )

    def _resume(self, decision, node="node-x"):
        return workflow_run.resume(
            "p", node, decision=decision, workflow_path=WORKFLOW, state_dir=self.state_dir,
        )

    def test_workflow_yaml_loads(self):
        wf = workflow_run.load_workflow(WORKFLOW)
        self.assertEqual(wf["name"], "daily-loop")
        ids = [s["id"] for s in wf["steps"]]
        self.assertIn("clarify", ids)
        self.assertIn("promote", ids)

    def test_run_pauses_at_first_gate(self):
        state = self._run()
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["current_step"], "clarify")

    def test_feature_dir_created(self):
        self._run()
        self.assertTrue((self.feature_root / "node-x" / "feature.json").is_file())

    def test_before_hook_recorded_at_gate(self):
        state = self._run()
        hooks = [h for h in state["history"] if h.get("hook") == "before" and h.get("step") == "clarify"]
        self.assertTrue(hooks)

    def test_resume_gate_requires_decision(self):
        self._run()
        with self.assertRaises(ValueError):
            self._resume(None)

    def test_resume_approve_advances_to_next_gate(self):
        self._run()
        state = self._resume("approve")
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["current_step"], "analyze")

    def test_full_run_reaches_completion_with_overlays_and_after_hook(self):
        self._run()
        self._resume("approve")   # clarify → analyze
        state = self._resume("approve")  # analyze → implement + overlays → promote
        self.assertEqual(state["current_step"], "promote")
        done_steps = [h["step"] for h in state["history"] if h.get("action") == "done"]
        self.assertIn("implement", done_steps)
        # Overlays inserted after implement.
        self.assertIn("verify", done_steps)
        self.assertIn("lint", done_steps)
        # after_implement hook recorded.
        after_hooks = [h for h in state["history"] if h.get("hook") == "after" and h.get("step") == "implement"]
        self.assertTrue(after_hooks)
        # Final approve completes.
        final = self._resume("approve")
        self.assertEqual(final["status"], "complete")

    def test_reject_aborts(self):
        self._run()
        state = self._resume("reject")
        self.assertEqual(state["status"], "aborted")

    def test_resume_after_abort_is_noop(self):
        self._run()
        self._resume("reject")
        state = self._resume("approve")
        self.assertEqual(state["status"], "aborted")

    def test_spike_path_skips_optional_gates(self):
        state = self._run(path="spike", node="spike-node")
        # spike skips clarify + spec + analyze; first (and only) gate is promote.
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["current_step"], "promote")
        self.assertIn("clarify", state["skipped"])
        self.assertIn("analyze", state["skipped"])

    def test_status_returns_persisted_state(self):
        self._run()
        st = workflow_run.status("p", "node-x", state_dir=self.state_dir)
        self.assertIsNotNone(st)
        self.assertEqual(st["current_step"], "clarify")

    def test_invalid_path_rejected(self):
        with self.assertRaises(ValueError):
            self._run(path="bogus")

    def test_overlays_apply_helper(self):
        steps = [{"id": "implement", "type": "step"}, {"id": "promote", "type": "gate"}]
        overlays = [{"after": "implement", "insert": [{"id": "verify", "type": "step"}]}]
        out = workflow_run.apply_overlays(steps, overlays)
        ids = [s["id"] for s in out]
        self.assertEqual(ids, ["implement", "verify", "promote"])


class TestWorkflowRunnerMCP(unittest.TestCase):
    """Epic E — runner exposed as MCP tools (registration + read-only status)."""

    def test_runner_tools_registered(self):
        import workflow_mcp

        tools = set(workflow_mcp.default_server.tools)
        self.assertIn("workflow_run", tools)
        self.assertIn("workflow_resume", tools)
        self.assertIn("workflow_status", tools)

    def test_status_no_run_marker(self):
        import workflow_mcp

        res = workflow_mcp.workflow_run_status("meta", "definitely-no-run-xyz-node")
        self.assertEqual(res["status"], "no_run")


if __name__ == "__main__":
    unittest.main()
