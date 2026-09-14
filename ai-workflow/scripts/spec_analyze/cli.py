from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import (
    AnalyzeAbort,
    analyze_paths,
    complete_analyze,
    load_status,
    run_analyze,
    skip_analyze,
)


def cmd_paths(args: argparse.Namespace) -> int:
    paths = analyze_paths(args.project, args.node_id)
    payload: dict = {
        "project": args.project,
        "node_id": args.node_id,
        **paths,
        "claims_exists": Path(paths["claims_json"] or "").is_file(),
        "contract_exists": Path(paths["contract_md"] or "").is_file(),
        "plan_exists": bool(paths.get("plan_md") and Path(str(paths["plan_md"])).is_file()),
        "tasks_exists": bool(paths.get("tasks_md") and Path(str(paths["tasks_md"])).is_file()),
    }
    status_path = Path(paths["status_json"] or "")
    if status_path.is_file():
        try:
            doc = load_status(status_path)
            payload["analyze_status"] = doc.get("status")
            payload["critical_count"] = doc.get("critical_count", 0)
        except (ValueError, json.JSONDecodeError):
            payload["analyze_status"] = "invalid"
    else:
        payload["analyze_status"] = None

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        doc = run_analyze(args.project, args.node_id)
    except AnalyzeAbort as exc:
        print(str(exc), file=sys.stderr)
        return 1
    paths = analyze_paths(args.project, args.node_id)
    print(
        json.dumps(
            {
                "status": "in_progress",
                "findings_json": paths["findings_json"],
                "status_json": paths["status_json"],
                "findings_count": len(doc.get("findings") or []),
                "critical_count": doc.get("critical_count", 0),
            }
        )
    )
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    try:
        doc = complete_analyze(args.project, args.node_id, status=args.status)
    except AnalyzeAbort as exc:
        print(str(exc), file=sys.stderr)
        return 1
    paths = analyze_paths(args.project, args.node_id)
    print(
        json.dumps(
            {
                "status": doc["status"],
                "findings_json": paths["findings_json"],
                "status_json": paths["status_json"],
            }
        )
    )
    return 0


def cmd_skip(args: argparse.Namespace) -> int:
    doc = skip_analyze(args.project, args.node_id)
    paths = analyze_paths(args.project, args.node_id)
    print(
        json.dumps(
            {
                "status": doc["status"],
                "status_json": paths["status_json"],
                "findings_json": paths["findings_json"],
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Spec analyze — read-only claims/contract consistency before implement"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve artifact paths for a node")
    p_paths.add_argument("project")
    p_paths.add_argument("node_id")
    p_paths.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Compute findings (does not mark complete)")
    p_run.add_argument("project")
    p_run.add_argument("node_id")

    p_done = sub.add_parser("complete", help="Run analyze and mark complete, or skip")
    p_done.add_argument("project")
    p_done.add_argument("node_id")
    p_done.add_argument("--status", choices=["complete", "skipped"], default="complete")

    p_skip = sub.add_parser("skip", help="Mark analyze skipped without requiring artifacts")
    p_skip.add_argument("project")
    p_skip.add_argument("node_id")

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "complete":
        return cmd_complete(args)
    if args.command == "skip":
        return cmd_skip(args)
    return 1
