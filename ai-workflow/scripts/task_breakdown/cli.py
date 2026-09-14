from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import (
    TaskBreakdownError,
    parse_tasks_markdown,
    scope_tasks,
    tasks_paths,
    write_tasks,
)


def cmd_paths(args: argparse.Namespace) -> int:
    paths = tasks_paths(args.project, args.node_id)
    payload = {
        "project": args.project,
        "node_id": args.node_id,
        **paths,
        "tasks_exists": Path(paths["tasks_md"]).is_file(),
        "claims_exists": Path(paths["claims_json"]).is_file(),
        "spec_exists": Path(paths["spec_md"]).is_file(),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    try:
        result = write_tasks(args.project, args.node_id)
    except TaskBreakdownError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"Wrote {result['tasks_md']} "
            f"({result['task_count']} tasks, {result['phase_count']} phases)"
        )
    return 0


def cmd_scope(args: argparse.Namespace) -> int:
    paths = tasks_paths(args.project, args.node_id)
    path = Path(paths["tasks_md"])
    if not path.is_file():
        print(
            f"tasks.md not found at {path}. Run task_breakdown generate first.",
            file=sys.stderr,
        )
        return 1
    parsed = parse_tasks_markdown(path.read_text(encoding="utf-8"))
    result = scope_tasks(parsed, phase=args.phase, tasks=args.tasks)
    result["project"] = args.project
    result["node_id"] = args.node_id
    result["tasks_md"] = str(path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for task in result["tasks"]:
            mark = "x" if task["done"] else " "
            print(f"- [{mark}] {task['id']} {task['description']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Task breakdown — generate phased tasks.md from claims/spec"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve tasks.md and related artifact paths")
    p_paths.add_argument("project")
    p_paths.add_argument("node_id")
    p_paths.add_argument("--json", action="store_true")

    p_gen = sub.add_parser("generate", help="Write <project>/tasks/<node-id>.md")
    p_gen.add_argument("project")
    p_gen.add_argument("node_id")
    p_gen.add_argument("--json", action="store_true")

    p_scope = sub.add_parser("scope", help="Filter tasks.md by phase marker or T00N range")
    p_scope.add_argument("project")
    p_scope.add_argument("node_id")
    p_scope.add_argument("--phase", default=None, help="Phase index or id (setup, 2, c1)")
    p_scope.add_argument("--tasks", default=None, help="Task selector, e.g. T001-T004")
    p_scope.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "generate":
        return cmd_generate(args)
    if args.command == "scope":
        return cmd_scope(args)
    return 1
