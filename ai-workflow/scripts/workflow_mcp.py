#!/usr/bin/env python3
"""JSON-RPC 2.0 stdio Model Context Protocol (MCP) server for ai-workflow."""

import copy
import difflib
import inspect
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Union

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from project_tree import fragments, model, ops as tree_ops
from project_tree.fragments import compose_tree, walk_nodes
from project_tree.model import (
    find_node_in_tree,
    find_parent_in_tree,
    list_pending_proposals,
    load_tree,
)
from project_tree.decay import scan_decay
from project_tree.verify_runner import run_verification, verification_spec_from_node_data
from spec_discovery.model import (
    VALID_KINDS,
    claims_dir,
    is_vague,
    save_document,
)
from spec_clarify.model import (
    append_decision,
    clarify_blocks_claims,
    clarify_paths,
    complete_clarify,
    constitution_path,
    ensure_decisions,
    infer_taxonomy_mode,
    load_decisions,
)


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
            bound = None

            # Attempt keyword binding first
            try:
                bound = sig.bind(**arguments)
            except TypeError:
                # If keyword binding fails, check if handler expects a single dictionary/generic parameter
                if len(sig.parameters) == 1:
                    param = next(iter(sig.parameters.values()))
                    if (
                        param.annotation in (dict, Dict)
                        or (
                            param.name not in arguments
                            and param.annotation in (inspect.Parameter.empty, Any)
                        )
                    ):
                        try:
                            bound = sig.bind(arguments)
                        except TypeError:
                            pass

            # If still not bound, re-bind with kwargs to raise clear signature TypeError
            if bound is None:
                bound = sig.bind(**arguments)

            bound.apply_defaults()
            res = handler(*bound.args, **bound.kwargs)

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


def workflow_orient(project: str, filter: str = "weak") -> Dict[str, Any]:
    """Fetch high-level project orientation: active weak nodes, broken invariants, and pending contracts."""
    filter_mode = (filter or "weak").lower()
    if filter_mode not in ("weak", "decayed", "all"):
        raise ValueError(f"Invalid filter '{filter}': must be one of 'weak', 'decayed', 'all'")

    raw_tree = load_tree(project)
    composed = compose_tree(raw_tree, project)
    all_nodes = list(walk_nodes(composed.get("nodes") or []))
    total_nodes = len(all_nodes)

    def _clean_node_orient(node: Dict[str, Any]) -> Dict[str, Any]:
        entry = copy.deepcopy(node)
        entry.pop("children", None)
        return entry

    if filter_mode == "weak":
        filtered_nodes = [_clean_node_orient(n) for n in all_nodes if n.get("status") == "weak"]
    elif filter_mode == "decayed":
        filtered_nodes = [
            _clean_node_orient(n)
            for n in all_nodes
            if n.get("status") in ("decayed", "decayed_unverified")
            or bool(n.get("stale"))
            or bool((n.get("data") or {}).get("decayed"))
        ]
    else:  # "all"
        filtered_nodes = [_clean_node_orient(n) for n in all_nodes]

    filtered_count = len(filtered_nodes)

    pending_raw = list_pending_proposals(project)
    pending_proposals = [
        {
            "target": target or "root",
            "fragment": target,
            "path": str(path),
        }
        for target, path in pending_raw
    ]

    summary = (
        f"Project '{project}' orientation: {total_nodes} total nodes, "
        f"{filtered_count} matching filter '{filter_mode}'. "
        f"Pending proposals: {len(pending_proposals)}."
    )

    return {
        "project": project,
        "total_nodes": total_nodes,
        "filtered_count": filtered_count,
        "filter": filter_mode,
        "nodes": filtered_nodes,
        "pending_proposals": pending_proposals,
        "has_pending_proposals": len(pending_proposals) > 0,
        "summary": summary,
    }


