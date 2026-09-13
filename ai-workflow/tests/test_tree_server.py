"""Unit tests for tree_server."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import yaml
from project_tree import model
from tree_server import TreeHandler


class TestTreeServerPendingProposals(unittest.TestCase):
    """Tests for pending proposal detection in tree_server.TreeHandler._load_tree."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.tmp_dir.name)
        # Create minimal valid nodes.yaml
        self.nodes_file = self.proj_dir / "nodes.yaml"
        with self.nodes_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [{"id": "root", "title": "Root", "kind": "goal", "status": "active"}],
                },
                f,
            )
        self.patcher = patch.object(model, "project_dir", return_value=self.proj_dir)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp_dir.cleanup()

    def test_load_tree_no_proposals(self):
        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertFalse(data["pending"])
        self.assertEqual(data["pending_targets"], [])

    def test_load_tree_fragment_proposal(self):
        frag_dir = self.proj_dir / "fragments"
        frag_dir.mkdir(parents=True, exist_ok=True)
        (frag_dir / "sim.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("fragments/sim.yaml", data["pending_targets"])

    def test_load_tree_root_proposal(self):
        (self.proj_dir / "nodes.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("nodes.yaml", data["pending_targets"])

    def test_load_tree_multiple_proposals(self):
        (self.proj_dir / "nodes.yaml.proposed").touch()
        frag_dir = self.proj_dir / "fragments"
        frag_dir.mkdir(parents=True, exist_ok=True)
        (frag_dir / "sim.yaml.proposed").touch()

        handler = TreeHandler.__new__(TreeHandler)
        data = handler._load_tree("test-proj")
        self.assertTrue(data["pending"])
        self.assertIn("nodes.yaml", data["pending_targets"])
        self.assertIn("fragments/sim.yaml", data["pending_targets"])
        self.assertEqual(len(data["pending_targets"]), 2)

    def test_load_tree_nonexistent_project(self):
        handler = TreeHandler.__new__(TreeHandler)
        with patch.object(model, "project_dir", return_value=self.proj_dir / "nonexistent"):
            with self.assertRaises(FileNotFoundError):
                handler._load_tree("nonexistent")


class TestTreeServerRestApi(unittest.TestCase):
    """End-to-end HTTP tests for Cockpit REST API in TreeHandler."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.tmp_dir.name)
        # Create minimal valid nodes.yaml
        self.nodes_file = self.proj_dir / "nodes.yaml"
        with self.nodes_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [
                        {
                            "id": "root",
                            "title": "Root",
                            "kind": "goal",
                            "status": "active",
                            "data": {
                                "verification": {"command": "echo 'ok'"}
                            },
                        }
                    ],
                },
                f,
            )

        import spec_discovery.model as spec_model

        self.patcher1 = patch.object(
            model,
            "project_dir",
            side_effect=lambda name: self.proj_dir if name == "test-proj" else (self.proj_dir / name),
        )
        self.patcher2 = patch.object(
            spec_model,
            "project_dir",
            side_effect=lambda name: self.proj_dir if name == "test-proj" else (self.proj_dir / name),
        )
        self.patcher1.start()
        self.patcher2.start()

        import threading
        from http.server import ThreadingHTTPServer

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TreeHandler)
        self.port = self.server.server_port
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.patcher1.stop()
        self.patcher2.stop()
        self.tmp_dir.cleanup()

    def _get(self, path: str):
        import urllib.error
        import urllib.request
        import json

        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = body
            return err.code, data

    def _post(self, path: str, payload=None, raw_body: bytes | None = None):
        import urllib.error
        import urllib.request
        import json

        url = f"http://127.0.0.1:{self.port}{path}"
        if raw_body is not None:
            data = raw_body
        else:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = body
            return err.code, data

    def test_get_proposals_no_pending(self):
        status, data = self._get("/api/proposals/test-proj")
        self.assertEqual(status, 200)
        self.assertEqual(data["project"], "test-proj")
        self.assertEqual(data["proposals"], [])

    def test_get_proposals_with_pending(self):
        proposed_file = self.proj_dir / "nodes.yaml.proposed"
        with proposed_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [{"id": "root", "title": "Updated Root", "kind": "goal", "status": "active"}],
                },
                f,
            )
        status, data = self._get("/api/proposals/test-proj")
        self.assertEqual(status, 200)
        self.assertEqual(data["project"], "test-proj")
        self.assertEqual(len(data["proposals"]), 1)
        prop = data["proposals"][0]
        self.assertEqual(prop["target"], "nodes.yaml")
        self.assertIsNone(prop["fragment"])
        self.assertIn("nodes.yaml.proposed", prop["path"])
        self.assertIn("+  title: Updated Root", prop["diff"])

    def test_get_proposals_nonexistent_project(self):
        status, data = self._get("/api/proposals/nonexistent")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_post_proposals_apply_success(self):
        proposed_file = self.proj_dir / "nodes.yaml.proposed"
        with proposed_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [{"id": "root", "title": "Applied Root", "kind": "goal", "status": "active"}],
                },
                f,
            )
        status, data = self._post("/api/proposals/apply", {"project": "test-proj", "fragment": None})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "applied")
        self.assertEqual(data["project"], "test-proj")
        self.assertIsNone(data["fragment"])
        self.assertFalse(proposed_file.exists())
        with self.nodes_file.open() as f:
            saved = yaml.safe_load(f)
        self.assertEqual(saved["nodes"][0]["title"], "Applied Root")

    def test_post_proposals_apply_not_found(self):
        status, data = self._post("/api/proposals/apply", {"project": "test-proj", "fragment": None})
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_post_proposals_reject_success(self):
        proposed_file = self.proj_dir / "nodes.yaml.proposed"
        with proposed_file.open("w") as f:
            yaml.safe_dump(
                {
                    "project": "test-proj",
                    "nodes": [{"id": "root", "title": "Rejected Root", "kind": "goal", "status": "active"}],
                },
                f,
            )
        status, data = self._post("/api/proposals/reject", {"project": "test-proj", "fragment": None})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "rejected")
        self.assertFalse(proposed_file.exists())
        with self.nodes_file.open() as f:
            saved = yaml.safe_load(f)
        self.assertEqual(saved["nodes"][0]["title"], "Root")

    def test_post_proposals_reject_not_found(self):
        status, data = self._post("/api/proposals/reject", {"project": "test-proj", "fragment": None})
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_get_claims_empty_when_file_not_found(self):
        status, data = self._get("/api/claims/test-proj/root")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"claims": []})

    def test_get_claims_existing_file(self):
        claims_dir = self.proj_dir / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claims_data = {
            "project": "test-proj",
            "node_id": "root",
            "claims": [
                {"id": "c1", "kind": "verify", "text": "Root runs smoothly", "decision": "pending"}
            ],
        }
        with (claims_dir / "root.json").open("w") as f:
            import json
            json.dump(claims_data, f)

        status, data = self._get("/api/claims/test-proj/root")
        self.assertEqual(status, 200)
        self.assertEqual(data["node_id"], "root")
        self.assertEqual(len(data["claims"]), 1)
        self.assertEqual(data["claims"][0]["id"], "c1")

    def test_post_claims_triage_approved(self):
        claims_dir = self.proj_dir / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claims_data = {
            "project": "test-proj",
            "node_id": "root",
            "claims": [
                {"id": "c1", "kind": "verify", "text": "Test claim", "decision": "pending"}
            ],
        }
        claims_file = claims_dir / "root.json"
        with claims_file.open("w") as f:
            import json
            json.dump(claims_data, f)

        status, data = self._post(
            "/api/claims/triage",
            {"project": "test-proj", "node_id": "root", "claim_id": "c1", "decision": "approved"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["claims"][0]["decision"], "approved")
        self.assertIn("triaged_at", data["claims"][0])

        with claims_file.open() as f:
            import json
            saved = json.load(f)
        self.assertEqual(saved["claims"][0]["decision"], "approved")
        self.assertIn("triaged_at", saved["claims"][0])

    def test_post_claims_triage_not_found(self):
        status, data = self._post(
            "/api/claims/triage",
            {"project": "test-proj", "node_id": "root", "claim_id": "c999", "decision": "approved"},
        )
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_post_claims_triage_invalid_decision(self):
        status, data = self._post(
            "/api/claims/triage",
            {"project": "test-proj", "node_id": "root", "claim_id": "c1", "decision": "invalid_choice"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_post_verify_success(self):
        status, data = self._post("/api/verify", {"project": "test-proj", "node_id": "root"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["project"], "test-proj")
        self.assertEqual(data["node_id"], "root")

    def test_post_verify_node_not_found(self):
        status, data = self._post("/api/verify", {"project": "test-proj", "node_id": "nonexistent"})
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_post_mutate_add_child(self):
        status, data = self._post(
            "/api/mutate",
            {
                "project": "test-proj",
                "target_node_id": "root",
                "operation": "add_child",
                "payload": {"id": "child-node", "title": "Child", "kind": "task"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "staged")
        self.assertTrue((self.proj_dir / "nodes.yaml.proposed").exists())

    def test_post_mutate_invalid_node(self):
        status, data = self._post(
            "/api/mutate",
            {
                "project": "test-proj",
                "target_node_id": "unknown-node",
                "operation": "add_child",
                "payload": {"id": "child-2", "title": "Child", "kind": "task"},
            },
        )
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_post_invalid_json_body(self):
        status, data = self._post("/api/verify", raw_body=b"not-valid-json{")
        self.assertEqual(status, 400)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()

