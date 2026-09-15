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
from tree_server import TreeHandler, get_project_fingerprint


class TestNodeStatusRoute(unittest.TestCase):
    """Epic A — GET /api/node/<project>/<id> and the node_status aggregator."""

    def _capture_handler(self):
        handler = TreeHandler.__new__(TreeHandler)
        captured = {"status": 200}

        def fake_json(payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

        def fake_error(status, message):
            captured["status"] = status
            captured["error"] = message

        handler._json_response = fake_json  # type: ignore[method-assign]
        handler._error_response = fake_error  # type: ignore[method-assign]
        return handler, captured

    def test_aggregator_leaf(self):
        from project_tree import status as tree_status

        result = tree_status.node_status("meta", "viewer-server")
        self.assertEqual(result["node_id"], "viewer-server")
        self.assertEqual(result["kind"], "work")
        self.assertTrue(result["read_only"])
        self.assertIn("gate_states", result)

    def test_aggregator_missing_raises(self):
        from project_tree import status as tree_status

        with self.assertRaises(ValueError):
            tree_status.node_status("meta", "no-such-node-xyz")

    def test_route_ok(self):
        handler, captured = self._capture_handler()
        handler._handle_get_node("/api/node/meta/viewer-server")
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["node_id"], "viewer-server")

    def test_route_missing_node_404(self):
        handler, captured = self._capture_handler()
        handler._handle_get_node("/api/node/meta/no-such-node-xyz")
        self.assertEqual(captured["status"], 404)

    def test_route_bad_path_400(self):
        handler, captured = self._capture_handler()
        handler._handle_get_node("/api/node/meta")
        self.assertEqual(captured["status"], 400)

    def test_route_rejects_traversal(self):
        handler, captured = self._capture_handler()
        handler._handle_get_node("/api/node/meta/..%2f..%2fetc")
        self.assertEqual(captured["status"], 400)


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
        self.server.sse_poll_interval = 0.05
        self.server.sse_ping_interval = 0.2
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
            with err:
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
            with err:
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

    def test_post_decay_scan_success(self):
        with patch("tree_server.scan_decay", return_value={"scanned": 2, "decayed": 0, "refreshed": 1, "nodes": []}):
            status, data = self._post("/api/decay-scan", {"project": "test-proj", "dry_run": False})
        self.assertEqual(status, 200)
        self.assertEqual(data["scanned"], 2)
        self.assertEqual(data["decayed"], 0)
        self.assertEqual(data["refreshed"], 1)

    def test_post_decay_scan_missing_project(self):
        status, data = self._post("/api/decay-scan", {"dry_run": False})
        self.assertEqual(status, 400)
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

    def _read_sse_event(self, resp):
        event_name = None
        data_lines = []
        import json
        while True:
            line = resp.readline()
            if not line:
                break
            text = line.decode("utf-8")
            if text.endswith("\r\n"):
                text = text[:-2]
            elif text.endswith("\n"):
                text = text[:-1]
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

    def test_json_response_headers_no_duplicate_cache_control(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        try:
            conn.request("GET", "/api/proposals/test-proj")
            resp = conn.getresponse()
            cache_controls = resp.headers.get_all("Cache-Control")
            self.assertEqual(len(cache_controls), 1)
            self.assertEqual(cache_controls[0], "no-store")
        finally:
            conn.close()

    def test_events_missing_project(self):
        status1, data1 = self._get("/api/events")
        self.assertEqual(status1, 400)
        self.assertIn("error", data1)
        status2, data2 = self._get("/api/events/")
        self.assertEqual(status2, 400)
        self.assertIn("error", data2)

    def test_events_nonexistent_project(self):
        status, data = self._get("/api/events/nonexistent")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_events_stream_headers_and_initial_connect(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.getheader("Content-Type"), "text/event-stream; charset=utf-8")
            self.assertEqual(resp.getheader("Cache-Control"), "no-cache, no-transform")
            self.assertEqual(resp.getheader("Connection"), "keep-alive")
            self.assertEqual(resp.getheader("X-Accel-Buffering"), "no")
            cache_controls = resp.headers.get_all("Cache-Control")
            self.assertEqual(len(cache_controls), 1)

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_detects_nodes_yaml_modification(self):
        import http.client
        import time
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Modify nodes.yaml
            time.sleep(0.05)
            with self.nodes_file.open("w") as f:
                yaml.safe_dump(
                    {
                        "project": "test-proj",
                        "nodes": [
                            {"id": "root", "title": "Root Changed", "kind": "goal", "status": "active"}
                        ],
                    },
                    f,
                )

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_detects_proposed_nodes_change(self):
        import http.client
        import time
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Create nodes.yaml.proposed
            time.sleep(0.05)
            (self.proj_dir / "nodes.yaml.proposed").write_text("test: proposal\n", encoding="utf-8")

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_detects_fragment_change(self):
        import http.client
        import time
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Create fragment
            time.sleep(0.05)
            frag_dir = self.proj_dir / "fragments"
            frag_dir.mkdir(parents=True, exist_ok=True)
            (frag_dir / "sim.yaml").write_text("nodes: []\n", encoding="utf-8")

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_detects_fragment_proposed_change(self):
        import http.client
        import time
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Create fragment proposed
            time.sleep(0.05)
            frag_dir = self.proj_dir / "fragments"
            frag_dir.mkdir(parents=True, exist_ok=True)
            (frag_dir / "sim.yaml.proposed").write_text("nodes: []\n", encoding="utf-8")

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_detects_claim_change(self):
        import http.client
        import time
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Create claim
            time.sleep(0.05)
            claims_dir = self.proj_dir / "claims"
            claims_dir.mkdir(parents=True, exist_ok=True)
            (claims_dir / "root.json").write_text('{"claims": []}\n', encoding="utf-8")

            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "tree_changed")
            self.assertEqual(data, {"project": "test-proj"})
        finally:
            conn.close()

    def test_events_stream_heartbeat_ping(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/events/test-proj")
            resp = conn.getresponse()
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "connected")

            # Without any file changes, heartbeat ping should arrive within ~0.25s
            event, data = self._read_sse_event(resp)
            self.assertEqual(event, "ping")
            self.assertEqual(data, {})
        finally:
            conn.close()

    def test_events_stream_clean_disconnect(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/events/test-proj")
        resp = conn.getresponse()
        event, data = self._read_sse_event(resp)
        self.assertEqual(event, "connected")
        # Abruptly close the connection
        conn.close()

        # Normal subsequent request works without any server hanging
        status, data = self._get("/api/proposals/test-proj")
        self.assertEqual(status, 200)

    def _get_raw(self, path: str):
        import urllib.request
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            content_type = resp.getheader("Content-Type")
            body = resp.read().decode("utf-8")
            return resp.status, content_type, body

    def test_get_static_index_html(self):
        status, content_type, body = self._get_raw("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn('class="status-dot connecting"', body)
        self.assertIn('id="cockpit-layout"', body)
        self.assertIn('id="search-input"', body)
        self.assertIn('id="tree"', body)
        self.assertIn('id="claims-list"', body)

    def test_get_static_styles_css(self):
        status, content_type, body = self._get_raw("/styles.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", content_type)
        self.assertIn("@media (max-width: 768px)", body)
        self.assertIn(".cockpit-layout", body)

    def test_get_static_app_js(self):
        status, content_type, body = self._get_raw("/app.js")
        self.assertEqual(status, 200)
        self.assertTrue("javascript" in content_type or "text/plain" in content_type)
        self.assertIn("state = {", body)
        self.assertIn("advanceSelection", body)
        self.assertIn("handleApprove", body)
        self.assertIn("handleReject", body)
        self.assertIn("approveAllClaims", body)
        self.assertIn("runVerification", body)
        self.assertIn("connectSSE", body)
        self.assertIn("EventSource", body)

    def test_static_assets_dom_id_integrity(self):
        import re
        from html.parser import HTMLParser

        class IDCollector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = set()
            def handle_starttag(self, tag, attrs):
                for k, v in attrs:
                    if k == "id":
                        self.ids.add(v)

        _, _, html = self._get_raw("/index.html")
        parser = IDCollector()
        parser.feed(html)

        _, _, js = self._get_raw("/app.js")
        js_ids = set(re.findall(r'document\.getElementById\(["\']([^"\']+)["\']\)', js))

        missing = js_ids - parser.ids
        self.assertEqual(missing, set(), f"IDs referenced in app.js not found in index.html: {missing}")


class TestGetProjectFingerprint(unittest.TestCase):
    """Unit tests for get_project_fingerprint change detection."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = Path(self.tmp_dir.name)
        (self.proj_dir / "nodes.yaml").write_text("project: test\n", encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_fingerprint_changes_on_nodes_modification(self):
        fp1 = get_project_fingerprint(self.proj_dir)
        import time
        time.sleep(0.01)
        (self.proj_dir / "nodes.yaml").write_text("project: test-modified\n", encoding="utf-8")
        fp2 = get_project_fingerprint(self.proj_dir)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_changes_on_proposed_nodes(self):
        fp1 = get_project_fingerprint(self.proj_dir)
        prop = self.proj_dir / "nodes.yaml.proposed"
        prop.write_text("prop\n", encoding="utf-8")
        fp2 = get_project_fingerprint(self.proj_dir)
        self.assertNotEqual(fp1, fp2)
        prop.unlink()
        fp3 = get_project_fingerprint(self.proj_dir)
        self.assertEqual(fp1, fp3)

    def test_fingerprint_changes_on_fragment(self):
        fp1 = get_project_fingerprint(self.proj_dir)
        frag_dir = self.proj_dir / "fragments"
        frag_dir.mkdir()
        (frag_dir / "sub.yaml").write_text("sub\n", encoding="utf-8")
        fp2 = get_project_fingerprint(self.proj_dir)
        self.assertNotEqual(fp1, fp2)
        (frag_dir / "sub.yaml.proposed").write_text("prop\n", encoding="utf-8")
        fp3 = get_project_fingerprint(self.proj_dir)
        self.assertNotEqual(fp2, fp3)

    def test_fingerprint_changes_on_claims(self):
        fp1 = get_project_fingerprint(self.proj_dir)
        claims_dir = self.proj_dir / "claims"
        claims_dir.mkdir()
        (claims_dir / "root.json").write_text("[]\n", encoding="utf-8")
        fp2 = get_project_fingerprint(self.proj_dir)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_ignores_unrelated_files(self):
        fp1 = get_project_fingerprint(self.proj_dir)
        (self.proj_dir / "unrelated.txt").write_text("hello\n", encoding="utf-8")
        (self.proj_dir / "random.log").write_text("log\n", encoding="utf-8")
        fp2 = get_project_fingerprint(self.proj_dir)
        self.assertEqual(fp1, fp2)


if __name__ == "__main__":
    unittest.main()