def workflow_get_node(project: str, node_id: str) -> Dict[str, Any]:
    """Retrieve deep context for a specific tree node: pain, pattern, linked claims, spec, and verification status."""
    raw_tree = load_tree(project)
    composed = compose_tree(raw_tree, project)

    node = find_node_in_tree(composed, node_id)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found in project '{project}'")

    parent = find_parent_in_tree(composed, node_id)
    parent_payload = None
    if parent:
        parent_payload = {
            "id": parent.get("id"),
            "title": parent.get("title"),
            "kind": parent.get("kind"),
            "status": parent.get("status"),
        }
        if "data" in parent:
            parent_payload["data"] = copy.deepcopy(parent["data"])

    node_data = copy.deepcopy(node.get("data") or {})
    payload = {
        "project": project,
        "id": node.get("id"),
        "node_id": node.get("id"),
        "title": node.get("title"),
        "kind": node.get("kind"),
        "status": node.get("status"),
        "data": node_data,
        "parent": parent_payload,
        "parent_id": parent.get("id") if parent else None,
        "children": copy.deepcopy(node.get("children") or []),
        "node": copy.deepcopy(node),
    }
    if "stale" in node:
        payload["stale"] = node["stale"]

    paths = clarify_paths(project, node_id)
    decisions_path = Path(paths["decisions_json"])
    payload["clarify"] = {
        **paths,
        "constitution_path": str(constitution_path(project)) if constitution_path(project) else None,
        "taxonomy_mode": infer_taxonomy_mode(node_data),
        "needs_clarify": node_data.get("needs_clarify"),
    }
    if decisions_path.exists():
        try:
            doc = load_decisions(decisions_path)
            payload["clarify"]["status"] = doc.get("status")
            payload["clarify"]["questions_asked"] = doc.get("questions_asked")
            payload["clarify"]["decisions"] = copy.deepcopy(doc.get("decisions") or [])
        except ValueError:
            payload["clarify"]["status"] = "invalid"
    else:
        payload["clarify"]["status"] = None
        payload["clarify"]["questions_asked"] = 0

    return payload


def workflow_clarify_context(project: str, node_id: str) -> Dict[str, Any]:
    """Resolve clarify artifact paths, taxonomy mode, constitution, and session state for a node."""
    node_payload = workflow_get_node(project, node_id)
    clarify = node_payload.get("clarify") or {}
    const = constitution_path(project)
    constitution_excerpt = None
    if const:
        text = const.read_text(encoding="utf-8")
        constitution_excerpt = text[:4000] + ("…" if len(text) > 4000 else "")
    return {
        "project": project,
        "node_id": node_id,
        "node_title": node_payload.get("title"),
        "pain": (node_payload.get("data") or {}).get("pain"),
        "pattern": (node_payload.get("data") or {}).get("pattern"),
        "needs_clarify": (node_payload.get("data") or {}).get("needs_clarify"),
        "taxonomy_mode": clarify.get("taxonomy_mode"),
        "paths": {
            "clarifications_md": clarify.get("clarifications_md"),
            "decisions_json": clarify.get("decisions_json"),
        },
        "constitution_path": clarify.get("constitution_path"),
        "constitution_excerpt": constitution_excerpt,
        "session": {
            "status": clarify.get("status"),
            "questions_asked": clarify.get("questions_asked", 0),
            "decisions": clarify.get("decisions") or [],
        },
    }


def workflow_clarify_record(
    project: str,
    node_id: str,
    question: str,
    answer: str,
    category: str = "general",
) -> Dict[str, Any]:
    """Append one clarification Q→A to decisions JSON and clarifications markdown."""
    composed = compose_tree(load_tree(project), project)
    node = find_node_in_tree(composed, node_id)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found in project '{project}'")
    mode = infer_taxonomy_mode(node.get("data") or {})
    doc = append_decision(
        project,
        node_id,
        question=question,
        answer=answer,
        category=category,
        taxonomy_mode=mode,
    )
    paths = clarify_paths(project, node_id)
    return {
        "status": "recorded",
        "project": project,
        "node_id": node_id,
        "questions_asked": doc["questions_asked"],
        "clarifications_md": paths["clarifications_md"],
        "decisions_json": paths["decisions_json"],
    }


