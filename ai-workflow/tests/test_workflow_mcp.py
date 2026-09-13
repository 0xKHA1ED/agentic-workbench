"""Unit tests for the Core MCP Protocol Server & Dispatch Engine."""

import io
import json
import sys
import unittest
from unittest import mock
from pathlib import Path

# Ensure ai-workflow/scripts is discoverable
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import workflow_mcp
from workflow_mcp import MCPServer, register_tool, run_stdio_server


class TestMCPProtocolServer(unittest.TestCase):
    """Test suite for JSON-RPC 2.0 MCP server implementation."""

    def setUp(self):
        self.server = MCPServer()

    def test_initialize(self):
        """Test initialize returns protocolVersion, capabilities, and serverInfo."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.get("jsonrpc"), "2.0")
        self.assertEqual(response.get("id"), 1)
        result = response.get("result", {})
        self.assertEqual(result.get("protocolVersion"), "2024-11-05")
        self.assertEqual(result.get("capabilities"), {"tools": {}})
        self.assertEqual(
            result.get("serverInfo"),
            {"name": "ai-workflow", "version": "2.0.0"},
        )

    def test_ping(self):
        """Test ping returns an empty dict result."""
        request = {
            "jsonrpc": "2.0",
            "id": "req-ping",
            "method": "ping",
        }
        response = self.server.handle_message(request)
        self.assertEqual(
            response,
            {"jsonrpc": "2.0", "id": "req-ping", "result": {}},
        )

    def test_notifications_initialized(self):
        """Test notifications/initialized produces no response (None)."""
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        response = self.server.handle_message(request)
        self.assertIsNone(response)

    def test_tools_list_empty(self):
        """Test tools/list returns empty tools array when no tools are registered."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }
        response = self.server.handle_message(request)
        self.assertEqual(
            response,
            {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
        )

    def test_register_tool_and_list(self):
        """Test registering a tool and listing it via tools/list."""
        schema = {
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
            "required": ["arg1"],
        }

        @self.server.register_tool(
            name="test_tool",
            description="A test tool description",
            input_schema=schema,
        )
        def handler(arguments):
            return f"Hello, {arguments.get('arg1')}"

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        tools = response.get("result", {}).get("tools", [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "test_tool")
        self.assertEqual(tools[0]["description"], "A test tool description")
        self.assertEqual(tools[0]["inputSchema"], schema)

    def test_tools_call_success_string(self):
        """Test calling a tool that returns a string."""
        self.server.register_tool(
            name="echo",
            description="Echoes input",
            input_schema={"type": "object"},
            handler=lambda args: f"Echo: {args.get('msg', '')}",
        )

        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"msg": "world"},
            },
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.get("id"), 4)
        result = response.get("result", {})
        self.assertNotIn("isError", result)
        self.assertEqual(
            result.get("content"),
            [{"type": "text", "text": "Echo: world"}],
        )

    def test_tools_call_success_dict(self):
        """Test calling a tool that returns a dict."""
        self.server.register_tool(
            name="get_data",
            description="Returns dict data",
            input_schema={"type": "object"},
            handler=lambda args: {"count": 42},
        )

        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "get_data", "arguments": {}},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        result = response.get("result", {})
        self.assertEqual(
            result.get("content"),
            [{"type": "text", "text": json.dumps({"count": 42}, indent=2)}],
        )

    def test_tools_call_unknown_tool(self):
        """Test calling an unregistered tool returns isError: True."""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        result = response.get("result", {})
        self.assertTrue(result.get("isError"))
        self.assertIn("nonexistent_tool", result.get("content", [{}])[0].get("text", ""))

    def test_tools_call_handler_exception(self):
        """Test tool execution error returns isError: True."""
        def faulty_tool(args):
            raise ValueError("Something broke inside tool")

        self.server.register_tool(
            name="faulty",
            description="Always raises",
            handler=faulty_tool,
        )

        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "faulty", "arguments": {}},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        result = response.get("result", {})
        self.assertTrue(result.get("isError"))
        self.assertIn("Something broke inside tool", result.get("content", [{}])[0].get("text", ""))

    def test_tools_call_missing_params_or_name(self):
        """Test tools/call with invalid or missing params returns -32602 error."""
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.get("id"), 8)
        self.assertEqual(response.get("error", {}).get("code"), -32602)

    def test_unknown_method(self):
        """Test unknown method returns -32601 Method not found."""
        request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "nonexistent/method",
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.get("id"), 9)
        self.assertEqual(response.get("error", {}).get("code"), -32601)

    def test_malformed_json_string(self):
        """Test handling malformed JSON string returns -32700 Parse error."""
        response = self.server.handle_message("{not valid json")
        self.assertIsNotNone(response)
        self.assertIsNone(response.get("id"))
        self.assertEqual(response.get("error", {}).get("code"), -32700)

    def test_invalid_jsonrpc_request(self):
        """Test invalid JSON-RPC version or missing method returns -32600 Invalid Request."""
        response = self.server.handle_message({"jsonrpc": "1.0", "id": 10, "method": "ping"})
        self.assertEqual(response.get("error", {}).get("code"), -32600)

        response = self.server.handle_message({"jsonrpc": "2.0", "id": 11})
        self.assertEqual(response.get("error", {}).get("code"), -32600)

    def test_handle_message_json_string_input(self):
        """Test handle_message accepts JSON string and returns dict response."""
        request_str = json.dumps({"jsonrpc": "2.0", "id": 12, "method": "ping"})
        response = self.server.handle_message(request_str)
        self.assertEqual(response, {"jsonrpc": "2.0", "id": 12, "result": {}})

    def test_module_level_register_tool(self):
        """Test module-level register_tool registers on default_server."""
        original_tools = dict(workflow_mcp.default_server.tools)
        self.addCleanup(lambda: setattr(workflow_mcp.default_server, "tools", original_tools))

        @register_tool("mod_tool", "Module level tool")
        def mod_handler(args):
            return "ok"

        self.assertIn("mod_tool", workflow_mcp.default_server.tools)

    def test_tools_call_single_named_parameter(self):
        """Test tool with a single named parameter receives argument value, not dict."""
        received_arg = {}

        @self.server.register_tool(name="get_node", description="Get node by ID")
        def get_node(node_id: str):
            received_arg["val"] = node_id
            return f"Node {node_id}"

        request = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "get_node", "arguments": {"node_id": "root-node"}},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        self.assertEqual(received_arg.get("val"), "root-node")
        self.assertIsInstance(received_arg.get("val"), str)
        self.assertEqual(
            response.get("result", {}).get("content"),
            [{"type": "text", "text": "Node root-node"}],
        )

    def test_tools_call_internal_type_error_not_masked(self):
        """Test TypeError inside handler execution body is preserved and not masked into parameter mismatch."""
        @self.server.register_tool(name="calc_fail", description="Fails with TypeError inside body")
        def calc_fail(x: int, y: int):
            # Explicit TypeError inside handler body
            return x + "not_an_int"

        request = {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {"name": "calc_fail", "arguments": {"x": 10, "y": 20}},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        result = response.get("result", {})
        self.assertTrue(result.get("isError"))
        err_msg = result.get("content", [{}])[0].get("text", "")
        self.assertIn("unsupported operand type", err_msg)
        self.assertNotIn("missing a required argument", err_msg)

    def test_tools_call_default_arguments(self):
        """Test tool handler with default arguments has defaults populated."""
        @self.server.register_tool(name="orient_default", description="Orient with defaults")
        def orient_default(project: str, filter_kind: str = "weak"):
            return f"Project: {project}, Filter: {filter_kind}"

        request = {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {"name": "orient_default", "arguments": {"project": "meta"}},
        }
        response = self.server.handle_message(request)
        self.assertIsNotNone(response)
        result = response.get("result", {})
        self.assertEqual(
            result.get("content"),
            [{"type": "text", "text": "Project: meta, Filter: weak"}],
        )

    def test_run_stdio_server(self):
        """Test run_stdio_server reads newline-delimited JSON and writes to stdout."""
        input_data = (
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "initialize"}) + "\n"
        )
        fake_stdin = io.StringIO(input_data)
        fake_stdout = io.StringIO()
        fake_stderr = io.StringIO()

        run_stdio_server(
            server=self.server,
            stdin=fake_stdin,
            stdout=fake_stdout,
            stderr=fake_stderr,
        )

        lines = fake_stdout.getvalue().strip().split("\n")
        self.assertEqual(len(lines), 2)  # Notification produces no stdout response
        res1 = json.loads(lines[0])
        res2 = json.loads(lines[1])
        self.assertEqual(res1.get("id"), 1)
        self.assertEqual(res1.get("result"), {})
        self.assertEqual(res2.get("id"), 2)
        self.assertEqual(res2.get("result", {}).get("protocolVersion"), "2024-11-05")


