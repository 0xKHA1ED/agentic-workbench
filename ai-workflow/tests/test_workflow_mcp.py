"""Unit tests for the Core MCP Protocol Server & Dispatch Engine."""

import io
import json
import sys
import unittest
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
        @register_tool("mod_tool", "Module level tool")
        def mod_handler(args):
            return "ok"

        self.assertIn("mod_tool", workflow_mcp.default_server.tools)

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


if __name__ == "__main__":
    unittest.main()
