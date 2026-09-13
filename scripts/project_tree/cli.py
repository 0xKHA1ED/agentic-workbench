from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from . import model
from . import ops


def _diff(before: str, after: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _apply_project(project: str) -> int:
    pending = model.proposed_path(project)
    if not pending.exists():
        print("Error: no pending proposal.", file=sys.stderr)
        return 1
    proposed = yaml_load(pending)
    model.save_tree(project, proposed, path=model.nodes_path(project))
    pending.unlink()
    print(f"Applied proposal to projects/{project}/nodes.yaml")
    print(model.ascii_tree(model.load_tree(project)))
    return 0


def _reject_project(project: str) -> int:
    pending = model.proposed_path(project)
    if not pending.exists():
        print("Error: no pending proposal.", file=sys.stderr)
        return 1
    pending.unlink()
    print("Proposal rejected.")
    return 0


def _interactive_confirm(project: str, no_prompt: bool) -> int:
    if no_prompt:
        print("\nProposal pending (--no-prompt).")
        print(f"  Apply:  python scripts/project_tree.py apply {project}")
        print(f"  Reject: python scripts/project_tree.py reject {project}")
        return 0
    if not sys.stdin.isatty():
        print("\nNon-interactive session — re-run in your terminal for y/n prompt:")
        print(f"  python scripts/project_tree.py pending {project}")
        print(f"  python scripts/project_tree.py apply {project}   # or reject")
        return 0
    while True:
        try:
            ans = input("\nApply this proposal? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nProposal left pending.")
            return 0
        if ans in ("y", "yes"):
            return _apply_project(project)
        if ans in ("n", "no"):
            return _reject_project(project)
        print("Please enter y or n.")


def _propose(
    project: str,
    mutator: Callable[[dict], dict],
    summary: str | None = None,
    no_prompt: bool = False,
) -> int:
    pending = model.proposed_path(project)
    if pending.exists():
        print("Error: a proposal is already pending. Run `apply` or `reject` first.", file=sys.stderr)
        return 1

    current = model.load_tree(project)
    before_text = model.dump_tree(current)
    try:
        proposed = mutator(current)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    after_text = model.dump_tree(proposed)
    diff = _diff(before_text, after_text, f"projects/{project}/nodes.yaml")
    if not diff.strip():
        print("No changes.")
        return 0

    model.save_tree(project, proposed, path=pending)
    if summary:
        print(f"Summary: {summary}\n")
    print(diff)
    print("\n---")
    return _interactive_confirm(project, no_prompt)


def yaml_load(path: Path):
    import yaml

    with path.open() as f:
        return yaml.safe_load(f)


def cmd_show(args: argparse.Namespace) -> int:
    tree = model.load_tree(args.project)
    print(model.ascii_tree(tree))
    pending = model.proposed_path(args.project)
    if pending.exists():
        print("\n⚠ Pending proposal — run apply or reject")
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    pending = model.proposed_path(args.project)
    current = model.load_tree(args.project)
    if not pending.exists():
        print("No pending proposal.")
        return 0
    proposed = yaml_load(pending)
    diff = _diff(model.dump_tree(current), model.dump_tree(proposed), f"projects/{args.project}/nodes.yaml")
    print(diff or "No diff.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    return _apply_project(args.project)


def cmd_reject(args: argparse.Namespace) -> int:
    return _reject_project(args.project)


def _parse_batch_ops(raw: str) -> tuple[str | None, list[dict]]:
    data = json.loads(raw)
    if isinstance(data, list):
        return None, data
    if isinstance(data, dict) and "ops" in data:
        return data.get("summary"), data["ops"]
    raise ValueError("Batch JSON must be a list of ops or {summary, ops}")


def _batch_payload(args: argparse.Namespace) -> str | None:
    if args.json:
        return args.json
    if args.file:
        return Path(args.file).read_text()
    rest = list(args.rest or [])
    i = 0
    while i < len(rest):
        if rest[i] == "--json" and i + 1 < len(rest):
            return rest[i + 1]
        if rest[i] == "--file" and i + 1 < len(rest):
            return Path(rest[i + 1]).read_text()
        i += 1
    return None


def cmd_propose_batch(args: argparse.Namespace) -> int:
    raw = _batch_payload(args)
    if not raw:
        print("Error: provide --json '<ops>' or --file batch.json", file=sys.stderr)
        return 1
    try:
        summary, operations = _parse_batch_ops(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return _propose(
        args.project,
        lambda t: ops.apply_batch(t, operations),
        summary=summary,
        no_prompt=args.no_prompt,
    )


def cmd_propose(args: argparse.Namespace) -> int:
    op = args.operation

    if op == "batch":
        return cmd_propose_batch(args)

    if op == "set-constraint":
        key, *values = args.rest
        return _propose(args.project, lambda t: ops.apply_op(t, "set-constraint", [key, *values]), no_prompt=args.no_prompt)

    if op == "add-child":
        if len(args.rest) < 3:
            print("Usage: propose <project> add-child <parent_id> <id> <title> [kind] [status]", file=sys.stderr)
            return 1
        parent_id, node_id, title = args.rest[0], args.rest[1], args.rest[2]
        kind = args.rest[3] if len(args.rest) > 3 else "work"
        status = args.rest[4] if len(args.rest) > 4 else "empty"
        return _propose(
            args.project,
            lambda t: ops.apply_op(t, "add-child", [parent_id, node_id, title, kind, status]),
            no_prompt=args.no_prompt,
        )

    if op == "set-data":
        node_id = args.rest[0]
        data = json.loads(args.rest[1])
        return _propose(args.project, lambda t: ops.apply_op(t, "set-data", [node_id, data]), no_prompt=args.no_prompt)

    if op == "set-status":
        node_id, status = args.rest[0], args.rest[1]
        return _propose(args.project, lambda t: ops.apply_op(t, "set-status", [node_id, status]), no_prompt=args.no_prompt)

    if op == "mark-stale":
        node_id = args.rest[0]
        notes = args.rest[1] if len(args.rest) > 1 else None
        return _propose(args.project, lambda t: ops.apply_op(t, "mark-stale", [node_id, notes]), no_prompt=args.no_prompt)

    if op == "include-meal":
        return _propose(args.project, lambda t: ops.apply_op(t, "include-meal", [args.rest[0]]), no_prompt=args.no_prompt)

    if op == "exclude-meal":
        return _propose(args.project, lambda t: ops.apply_op(t, "exclude-meal", [args.rest[0]]), no_prompt=args.no_prompt)

    if op == "add-group":
        parent_id, node_id, title = args.rest[0], args.rest[1], args.rest[2]
        return _propose(args.project, lambda t: ops.apply_op(t, "add-group", [parent_id, node_id, title]), no_prompt=args.no_prompt)

    if op == "add-allergies":
        parent_id = args.rest[0]
        allergies = args.rest[1:]
        as_children = "--children" in allergies
        if as_children:
            allergies = [a for a in allergies if a != "--children"]
        return _propose(
            args.project,
            lambda t: ops.apply_op(t, "add-allergies", [parent_id, *allergies], {"as_children": as_children}),
            no_prompt=args.no_prompt,
        )

    print(f"Unknown operation: {op}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project tree CLI — propose, diff, apply")
    parser.add_argument("command", choices=["show", "propose", "apply", "reject", "pending"])
    parser.add_argument("project", help="Project name (folder under projects/)")
    parser.add_argument("operation", nargs="?", help="Propose operation name (or 'batch')")
    parser.add_argument("rest", nargs=argparse.REMAINDER, help="Operation arguments")
    parser.add_argument("--json", dest="json", default=None, help="Batch ops JSON")
    parser.add_argument("--file", dest="file", default=None, help="Batch ops JSON file")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip y/n prompt (for agents). Default: prompt in interactive terminal.",
    )

    args = parser.parse_args(argv)
    if not hasattr(args, "no_prompt"):
        args.no_prompt = False

    if args.command == "show":
        return cmd_show(args)
    if args.command == "apply":
        return cmd_apply(args)
    if args.command == "reject":
        return cmd_reject(args)
    if args.command == "pending":
        return cmd_pending(args)
    if args.command == "propose":
        if not args.operation:
            print("Error: propose requires an operation.", file=sys.stderr)
            return 1
        return cmd_propose(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
