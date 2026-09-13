#!/usr/bin/env python3
"""JSON-RPC 2.0 stdio Model Context Protocol (MCP) server for ai-workflow."""

import inspect
import json
import sys
from typing import Any, Callable, Dict, List, Optional, TextIO, Union

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-workflow"
SERVER_VERSION = "2.0.0"


class MCPServer:
    """Core Model Context Protocol (MCP) server engine implementing JSON-RPC 2.0."""

    def __init__(
        self,
        name: str = SERVER_NAME,
        version: str = SERVER_VERSION,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> None:
        self.name = name
        self.version = version
        self.protocol_version = protocol_version
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        handler: Optional[Callable[..., Any]] = None,
    ) -> Any:
        """Register an MCP tool either directly or as a decorator.

        Usage as decorator:
            @server.register_tool(name="my_tool", description="Does something", input_schema={...})
            def my_tool(args):
                ...

        Usage as method call:
            server.register_tool(name="my_tool", handler=my_tool_fn)
        """
        tool_meta = {
            "name": name,
            "description": description,
            "inputSchema": input_schema if input_schema is not None else {"type": "object"},
        }

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = {
                **tool_meta,
                "handler": fn,
            }
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    def handle_message(self, message: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process an incoming JSON-RPC 2.0 message (str or dict).

        Returns a JSON-RPC response dict, or None if the message is a notification.
        """
        # 1. Parse JSON if string
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(exc)}",
                    },
                }
        elif isinstance(message, dict):
            data = message
        else:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: message must be a JSON object or string",
                },
            }

        # 2. Validate JSON-RPC 2.0 object structure
        if not isinstance(data, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: payload must be a JSON object",
                },
            }

        req_id = data.get("id")
        is_notification = "id" not in data

        if data.get("jsonrpc") != "2.0":
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: 'jsonrpc' must be exactly '2.0'",
                },
            }

        method = data.get("method")
        if not isinstance(method, str):
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: 'method' must be a string",
                },
            }

        params = data.get("params")

        # 3. Dispatch method
        response_result = None
        response_error = None

        if method == "initialize":
            response_result = {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
        elif method in ("notifications/initialized", "initialized"):
            # Notifications do not receive any response
            return None
        elif method == "ping":
            response_result = {}
        elif method == "tools/list":
            tools_list: List[Dict[str, Any]] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"],
                }
                for t in self.tools.values()
            ]
            response_result = {"tools": tools_list}
        elif method == "tools/call":
            if params is None or not isinstance(params, dict):
                response_error = {
                    "code": -32602,
                    "message": "Invalid params: object expected for 'params'",
                }
            elif "name" not in params or not isinstance(params["name"], str):
                response_error = {
                    "code": -32602,
                    "message": "Invalid params: string 'name' is required in 'params'",
                }
            else:
                tool_name = params["name"]
                tool_args = params.get("arguments")
                if tool_args is None:
                    tool_args = {}
                elif not isinstance(tool_args, dict):
                    tool_args = {"value": tool_args}
                response_result = self._execute_tool(tool_name, tool_args)
        else:
            response_error = {
                "code": -32601,
                "message": f"Method not found: '{method}'",
            }

        # 4. Format response
        if is_notification:
            return None

        if response_error is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": response_error,
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": response_result,
        }

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered tool and format standard MCP content result."""
        if name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Unknown tool: '{name}'",
                    }
                ],
                "isError": True,
            }

        tool_entry = self.tools[name]
        handler = tool_entry["handler"]

        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())

            # If handler expects 1 argument or has single positional param, pass arguments dict
            if len(params) == 1 and params[0].kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                res = handler(arguments)
            else:
                try:
                    res = handler(**arguments)
                except TypeError:
                    res = handler(arguments)

            # Format tool result
            if isinstance(res, dict) and "content" in res:
                return res
            if isinstance(res, str):
                return {
                    "content": [{"type": "text", "text": res}],
                }
            return {
                "content": [{"type": "text", "text": json.dumps(res, indent=2)}],
            }
        except Exception as exc:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool '{name}': {str(exc)}",
                    }
                ],
                "isError": True,
            }


# Default module-level server instance
default_server = MCPServer()


def register_tool(
    name: str,
    description: str = "",
    input_schema: Optional[Dict[str, Any]] = None,
    handler: Optional[Callable[..., Any]] = None,
) -> Any:
    """Register a tool on the default module-level MCP server."""
    return default_server.register_tool(name, description, input_schema, handler)


def run_stdio_server(
    server: Optional[MCPServer] = None,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> None:
    """Run newline-delimited JSON-RPC stdio message loop."""
    if server is None:
        server = default_server
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    if stderr is None:
        stderr = sys.stderr

    for line in stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            response = server.handle_message(raw)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()
        except Exception as exc:
            stderr.write(f"Unexpected server error: {exc}\n")
            stderr.flush()


if __name__ == "__main__":
    run_stdio_server()