class TestWorkflowReadTools(unittest.TestCase):
    """Test suite for workflow_orient and workflow_get_node MCP read tools."""

    def setUp(self):
        self.server = workflow_mcp.default_server

    def _call_tool(self, name: str, arguments: dict):
        req = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }
        return self.server.handle_message(req)

    def test_tools_list_registers_read_tools(self):
        """Test that workflow_orient and workflow_get_node are registered on default_server."""
        req = {"jsonrpc": "2.0", "id": 101, "method": "tools/list"}
        resp = self.server.handle_message(req)
        self.assertIsNotNone(resp)
        tools = {t["name"]: t for t in resp.get("result", {}).get("tools", [])}
        self.assertIn("workflow_orient", tools)
        self.assertIn("workflow_get_node", tools)
        self.assertIn("project", tools["workflow_orient"]["inputSchema"]["properties"])
        self.assertIn("filter", tools["workflow_orient"]["inputSchema"]["properties"])
        self.assertIn("project", tools["workflow_get_node"]["inputSchema"]["properties"])
        self.assertIn("node_id", tools["workflow_get_node"]["inputSchema"]["properties"])

    def test_workflow_orient_meta_weak(self):
        """Test workflow_orient on meta with default filter weak."""
        resp = self._call_tool("workflow_orient", {"project": "meta", "filter": "weak"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["project"], "meta")
        self.assertEqual(data["total_nodes"], 38)
        self.assertEqual(data["filtered_count"], 36)
        self.assertEqual(len(data["nodes"]), 36)
        self.assertEqual(data["pending_proposals"], [])
        # All returned nodes should have status == 'weak'
        for node in data["nodes"]:
            self.assertEqual(node.get("status"), "weak")
            self.assertNotIn("children", node)
        # Verify strong nodes are excluded
        returned_ids = {n["id"] for n in data["nodes"]}
        self.assertNotIn("tree-cli-usage", returned_ids)
        self.assertNotIn("viewer-ui", returned_ids)
        self.assertIn("root", returned_ids)

    def test_workflow_orient_meta_all(self):
        """Test workflow_orient on meta with filter all."""
        resp = self._call_tool("workflow_orient", {"project": "meta", "filter": "all"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["total_nodes"], 38)
        self.assertEqual(data["filtered_count"], 38)
        self.assertEqual(len(data["nodes"]), 38)
        returned_ids = {n["id"] for n in data["nodes"]}
        self.assertIn("tree-cli-usage", returned_ids)
        self.assertIn("viewer-ui", returned_ids)

    def test_workflow_orient_meta_decayed(self):
        """Test workflow_orient on meta with filter decayed."""
        resp = self._call_tool("workflow_orient", {"project": "meta", "filter": "decayed"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["total_nodes"], 38)
        self.assertEqual(data["filtered_count"], 0)
        self.assertEqual(data["nodes"], [])

    def test_workflow_orient_decayed_positive_matches(self):
        """Test workflow_orient with filter decayed matches nodes by status, stale flag, or data.decayed."""
        import tempfile
        from pathlib import Path
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "fixture-decay",
                "nodes": [
                    {
                        "id": "root-decay",
                        "title": "Root Group",
                        "kind": "group",
                        "status": "strong",
                        "children": [
                            {
                                "id": "n-decayed",
                                "title": "Explicit Decayed Status",
                                "kind": "work",
                                "status": "decayed",
                            },
                            {
                                "id": "n-unverified",
                                "title": "Decayed Unverified Status",
                                "kind": "work",
                                "status": "decayed_unverified",
                            },
                            {
                                "id": "n-stale",
                                "title": "Stale Flagged Node",
                                "kind": "work",
                                "status": "weak",
                                "stale": True,
                            },
                            {
                                "id": "n-data-decay",
                                "title": "Data Decayed Node",
                                "kind": "work",
                                "status": "weak",
                                "data": {"decayed": True},
                            },
                            {
                                "id": "n-healthy-weak",
                                "title": "Normal Weak Node",
                                "kind": "work",
                                "status": "weak",
                            },
                            {
                                "id": "n-healthy-strong",
                                "title": "Normal Strong Node",
                                "kind": "work",
                                "status": "strong",
                            },
                        ],
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_orient",
                    {"project": "fixture-decay", "filter": "decayed"},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["total_nodes"], 7)
                self.assertEqual(data["filtered_count"], 4)
                self.assertEqual(len(data["nodes"]), 4)
                decayed_ids = {n["id"] for n in data["nodes"]}
                self.assertEqual(
                    decayed_ids,
                    {"n-decayed", "n-unverified", "n-stale", "n-data-decay"},
                )
                # Verify children key is omitted from oriented node entries
                for node in data["nodes"]:
                    self.assertNotIn("children", node)

    def test_workflow_orient_unknown_project(self):
        """Test workflow_orient returns error for unknown project."""
        resp = self._call_tool("workflow_orient", {"project": "nonexistent_project_xyz"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertTrue(result.get("isError"))
        err_text = result["content"][0]["text"]
        self.assertIn("nonexistent_project_xyz", err_text)

    def test_workflow_orient_invalid_filter(self):
        """Test workflow_orient returns error for invalid filter."""
        resp = self._call_tool("workflow_orient", {"project": "meta", "filter": "invalid_kind"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertTrue(result.get("isError"))
        err_text = result["content"][0]["text"]
        self.assertIn("invalid_kind", err_text)

    def test_workflow_orient_with_pending_proposals(self):
        """Test workflow_orient detects pending proposals."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            (proj_dir / "nodes.yaml").write_text("project: tmp-proj\nnodes:\n- id: r\n  title: R\n  kind: group\n  status: weak\n")
            (proj_dir / "nodes.yaml.proposed").write_text("project: tmp-proj\nnodes:\n- id: r\n  title: R\n  kind: group\n  status: strong\n")
            with unittest.mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool("workflow_orient", {"project": "tmp-proj"})
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["total_nodes"], 1)
                self.assertEqual(len(data["pending_proposals"]), 1)
                self.assertIn("target", data["pending_proposals"][0])
                self.assertIn("path", data["pending_proposals"][0])

    def test_workflow_get_node_existing_meta_node(self):
        """Test workflow_get_node retrieves an existing node from meta project."""
        resp = self._call_tool("workflow_get_node", {"project": "meta", "node_id": "tree-cli-usage"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["id"], "tree-cli-usage")
        self.assertEqual(data["title"], "Propose / diff / apply workflow")
        self.assertEqual(data["kind"], "work")
        self.assertEqual(data["status"], "strong")
        self.assertEqual(data["data"]["pattern"], "scripts/project_tree/cli.py")
        self.assertIsNotNone(data.get("parent"))
        self.assertEqual(data["parent"]["id"], "orient-skill")

    def test_workflow_get_node_root_node_has_no_parent(self):
        """Test workflow_get_node on root node returns None for parent."""
        resp = self._call_tool("workflow_get_node", {"project": "meta", "node_id": "root"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertNotIn("isError", result)
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["id"], "root")
        self.assertIsNone(data.get("parent"))

    def test_workflow_get_node_complete_details_fixture(self):
        """Test workflow_get_node returning complete details (title, kind, status, data.pattern, data.pain, data.contract, data.claims)."""
        import tempfile
        from pathlib import Path
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "fixture-proj",
                "nodes": [
                    {
                        "id": "root",
                        "title": "Root Node",
                        "kind": "group",
                        "status": "strong",
                        "children": [
                            {
                                "id": "detailed-leaf",
                                "title": "Detailed Leaf Node",
                                "kind": "work",
                                "status": "weak",
                                "data": {
                                    "pattern": "src/core/leaf.py",
                                    "pain": "Slow serialization overhead on 10k nodes",
                                    "contract": "specs/leaf-optimization.md",
                                    "claims": "claims/detailed-leaf.json",
                                    "verification": {
                                        "check_type": "command",
                                        "command": "pytest tests/test_leaf.py",
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with unittest.mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_get_node",
                    {"project": "fixture-proj", "node_id": "detailed-leaf"},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                node_info = json.loads(result["content"][0]["text"])
                self.assertEqual(node_info["id"], "detailed-leaf")
                self.assertEqual(node_info["title"], "Detailed Leaf Node")
                self.assertEqual(node_info["kind"], "work")
                self.assertEqual(node_info["status"], "weak")
                self.assertEqual(node_info["data"]["pattern"], "src/core/leaf.py")
                self.assertEqual(node_info["data"]["pain"], "Slow serialization overhead on 10k nodes")
                self.assertEqual(node_info["data"]["contract"], "specs/leaf-optimization.md")
                self.assertEqual(node_info["data"]["claims"], "claims/detailed-leaf.json")
                self.assertIsNotNone(node_info["parent"])
                self.assertEqual(node_info["parent"]["id"], "root")

    def test_workflow_get_node_not_found(self):
        """Test workflow_get_node returns error when node is not found."""
        resp = self._call_tool("workflow_get_node", {"project": "meta", "node_id": "missing_node_123"})
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertTrue(result.get("isError"))
        err_text = result["content"][0]["text"]
        self.assertIn("missing_node_123", err_text)

    def test_direct_functions(self):
        """Test direct function invocation of workflow_orient and workflow_get_node."""
        self.assertTrue(hasattr(workflow_mcp, "workflow_orient"))
        self.assertTrue(hasattr(workflow_mcp, "workflow_get_node"))
        self.assertTrue(hasattr(workflow_mcp, "workflow_propose_tree_mutation"))
        self.assertTrue(hasattr(workflow_mcp, "workflow_stage_contract_claims"))
        self.assertTrue(hasattr(workflow_mcp, "workflow_execute_verification"))
        orient_fn = getattr(workflow_mcp, "workflow_orient")
        get_node_fn = getattr(workflow_mcp, "workflow_get_node")
        res = orient_fn("meta", "weak")
        self.assertEqual(res["total_nodes"], 38)
        node_res = get_node_fn("meta", "tree-cli-usage")
        self.assertEqual(node_res["id"], "tree-cli-usage")


class TestWorkflowMutationAndExecutionTools(unittest.TestCase):
    """Test suite for mutation, claims staging, and verification execution MCP tools."""

    def setUp(self):
        self.server = workflow_mcp.default_server

    def _call_tool(self, name: str, arguments: dict):
        req = {
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }
        return self.server.handle_message(req)

    def test_tools_list_registers_mutation_and_execution_tools(self):
        """Test that mutation, claims staging, and verification tools are registered on default_server."""
        req = {"jsonrpc": "2.0", "id": 201, "method": "tools/list"}
        resp = self.server.handle_message(req)
        self.assertIsNotNone(resp)
        tools = {t["name"]: t for t in resp.get("result", {}).get("tools", [])}
        self.assertIn("workflow_propose_tree_mutation", tools)
        self.assertIn("workflow_stage_contract_claims", tools)
        self.assertIn("workflow_execute_verification", tools)

        mut_props = tools["workflow_propose_tree_mutation"]["inputSchema"]["properties"]
        self.assertIn("project", mut_props)
        self.assertIn("target_node_id", mut_props)
        self.assertIn("operation", mut_props)
        self.assertIn("payload", mut_props)

        claim_props = tools["workflow_stage_contract_claims"]["inputSchema"]["properties"]
        self.assertIn("project", claim_props)
        self.assertIn("node_id", claim_props)
        self.assertIn("goal", claim_props)
        self.assertIn("claims", claim_props)

        verif_props = tools["workflow_execute_verification"]["inputSchema"]["properties"]
        self.assertIn("project", verif_props)
        self.assertIn("node_id", verif_props)

    def test_propose_tree_mutation_set_data(self):
        """Test workflow_propose_tree_mutation with set_data operation."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "tmp-proj",
                "nodes": [
                    {
                        "id": "root",
                        "title": "Root",
                        "kind": "group",
                        "status": "strong",
                        "children": [
                            {
                                "id": "leaf-node",
                                "title": "Leaf Node",
                                "kind": "work",
                                "status": "weak",
                                "data": {"pattern": "src/core.py"},
                            }
                        ],
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_propose_tree_mutation",
                    {
                        "project": "tmp-proj",
                        "target_node_id": "leaf-node",
                        "operation": "set_data",
                        "payload": {"pain": "High memory consumption during indexing"},
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                self.assertEqual(data["target_node_id"], "leaf-node")
                proposed_file = Path(data["proposed_file"])
                self.assertTrue(proposed_file.exists())
                self.assertEqual(proposed_file.name, "nodes.yaml.proposed")
                self.assertIn("+", data["diff"])
                self.assertIn("High memory consumption during indexing", data["diff"])
                staged_content = yaml.safe_load(proposed_file.read_text())
                leaf = staged_content["nodes"][0]["children"][0]
                self.assertEqual(leaf["data"]["pain"], "High memory consumption during indexing")
                self.assertEqual(leaf["data"]["pattern"], "src/core.py")

    def test_propose_tree_mutation_add_child(self):
        """Test workflow_propose_tree_mutation with add_child operation."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "tmp-proj",
                "nodes": [
                    {
                        "id": "root",
                        "title": "Root",
                        "kind": "group",
                        "status": "strong",
                        "children": [],
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_propose_tree_mutation",
                    {
                        "project": "tmp-proj",
                        "target_node_id": "root",
                        "operation": "add_child",
                        "payload": {
                            "id": "new-worker",
                            "title": "New Worker Service",
                            "kind": "work",
                            "status": "weak",
                        },
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                proposed_file = Path(data["proposed_file"])
                self.assertTrue(proposed_file.exists())
                self.assertIn("new-worker", data["diff"])
                self.assertIn("New Worker Service", data["diff"])
                staged_content = yaml.safe_load(proposed_file.read_text())
                children = staged_content["nodes"][0]["children"]
                self.assertEqual(len(children), 1)
                self.assertEqual(children[0]["id"], "new-worker")

    def test_propose_tree_mutation_set_status(self):
        """Test workflow_propose_tree_mutation with set_status operation."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "tmp-proj",
                "nodes": [
                    {
                        "id": "worker",
                        "title": "Worker",
                        "kind": "work",
                        "status": "weak",
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_propose_tree_mutation",
                    {
                        "project": "tmp-proj",
                        "target_node_id": "worker",
                        "operation": "set_status",
                        "payload": {"status": "strong"},
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                self.assertIn("+", data["diff"])
                self.assertIn("strong", data["diff"])

    def test_propose_tree_mutation_mark_stale(self):
        """Test workflow_propose_tree_mutation with mark_stale operation."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "tmp-proj",
                "nodes": [
                    {
                        "id": "worker",
                        "title": "Worker",
                        "kind": "work",
                        "status": "strong",
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_propose_tree_mutation",
                    {
                        "project": "tmp-proj",
                        "target_node_id": "worker",
                        "operation": "mark_stale",
                        "payload": {"notes": "Dependencies were bumped"},
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                self.assertIn("stale", data["diff"])
                self.assertIn("Dependencies were bumped", data["diff"])

    def test_propose_tree_mutation_fragment(self):
        """Test workflow_propose_tree_mutation targeting a node in a fragment file."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            (proj_dir / "fragments").mkdir(parents=True)
            root_tree = {
                "project": "frag-proj",
                "nodes": [
                    {
                        "id": "root",
                        "title": "Root",
                        "kind": "group",
                        "status": "strong",
                        "data": {"subtree": "fragments/sub.yaml"},
                    }
                ],
            }
            frag_tree = {
                "nodes": [
                    {
                        "id": "frag-leaf",
                        "title": "Fragment Leaf",
                        "kind": "work",
                        "status": "weak",
                    }
                ]
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(root_tree))
            (proj_dir / "fragments" / "sub.yaml").write_text(yaml.dump(frag_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_propose_tree_mutation",
                    {
                        "project": "frag-proj",
                        "target_node_id": "frag-leaf",
                        "operation": "set_status",
                        "payload": {"status": "strong"},
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                self.assertEqual(data["target_node_id"], "frag-leaf")
                self.assertTrue(data["proposed_file"].endswith("fragments/sub.yaml.proposed"))
                proposed_path = Path(data["proposed_file"])
                self.assertTrue(proposed_path.exists())

    def test_propose_tree_mutation_node_not_found(self):
        """Test workflow_propose_tree_mutation returns error for nonexistent node."""
        resp = self._call_tool(
            "workflow_propose_tree_mutation",
            {
                "project": "meta",
                "target_node_id": "nonexistent_node_xyz",
                "operation": "set_status",
                "payload": {"status": "strong"},
            },
        )
        self.assertIsNotNone(resp)
        result = resp.get("result", {})
        self.assertTrue(result.get("isError"))
        self.assertIn("nonexistent_node_xyz", result["content"][0]["text"])

    def test_stage_contract_claims_success(self):
        """Test workflow_stage_contract_claims writes claims JSON to claims/<node_id>.json."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "claim-proj",
                "nodes": [
                    {
                        "id": "node-api",
                        "title": "API Node",
                        "kind": "work",
                        "status": "weak",
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                claims = [
                    {
                        "id": "c1",
                        "kind": "verify",
                        "text": "GET /health returns HTTP 200 with status ok",
                        "check_command": "curl -s http://localhost/health | grep ok",
                        "source_file": "src/api.py",
                    },
                    {
                        "id": "c2",
                        "kind": "must_not",
                        "text": "Expose internal stack traces in 500 responses",
                    },
                ]
                resp = self._call_tool(
                    "workflow_stage_contract_claims",
                    {
                        "project": "claim-proj",
                        "node_id": "node-api",
                        "goal": "Implement resilient API health check endpoint",
                        "claims": claims,
                        "in_scope": ["health endpoint", "status response"],
                        "out_scope": ["metrics prometheus exporter"],
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "staged")
                self.assertEqual(data["claim_count"], 2)
                self.assertEqual(data["goal"], "Implement resilient API health check endpoint")
                claims_file = Path(data["claims_path"])
                self.assertTrue(claims_file.exists())
                self.assertEqual(claims_file.name, "node-api.json")

                saved = json.loads(claims_file.read_text())
                self.assertEqual(saved["project"], "claim-proj")
                self.assertEqual(saved["node"], "node-api")
                self.assertEqual(saved["goal"], "Implement resilient API health check endpoint")
                self.assertEqual(len(saved["claims"]), 2)
                self.assertEqual(saved["claims"][0]["decision"], "pending")
                self.assertEqual(saved["in"], ["health endpoint", "status response"])
                self.assertEqual(saved["out"], ["metrics prometheus exporter"])

    def test_stage_contract_claims_rejects_vague_claims(self):
        """Test workflow_stage_contract_claims rejects non-falsifiable claims."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {"project": "vague-proj", "nodes": [{"id": "n1", "title": "N", "kind": "work", "status": "weak"}]}
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_stage_contract_claims",
                    {
                        "project": "vague-proj",
                        "node_id": "n1",
                        "goal": "Handle tasks",
                        "claims": [
                            {
                                "id": "c1",
                                "kind": "verify",
                                "text": "The worker should handle errors gracefully",
                            }
                        ],
                    },
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertTrue(result.get("isError"))
                err_text = result["content"][0]["text"]
                self.assertIn("vague", err_text.lower())

    def test_stage_contract_claims_schema_validation(self):
        """Test workflow_stage_contract_claims validates input schema and values."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {"project": "val-proj", "nodes": [{"id": "n1", "title": "N", "kind": "work", "status": "weak"}]}
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                # Invalid kind
                resp = self._call_tool(
                    "workflow_stage_contract_claims",
                    {
                        "project": "val-proj",
                        "node_id": "n1",
                        "goal": "Goal",
                        "claims": [{"id": "c1", "kind": "invalid_kind_foo", "text": "Valid test claim"}],
                    },
                )
                self.assertTrue(resp.get("result", {}).get("isError"))

                # Empty claims
                resp = self._call_tool(
                    "workflow_stage_contract_claims",
                    {
                        "project": "val-proj",
                        "node_id": "n1",
                        "goal": "Goal",
                        "claims": [],
                    },
                )
                self.assertTrue(resp.get("result", {}).get("isError"))

                # Empty goal
                resp = self._call_tool(
                    "workflow_stage_contract_claims",
                    {
                        "project": "val-proj",
                        "node_id": "n1",
                        "goal": "",
                        "claims": [{"id": "c1", "kind": "verify", "text": "Valid test claim"}],
                    },
                )
                self.assertTrue(resp.get("result", {}).get("isError"))

    def test_execute_verification_passed(self):
        """Test workflow_execute_verification on a node whose verification passes."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "exec-proj",
                "nodes": [
                    {
                        "id": "pass-node",
                        "title": "Passing Node",
                        "kind": "work",
                        "status": "weak",
                        "data": {
                            "verification": {
                                "command": "python3 -c 'print(\"VERIFY_OK\")'",
                            }
                        },
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_execute_verification",
                    {"project": "exec-proj", "node_id": "pass-node"},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "passed")
                self.assertEqual(data["exit_code"], 0)
                self.assertIn("VERIFY_OK", data["stdout"])
                self.assertIsInstance(data["duration_seconds"], (int, float))

    def test_execute_verification_failed(self):
        """Test workflow_execute_verification on a node whose verification fails."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "exec-proj",
                "nodes": [
                    {
                        "id": "fail-node",
                        "title": "Failing Node",
                        "kind": "work",
                        "status": "weak",
                        "data": {
                            "check_command": "python3 -c 'import sys; sys.stderr.write(\"FAILED_TEST\\n\"); sys.exit(2)'",
                        },
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_execute_verification",
                    {"project": "exec-proj", "node_id": "fail-node"},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "failed")
                self.assertEqual(data["exit_code"], 2)
                self.assertIn("FAILED_TEST", data["stderr"])

    def test_execute_verification_missing_command(self):
        """Test workflow_execute_verification returns error when node has no verification configured."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "exec-proj",
                "nodes": [
                    {
                        "id": "no-cmd-node",
                        "title": "No Command Node",
                        "kind": "work",
                        "status": "weak",
                        "data": {},
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_execute_verification",
                    {"project": "exec-proj", "node_id": "no-cmd-node"},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertTrue(result.get("isError"))
                self.assertIn("no verification command", result["content"][0]["text"].lower())

    def test_execute_verification_timeout(self):
        """Test workflow_execute_verification handles command timeout gracefully."""
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            sample_tree = {
                "project": "exec-proj",
                "nodes": [
                    {
                        "id": "timeout-node",
                        "title": "Timeout Node",
                        "kind": "work",
                        "status": "weak",
                        "data": {
                            "verification": "sleep 10",
                        },
                    }
                ],
            }
            (proj_dir / "nodes.yaml").write_text(yaml.dump(sample_tree))
            with mock.patch("project_tree.model.project_dir", return_value=proj_dir):
                resp = self._call_tool(
                    "workflow_execute_verification",
                    {"project": "exec-proj", "node_id": "timeout-node", "timeout": 0.1},
                )
                self.assertIsNotNone(resp)
                result = resp.get("result", {})
                self.assertNotIn("isError", result)
                data = json.loads(result["content"][0]["text"])
                self.assertEqual(data["status"], "failed")
                self.assertNotEqual(data["exit_code"], 0)
                self.assertIn("timed out", data["stderr"].lower())


if __name__ == "__main__":
    unittest.main()

