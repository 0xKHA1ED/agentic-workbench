from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from project_tree.fragments import compose_tree
from project_tree.model import find_node_in_tree, load_tree

from .model import init_plan, plan_paths, plan_rel, validate_node_id


def _node_context(project: str, node_id: str) -> dict[str, Any]:
    extra: dict[str, Any] = {"data_plan": None, "node_title": None}
    try:
        composed = compose_tree(load_tree(project), project)
        node = find_node_in_tree(composed, node_id)
        if node:
            data = node.get("data") or {}
            extra["node_title"] = node.get("title")
            extra["data_plan"] = data.get("plan")
    except Exception as exc:
        extra["node_lookup_error"] = str(exc)
    return extra


def _payload(project: str, node_id: str, paths: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": project,
        "node_id": node_id,
        "link": {"plan": plan_rel(node_id)},
        **_node_context(project, node_id),
        **paths,
    }


def _print(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def cmd_paths(args: argparse.Namespace) -> int:
    try:
        validate_node_id(args.node_id)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    paths = plan_paths(args.project, args.node_id)
    _print(_payload(args.project, args.node_id, paths), args.json)
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    try:
        validate_node_id(args.node_id)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    extra = _node_context(args.project, args.node_id)
    result = init_plan(
        args.project,
        args.node_id,
        title=extra.get("node_title"),
        overwrite=args.force,
    )
    _print(_payload(args.project, args.node_id, result), args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve optional technical-plan artifact paths (HOW, not the scope contract)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve plan.md path and data.plan link for a node")
    p_paths.add_argument("project")
    p_paths.add_argument("node_id")
    p_paths.add_argument("--json", action="store_true")

    p_init = sub.add_parser("init", help="Write a HOW stub at plans/<node-id>.plan.md if missing")
    p_init.add_argument("project")
    p_init.add_argument("node_id")
    p_init.add_argument("--json", action="store_true")
    p_init.add_argument("--force", action="store_true", help="Overwrite an existing plan file")

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "init":
        return cmd_init(args)
    return 1
