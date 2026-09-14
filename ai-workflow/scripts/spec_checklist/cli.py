from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import (
    checklist_paths,
    generate_checklist,
    scan_checklist_status,
    validate_checklist_file,
    validate_checklist_text,
)


def cmd_paths(args: argparse.Namespace) -> int:
    payload = {
        "project": args.project,
        "node_id": args.node_id,
        **checklist_paths(args.project, args.node_id),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    try:
        result = generate_checklist(
            args.project,
            args.node_id,
            domain=args.domain,
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Generate failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        action = "created" if result["created"] else f"appended {result['appended']}"
        print(f"{result['path']} ({action}; {result['total_items']} items, {result['checked']} checked)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    payload = scan_checklist_status(args.project, args.node_id)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"project: {payload['project']}  node: {payload['node_id']}")
        print(f"overall: {payload['overall']}  blocks_implement: {payload['blocks_implement']}")
        print(
            f"total={payload['total']} checked={payload['checked']} "
            f"unchecked={payload['unchecked']} (custom={payload['unchecked_custom']})"
        )
        if payload["checklists"]:
            print("file\ttotal\tchecked\tunchecked\tstatus\tkind")
            for row in payload["checklists"]:
                print(
                    f"{row['file']}\t{row['total']}\t{row['checked']}\t"
                    f"{row['unchecked']}\t{row['status']}\t{row['kind']}"
                )
        else:
            print("(no checklist files)")
        print(payload["note"])
    if args.gate and payload.get("blocks_implement"):
        return 2
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    target = args.path
    files: list[Path]
    if target.is_dir():
        files = sorted(p for p in target.glob("*.md") if p.is_file())
        if not files:
            print(f"Invalid: no markdown checklists in {target}", file=sys.stderr)
            return 1
    elif target.is_file():
        files = [target]
    else:
        print(f"Invalid: not found: {target}", file=sys.stderr)
        return 1

    failed = False
    for path in files:
        try:
            items = validate_checklist_file(path, require_unchecked=args.require_unchecked)
            print(f"OK {path} ({len(items)} items)")
        except (ValueError, FileNotFoundError, OSError) as exc:
            print(f"Invalid {path}: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def cmd_validate_text_for_tests(text: str, require_unchecked: bool = False) -> int:
    """Helper used by tests; not a CLI subcommand."""
    validate_checklist_text(text, require_unchecked=require_unchecked)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Requirements checklists — unit tests for English (user-only checkboxes)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve checklist paths for a node")
    p_paths.add_argument("project")
    p_paths.add_argument("node_id")
    p_paths.add_argument("--json", action="store_true")

    p_gen = sub.add_parser("generate", help="Generate or append a checklist from claims/assembled spec")
    p_gen.add_argument("project")
    p_gen.add_argument("node_id")
    p_gen.add_argument(
        "--domain",
        default="requirements",
        help="Filename stem (requirements.md built-in; other names are custom)",
    )
    p_gen.add_argument("--json", action="store_true")

    p_status = sub.add_parser("status", help="Read-only checkbox counts (implement gate)")
    p_status.add_argument("project")
    p_status.add_argument("node_id")
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument(
        "--gate",
        action="store_true",
        help="Exit 2 when unchecked items block /implement",
    )

    p_val = sub.add_parser("validate", help="Validate CHK ids and checkbox format")
    p_val.add_argument("path", type=Path, help="Checklist file or checklists/<node-id>/ directory")
    p_val.add_argument(
        "--require-unchecked",
        action="store_true",
        help="Fail if any item is [x] (generation / user-only contract)",
    )

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "generate":
        return cmd_generate(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "validate":
        return cmd_validate(args)
    return 1
