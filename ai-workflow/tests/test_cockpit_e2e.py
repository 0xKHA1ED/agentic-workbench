"""End-to-end cockpit integration tests.

Starts tree_server.py as a real subprocess on a free port and exercises
REST endpoints, SSE streaming, proposal lifecycle, and claims triage over
actual TCP connections.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


# Absolute path to tree_server.py
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SERVER_SCRIPT = SCRIPTS_DIR / "tree_server.py"
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 10.0) -> bool:
    """Poll until the server accepts connections or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


import yaml

SCRIPTS_PATH = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)


class TestCockpitE2E(unittest.TestCase):
    """Full end-to-end tests against a real tree_server subprocess."""

    @classmethod
    def setUpClass(cls):
        # Create a temporary project directory with nodes.yaml
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._proj_dir = Path(cls._tmp_dir.name)
        cls._proj_name = f"e2e-test-{os.getpid()}"

        # Write a minimal valid nodes.yaml
        nodes_data = {
            "project": cls._proj_name,
            "nodes": [
                {
                    "id": "root",
                    "title": "E2E Root",
                    "kind": "goal",
                    "status": "active",
                    "data": {
                        "verification": {"command": "echo e2e-pass"},
                    },
                },
                {
                    "id": "child-node",
                    "title": "Child Node",
                    "kind": "task",
                    "status": "weak",
                    "parent": "root",
                },
            ],
        }
        with (cls._proj_dir / "nodes.yaml").open("w") as f:
            yaml.safe_dump(nodes_data, f)

        # Symlink into examples/ so list_projects() discovers it
        cls._symlink = EXAMPLES_DIR / cls._proj_name
        cls._symlink.symlink_to(cls._proj_dir)

        # Find a free port and start the server
        cls._port = _find_free_port()
        cls._proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), str(cls._port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not _wait_for_server(cls._port):
            cls._proc.kill()
            stdout, stderr = cls._proc.communicate(timeout=5)
            raise RuntimeError(
                f"Server failed to start on port {cls._port}.\n"
                f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
            )

    @classmethod
    def tearDownClass(cls):
        cls._proc.terminate()
        try:
            cls._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls._proc.kill()
            cls._proc.wait(timeout=5)
        # Remove symlink
        if cls._symlink.is_symlink():
            cls._symlink.unlink()
        cls._tmp_dir.cleanup()

    # ── Helpers ──────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self._port}{path}"

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = urllib.request.Request(self._url(path), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                body = err.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = body
                return err.code, data

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url(path),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                body = err.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = body
                return err.code, data

    def _get_raw(self, path: str) -> tuple[int, str, str]:
        req = urllib.request.Request(self._url(path), method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ct = resp.getheader("Content-Type")
            body = resp.read().decode("utf-8")
            return resp.status, ct, body

    # ── Tests ────────────────────────────────────────────────────────

    def test_01_get_projects(self):
        """Server lists projects including our temp project."""
        status, data = self._get_json("/api/projects")
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertIn(self._proj_name, data)

    def test_02_get_tree(self):
        """Fetch the tree for our project."""
        status, data = self._get_json(f"/api/tree/{self._proj_name}")
        self.assertEqual(status, 200)
        self.assertEqual(data["project"], self._proj_name)
        self.assertIn("nodes", data)
        ids = [n["id"] for n in data["nodes"]]
        self.assertIn("root", ids)

    def test_03_static_index_html(self):
        """Server serves the cockpit HTML."""
        status, ct, body = self._get_raw("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ct)
        self.assertIn("id=\"cockpit-layout\"", body)

    def test_04_static_styles_css(self):
        """Server serves the cockpit CSS."""
        status, ct, body = self._get_raw("/styles.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ct)

    def test_05_static_app_js(self):
        """Server serves the cockpit JS."""
        status, ct, body = self._get_raw("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("state = {", body)

    def test_06_sse_connect(self):
        """SSE endpoint delivers connected event."""
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        try:
            conn.request("GET", f"/api/events/{self._proj_name}")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertEqual(
                resp.getheader("Content-Type"),
                "text/event-stream; charset=utf-8",
            )

            # Read the first SSE event
            event_name, data = self._read_sse_event(resp)
            self.assertEqual(event_name, "connected")
            self.assertEqual(data, {"project": self._proj_name})
        finally:
            conn.close()

    def test_07_proposals_empty(self):
        """No proposals initially."""
        status, data = self._get_json(f"/api/proposals/{self._proj_name}")
        self.assertEqual(status, 200)
        self.assertEqual(data["proposals"], [])

    def test_08_proposal_lifecycle_create_and_apply(self):
        """Create a proposal via mutate, verify it appears, then apply it."""
        # Create proposal via add_child mutation
        status, data = self._post_json(
            "/api/mutate",
            {
                "project": self._proj_name,
                "target_node_id": "root",
                "operation": "add_child",
                "payload": {"id": "e2e-added", "title": "E2E Added Child", "kind": "task"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "staged")

        # Verify proposal appears
        status, data = self._get_json(f"/api/proposals/{self._proj_name}")
        self.assertEqual(status, 200)
        self.assertGreater(len(data["proposals"]), 0)
        self.assertIn("e2e-added", data["proposals"][0]["diff"])

        # Apply proposal
        status, data = self._post_json(
            "/api/proposals/apply",
            {"project": self._proj_name, "fragment": None},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "applied")

        # Verify tree reflects the mutation (add_child nests under parent)
        status, data = self._get_json(f"/api/tree/{self._proj_name}")
        self.assertEqual(status, 200)
        root_node = next(n for n in data["nodes"] if n["id"] == "root")
        child_ids = [c["id"] for c in root_node.get("children", [])]
        self.assertIn("e2e-added", child_ids)

    def test_09_proposal_create_and_reject(self):
        """Create a proposal and reject it."""
        # Mutate to create a proposal (set_status on root)
        status, data = self._post_json(
            "/api/mutate",
            {
                "project": self._proj_name,
                "target_node_id": "root",
                "operation": "set_status",
                "payload": {"status": "strong"},
            },
        )
        self.assertEqual(status, 200)

        # Reject proposal
        status, data = self._post_json(
            "/api/proposals/reject",
            {"project": self._proj_name, "fragment": None},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "rejected")

        # Verify tree was NOT changed (root should still be active)
        status, data = self._get_json(f"/api/tree/{self._proj_name}")
        self.assertEqual(status, 200)
        root_node = next(n for n in data["nodes"] if n["id"] == "root")
        self.assertNotEqual(root_node.get("status"), "strong")

    def test_10_claims_triage(self):
        """Stage claims and triage them."""
        claims_dir = self._proj_dir / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claims_data = {
            "project": self._proj_name,
            "node_id": "root",
            "claims": [
                {
                    "id": "e2e-c1",
                    "kind": "verify",
                    "text": "E2E root is stable",
                    "decision": "pending",
                },
                {
                    "id": "e2e-c2",
                    "kind": "verify",
                    "text": "E2E root passes tests",
                    "decision": "pending",
                },
            ],
        }
        with (claims_dir / "root.json").open("w") as f:
            json.dump(claims_data, f)

        # Fetch claims
        status, data = self._get_json(f"/api/claims/{self._proj_name}/root")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["claims"]), 2)

        # Triage first claim as approved
        status, data = self._post_json(
            "/api/claims/triage",
            {
                "project": self._proj_name,
                "node_id": "root",
                "claim_id": "e2e-c1",
                "decision": "approved",
            },
        )
        self.assertEqual(status, 200)
        triaged = next(c for c in data["claims"] if c["id"] == "e2e-c1")
        self.assertEqual(triaged["decision"], "approved")
        self.assertIn("triaged_at", triaged)

        # Triage second claim as rejected
        status, data = self._post_json(
            "/api/claims/triage",
            {
                "project": self._proj_name,
                "node_id": "root",
                "claim_id": "e2e-c2",
                "decision": "rejected",
            },
        )
        self.assertEqual(status, 200)
        triaged = next(c for c in data["claims"] if c["id"] == "e2e-c2")
        self.assertEqual(triaged["decision"], "rejected")

    def test_11_verify_execution(self):
        """Verification command runs and returns results."""
        status, data = self._post_json(
            "/api/verify",
            {"project": self._proj_name, "node_id": "root"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["exit_code"], 0)
        self.assertIn("e2e-pass", data["stdout"])

    def test_12_verify_node_not_found(self):
        """Verification of nonexistent node returns 404."""
        status, data = self._post_json(
            "/api/verify",
            {"project": self._proj_name, "node_id": "nonexistent-node"},
        )
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_13_decay_scan_endpoint(self):
        """Decay scan endpoint returns scan summary for a project."""
        status, data = self._post_json(
            "/api/decay-scan",
            {"project": self._proj_name, "dry_run": True},
        )
        self.assertEqual(status, 200)
        self.assertIn("scanned", data)
        self.assertIn("decayed", data)
        self.assertIn("refreshed", data)
        self.assertIn("nodes", data)

    def test_13b_node_status_hud(self):
        """GET /api/node returns the unified read-only Node HUD payload (Epic A/C)."""
        status, data = self._get_json(f"/api/node/{self._proj_name}/root")
        self.assertEqual(status, 200)
        self.assertEqual(data["node_id"], "root")
        self.assertTrue(data["read_only"])
        self.assertIn("gate_states", data)
        for key in ("contract_present", "verify_present", "analyze_status"):
            self.assertIn(key, data["gate_states"])

    def test_13c_node_status_missing_returns_404(self):
        """GET /api/node for an unknown node returns 404 (Epic A/C)."""
        status, data = self._get_json(f"/api/node/{self._proj_name}/nonexistent-node")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_14_sse_detects_file_change(self):
        """SSE stream fires tree_changed when nodes.yaml is modified."""
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        try:
            conn.request("GET", f"/api/events/{self._proj_name}")
            resp = conn.getresponse()
            event, _ = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Modify nodes.yaml
            time.sleep(0.1)
            nodes_data = {
                "project": self._proj_name,
                "nodes": [
                    {
                        "id": "root",
                        "title": "SSE Changed Root",
                        "kind": "goal",
                        "status": "active",
                        "data": {"verification": {"command": "echo e2e-pass"}},
                    },
                ],
            }
            with (self._proj_dir / "nodes.yaml").open("w") as f:
                yaml.safe_dump(nodes_data, f)

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": self._proj_name})
        finally:
            conn.close()

    # ── SSE helper ───────────────────────────────────────────────────

    def _read_sse_event(self, resp) -> tuple:
        event_name = None
        data_lines = []
        while True:
            line = resp.readline()
            if not line:
                break
            text = line.decode("utf-8").rstrip("\r\n")
            if not text:
                break
            if text.startswith("event:"):
                event_name = text.split(":", 1)[1].strip()
            elif text.startswith("data:"):
                data_lines.append(text.split(":", 1)[1].strip())
        raw_data = "\n".join(data_lines)
        try:
            data_obj = json.loads(raw_data) if raw_data else None
        except Exception:
            data_obj = raw_data
        return event_name, data_obj


if __name__ == "__main__":
    unittest.main()
