from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from project_tree.fragments import compose_tree
from project_tree.model import find_node_in_tree, load_tree

from .model import (
    clarify_paths,
    complete_clarify,
    constitution_path,
    ensure_decisions,
    infer_taxonomy_mode,
    load_decisions,
    normalize_decisions,
)


def cmd_paths(args: argparse.Namespace) -> int:
    paths = clarify_paths(args.project, args.node_id)
    payload: dict = {
        "project": args.project,
        "node_id": args.node_id,
        **paths,
    }
    const = constitution_path(args.project)
    payload["constitution_path"] = str(const) if const else None

    try:
        composed = compose_tree(load_tree(args.project), args.project)
        node = find_node_in_tree(composed, args.node_id)
        if node:
            data = node.get("data") or {}
            payload["node_title"] = node.get("title")
            payload["needs_clarify"] = data.get("needs_clarify")
            payload["pain"] = data.get("pain")
            payload["pattern"] = data.get("pattern")
            payload["taxonomy_mode"] = infer_taxonomy_mode(data)
    except Exception as exc:
        payload["node_lookup_error"] = str(exc)

    decisions_path = Path(paths["decisions_json"])
    if decisions_path.exists():
        doc = load_decisions(decisions_path)
        payload["clarify_status"] = doc.get("status")
        payload["questions_asked"] = doc.get("questions_asked")
    else:
        payload["clarify_status"] = None
        payload["questions_asked"] = 0

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        normalize_decisions(load_decisions(args.file))
        print("OK")
        return 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid: {exc}", file=sys.stderr)
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    mode = args.taxonomy or "full"
    if args.project and args.node_id:
        ensure_decisions(args.project, args.node_id, mode)
        paths = clarify_paths(args.project, args.node_id)
        print(paths["decisions_json"])
        return 0
    print("Usage: init requires --project and --node-id", file=sys.stderr)
    return 1


def cmd_complete(args: argparse.Namespace) -> int:
    deferred = [s.strip() for s in args.deferred.split(",") if s.strip()] if args.deferred else []
    outstanding = (
        [s.strip() for s in args.outstanding.split(",") if s.strip()] if args.outstanding else []
    )
    doc = complete_clarify(
        args.project,
        args.node_id,
        deferred_categories=deferred,
        outstanding_categories=outstanding,
        status=args.status,
    )
    print(json.dumps({"status": doc["status"], "decisions_json": clarify_paths(args.project, args.node_id)["decisions_json"]}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spec clarify — paths and validation for clarification artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve artifact paths for a node")
    p_paths.add_argument("project")
    p_paths.add_argument("node_id")
    p_paths.add_argument("--json", action="store_true")

    p_val = sub.add_parser("validate", help="Validate a decisions JSON file")
    p_val.add_argument("file", type=Path)

    p_init = sub.add_parser("init", help="Create in_progress decisions file")
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--node-id", required=True)
    p_init.add_argument("--taxonomy", choices=["full", "tooling"])

    p_done = sub.add_parser("complete", help="Mark clarify session complete or skipped")
    p_done.add_argument("project")
    p_done.add_argument("node_id")
    p_done.add_argument("--status", choices=["complete", "skipped"], default="complete")
    p_done.add_argument("--deferred", default="", help="Comma-separated category names")
    p_done.add_argument("--outstanding", default="", help="Comma-separated category names")

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "complete":
        return cmd_complete(args)
    return 1