def workflow_clarify_complete(
    project: str,
    node_id: str,
    deferred_categories: Optional[List[str]] = None,
    outstanding_categories: Optional[List[str]] = None,
    status: str = "complete",
) -> Dict[str, Any]:
    """Mark clarify session complete or skipped; write completion block (B+ deferred/outstanding)."""
    if status not in ("complete", "skipped"):
        raise ValueError("status must be 'complete' or 'skipped'")
    doc = complete_clarify(
        project,
        node_id,
        deferred_categories=deferred_categories or [],
        outstanding_categories=outstanding_categories or [],
        status=status,
    )
    paths = clarify_paths(project, node_id)
    return {
        "status": doc["status"],
        "project": project,
        "node_id": node_id,
        "deferred_categories": doc.get("deferred_categories"),
        "outstanding_categories": doc.get("outstanding_categories"),
        "clarifications_md": paths["clarifications_md"],
        "decisions_json": paths["decisions_json"],
        "next": "workflow_stage_contract_claims (read decisions; do not re-ask settled questions)",
    }


def _diff(before: str, after: str, path: str) -> str:
    """Compute unified diff between before and after strings."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def workflow_propose_tree_mutation(
    project: str,
    target_node_id: str,
    operation: str,
    payload: Dict[str, Any],
    fragment: Optional[str] = None,
) -> Dict[str, Any]:
    """Propose an atomic mutation to the project tree (add child, update pain, reparent, attach fragment). Stages change without blocking prompt."""
    if not project or not str(project).strip():
        raise ValueError("Parameter 'project' must be non-empty")
    if not target_node_id or not str(target_node_id).strip():
        raise ValueError("Parameter 'target_node_id' must be non-empty")
    if not operation or not str(operation).strip():
        raise ValueError("Parameter 'operation' must be non-empty")
    if payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        raise ValueError("Parameter 'payload' must be a dictionary")

    raw_tree = load_tree(project)

    target_path = None
    pending_path = None
    target_tree = None
    fragment_rel = None
    is_fragment = False

    if fragment:
        frag_full = fragments.resolve_fragment_path(project, fragment)
        target_path = frag_full
        pending_path = fragments.fragment_proposed_path(frag_full)
        frag_data = fragments.load_fragment_file(frag_full)
        target_tree = fragments.fragment_as_tree(frag_data, f"{project}:{fragment}")
        fragment_rel = fragment
        is_fragment = True
        if not find_node_in_tree(target_tree, target_node_id):
            raise ValueError(f"Node '{target_node_id}' not found in fragment '{fragment}'")
    else:
        # Check root tree first
        if find_node_in_tree(raw_tree, target_node_id) is not None:
            target_path = model.nodes_path(project)
            pending_path = model.proposed_path(project)
            target_tree = raw_tree
            is_fragment = False
        else:
            # Check fragments under project fragments/ directory
            frag_dir = model.project_dir(project) / "fragments"
            found = False
            if frag_dir.is_dir():
                for frag_file in sorted(frag_dir.glob("*.yaml")):
                    if frag_file.name.endswith(".proposed"):
                        continue
                    try:
                        frag_data = fragments.load_fragment_file(frag_file)
                        rel = f"fragments/{frag_file.name}"
                        tree_candidate = fragments.fragment_as_tree(frag_data, f"{project}:{rel}")
                        if find_node_in_tree(tree_candidate, target_node_id) is not None:
                            target_path = frag_file
                            pending_path = fragments.fragment_proposed_path(frag_file)
                            target_tree = tree_candidate
                            fragment_rel = rel
                            is_fragment = True
                            found = True
                            break
                    except Exception:
                        continue
            if not found:
                raise ValueError(f"Node '{target_node_id}' not found in project '{project}'")

    op_norm = operation.strip().lower().replace("-", "_")

    if is_fragment:
        before_text = yaml.dump(
            fragments.tree_as_fragment(target_tree),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    else:
        before_text = model.dump_tree(target_tree)

    if op_norm == "set_data":
        data_to_set = payload.get("data") if "data" in payload and isinstance(payload["data"], dict) else payload
        proposed_tree = tree_ops.set_data(target_tree, target_node_id, data_to_set)
    elif op_norm == "add_child":
        child_id = payload.get("node_id") or payload.get("id")
        if not child_id:
            raise ValueError("add_child requires 'id' or 'node_id' in payload")
        title = payload.get("title")
        if not title:
            raise ValueError("add_child requires 'title' in payload")
        kind = payload.get("kind", "work")
        status = payload.get("status", "weak")
        proposed_tree = tree_ops.add_child(
            target_tree,
            parent_id=target_node_id,
            node_id=child_id,
            title=title,
            kind=kind,
            status=status,
        )
        if "data" in payload and isinstance(payload["data"], dict):
            proposed_tree = tree_ops.set_data(proposed_tree, child_id, payload["data"])
    elif op_norm == "set_status":
        status = payload.get("status") if isinstance(payload, dict) else str(payload)
        if not status:
            raise ValueError("set_status requires 'status' in payload")
        proposed_tree = tree_ops.set_status(target_tree, target_node_id, status)
    elif op_norm == "mark_stale":
        notes = payload.get("notes") if isinstance(payload, dict) else None
        proposed_tree = tree_ops.mark_stale(target_tree, target_node_id, notes=notes)
    elif op_norm == "clear_stale":
        proposed_tree = tree_ops.clear_stale(target_tree, target_node_id)
    elif op_norm == "reparent":
        new_parent_id = payload.get("new_parent_id")
        if not new_parent_id:
            raise ValueError("reparent requires 'new_parent_id' in payload")
        proposed_tree = tree_ops.reparent(target_tree, target_node_id, new_parent_id)
    elif op_norm == "attach_subtree":
        child_id = payload.get("node_id") or payload.get("id")
        title = payload.get("title")
        fragment_path = payload.get("fragment_path") or payload.get("subtree")
        kind = payload.get("kind", "group")
        if not child_id or not title or not fragment_path:
            raise ValueError("attach_subtree requires 'id', 'title', and 'fragment_path' in payload")
        proposed_tree = tree_ops.attach_subtree(target_tree, target_node_id, child_id, title, fragment_path, kind)
    else:
        raise ValueError(
            f"Unsupported operation '{operation}': must be one of 'add_child', 'set_data', 'set_status', 'mark_stale', 'clear_stale', 'reparent', 'attach_subtree'"
        )

    target_label = fragment_rel if fragment_rel else "nodes.yaml"
    diff_label = f"{project}/{target_label}"

    if is_fragment:
        after_text = yaml.dump(
            fragments.tree_as_fragment(proposed_tree),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        fragments.save_fragment_file(pending_path, proposed_tree)
    else:
        after_text = model.dump_tree(proposed_tree)
        model.save_tree(project, proposed_tree, path=pending_path)

    diff = _diff(before_text, after_text, diff_label)

    return {
        "status": "staged",
        "project": project,
        "target_node_id": target_node_id,
        "operation": operation,
        "proposed_file": str(pending_path),
        "diff": diff,
    }


def workflow_stage_contract_claims(
    project: str,
    node_id: str,
    goal: str,
    claims: List[Dict[str, Any]],
    in_scope: Optional[List[str]] = None,
    out_scope: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Stage a set of falsifiable claims for user triage. Emits event to Cockpit and renders inline triage block."""
    if not project or not str(project).strip():
        raise ValueError("Parameter 'project' must be non-empty")
    if not node_id or not str(node_id).strip():
        raise ValueError("Parameter 'node_id' must be non-empty")
    if not goal or not str(goal).strip():
        raise ValueError("Parameter 'goal' must be a non-empty string")
    if not isinstance(claims, list) or len(claims) == 0:
        raise ValueError("Parameter 'claims' must be a non-empty list of claim objects")

    try:
        composed = compose_tree(load_tree(project), project)
        target = find_node_in_tree(composed, node_id)
        node_data = (target.get("data") or {}) if target else {}
    except Exception:
        node_data = {}
    block_msg = clarify_blocks_claims(project, node_id, node_data)
    if block_msg:
        raise ValueError(block_msg)

    formatted_claims = []
    for i, raw_claim in enumerate(claims):
        if not isinstance(raw_claim, dict):
            raise ValueError(f"Claim at index {i} must be an object")

        text = str(raw_claim.get("text") or "").strip()
        if not text:
            raise ValueError(f"Claim at index {i} is missing non-empty 'text'")

        if is_vague(text):
            claim_id_str = raw_claim.get("id") or f"c{i+1}"
            raise ValueError(f"Claim '{claim_id_str}' contains non-falsifiable / vague language: '{text}'")

        kind = raw_claim.get("kind", "verify")
        if kind not in VALID_KINDS:
            raise ValueError(f"Claim at index {i} has invalid kind '{kind}': must be one of {sorted(VALID_KINDS)}")

        claim_id = raw_claim.get("id") or f"c{i+1}"
        decision = raw_claim.get("decision", "pending")

        entry: Dict[str, Any] = {
            "id": claim_id,
            "kind": kind,
            "text": text,
            "decision": decision,
        }
        if "check_command" in raw_claim:
            entry["check_command"] = raw_claim["check_command"]
        if "source_file" in raw_claim or "source" in raw_claim:
            src = raw_claim.get("source_file") or raw_claim.get("source")
            entry["source"] = src
            if "source_file" in raw_claim:
                entry["source_file"] = raw_claim["source_file"]
        if "examples" in raw_claim:
            entry["examples"] = raw_claim["examples"]

        formatted_claims.append(entry)

    node_title = node_id
    try:
        raw_tree = load_tree(project)
        composed = compose_tree(raw_tree, project)
        n = find_node_in_tree(composed, node_id)
        if n and n.get("title"):
            node_title = n["title"]
    except Exception:
        pass

    doc: Dict[str, Any] = {
        "project": project,
        "node": node_id,
        "node_id": node_id,
        "title": node_title,
        "goal": goal.strip(),
        "in": list(in_scope) if in_scope is not None else [],
        "out": list(out_scope) if out_scope is not None else [],
        "in_scope": list(in_scope) if in_scope is not None else [],
        "out_scope": list(out_scope) if out_scope is not None else [],
        "claims": formatted_claims,
        "goal_approved": None,
    }

    out_dir = claims_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    claims_file = out_dir / f"{node_id}.json"
    save_document(claims_file, doc)

    return {
        "status": "staged",
        "project": project,
        "node_id": node_id,
        "claims_path": str(claims_file),
        "claim_count": len(formatted_claims),
        "goal": goal.strip(),
    }


def workflow_decay_scan(
    project: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Scan a project for verified_strong pattern drift and decay stale nodes."""
    return scan_decay(project, dry_run=bool(dry_run))


def workflow_execute_verification(
    project: str,
    node_id: str,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Execute the verification suite for a node. Returns pass/fail status, stdout, and stderr."""
    raw_tree = load_tree(project)
    composed = compose_tree(raw_tree, project)
    node = find_node_in_tree(composed, node_id)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found in project '{project}'")

    data = node.get("data") or {}
    try:
        spec = verification_spec_from_node_data(data)
    except ValueError as exc:
        raise ValueError(f"Node '{node_id}' has no verification command configured in data") from exc

    repo_root = getattr(model, "REPO_ROOT", None) or model.host_root()
    result = run_verification(spec, Path(repo_root), timeout=float(timeout))

    return {
        "status": result["status"],
        "project": project,
        "node_id": node_id,
        "command": result["command"],
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "duration_seconds": result["duration_seconds"],
    }


def register_builtin_tools(server: MCPServer) -> None:
    """Register core workflow tools on an MCPServer instance."""
    server.register_tool(
        name="workflow_orient",
        description="Fetch high-level project orientation: active weak nodes, broken invariants, and pending contracts.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "filter": {
                    "type": "string",
                    "enum": ["weak", "decayed", "all"],
                    "default": "weak",
                    "description": "Filter node status (weak, decayed, or all)",
                },
            },
            "required": ["project"],
        },
        handler=workflow_orient,
    )

    server.register_tool(
        name="workflow_get_node",
        description="Retrieve deep context for a specific tree node: pain, pattern, linked claims, spec, and verification status.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "node_id": {
                    "type": "string",
                    "description": "Node identifier to fetch",
                },
            },
            "required": ["project", "node_id"],
        },
        handler=workflow_get_node,
    )

    server.register_tool(
        name="workflow_clarify_context",
        description="Load clarify session paths, taxonomy mode (full vs tooling), constitution excerpt, and prior decisions for a node.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "node_id": {"type": "string"},
            },
            "required": ["project", "node_id"],
        },
        handler=workflow_clarify_context,
    )

    server.register_tool(
        name="workflow_clarify_record",
        description="Record one clarification Q→A (max 5 per session). Updates clarifications/*.md and *.decisions.json.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "node_id": {"type": "string"},
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "category": {"type": "string", "default": "general"},
            },
            "required": ["project", "node_id", "question", "answer"],
        },
        handler=workflow_clarify_record,
    )

    server.register_tool(
        name="workflow_clarify_complete",
        description="Finish clarify session (complete or skipped). Optional deferred/outstanding category lists (B+ completion block).",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "node_id": {"type": "string"},
                "deferred_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "outstanding_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "status": {
                    "type": "string",
                    "enum": ["complete", "skipped"],
                    "default": "complete",
                },
            },
            "required": ["project", "node_id"],
        },
        handler=workflow_clarify_complete,
    )

    server.register_tool(
        name="workflow_propose_tree_mutation",
        description="Propose an atomic mutation to the project tree (add child, update pain, reparent, attach fragment). Stages change without blocking prompt.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "target_node_id": {
                    "type": "string",
                    "description": "ID of node being modified or targeted as parent",
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "add_child",
                        "set_data",
                        "set_status",
                        "mark_stale",
                        "clear_stale",
                        "reparent",
                        "attach_subtree",
                    ],
                    "description": "Mutation operation type",
                },
                "payload": {
                    "type": "object",
                    "description": "Operation payload (e.g. child attributes, data dictionary, status)",
                },
            },
            "required": ["project", "target_node_id", "operation", "payload"],
        },
        handler=workflow_propose_tree_mutation,
    )

    server.register_tool(
        name="workflow_stage_contract_claims",
        description="Stage a set of falsifiable claims for user triage. Emits event to Cockpit and renders inline triage block.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "node_id": {
                    "type": "string",
                    "description": "Node identifier to stage claims for",
                },
                "goal": {
                    "type": "string",
                    "description": "High-level goal statement for the node contract",
                },
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "kind": {"type": "string", "enum": ["verify", "must", "must_not"]},
                            "text": {"type": "string"},
                            "check_command": {"type": "string"},
                            "source_file": {"type": "string"},
                        },
                        "required": ["id", "kind", "text"],
                    },
                    "description": "Array of falsifiable claims",
                },
                "in_scope": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "In-scope items list",
                },
                "out_scope": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Out-of-scope items list",
                },
            },
            "required": ["project", "node_id", "goal", "claims"],
        },
        handler=workflow_stage_contract_claims,
    )

    server.register_tool(
        name="workflow_execute_verification",
        description="Execute the verification suite for a node. Returns pass/fail status, stdout, and stderr.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "node_id": {
                    "type": "string",
                    "description": "Node identifier whose verification check will be run",
                },
            },
            "required": ["project", "node_id"],
        },
        handler=workflow_execute_verification,
    )

    server.register_tool(
        name="workflow_decay_scan",
        description="Scan verified_strong nodes for pattern fingerprint drift and decay or refresh them.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project initiative name (e.g. 'tik')",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "Report decay actions without writing nodes.yaml",
                },
            },
            "required": ["project"],
        },
        handler=workflow_decay_scan,
    )



# Register builtin tools on default server
register_builtin_tools(default_server)


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
