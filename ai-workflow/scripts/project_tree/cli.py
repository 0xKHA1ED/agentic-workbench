from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from . import fragments
from . import model
from . import ops
from . import patterns


def _diff(before: str, after: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _target_label(project: str, fragment_rel: str | None) -> str:
    base = model.project_dir(project)
    try:
        rel = base.relative_to(model.host_root())
    except ValueError:
        rel = base
    if fragment_rel:
        return f"{rel}/{fragment_rel}"
    return f"{rel}/nodes.yaml"


def _load_target(project: str, fragment_rel: str | None) -> tuple[dict[str, Any], Path]:
    if fragment_rel:
        path = fragments.resolve_fragment_path(project, fragment_rel)
        fragment = fragments.load_fragment_file(path)
        return fragments.fragment_as_tree(fragment, f"{project}:{fragment_rel}"), path
    return model.load_tree(project), model.nodes_path(project)


def _save_target(project: str, fragment_rel: str | None, tree: dict[str, Any], path: Path) -> None:
    if fragment_rel:
        fragments.save_fragment_file(path, tree)
    else:
        model.save_tree(project, tree, path=path)


def _pending_path(project: str, fragment_rel: str | None) -> Path:
    if fragment_rel:
        return fragments.fragment_proposed_path(fragments.resolve_fragment_path(project, fragment_rel))
    return model.proposed_path(project)


def _fragment_flag(fragment_rel: str | None) -> str:
    return f" --fragment {fragment_rel}" if fragment_rel else ""


def _pending_target_label(fragment_rel: str | None) -> str:
    return fragment_rel or "nodes.yaml"


def _pending_commands(project: str, fragment_rel: str | None) -> list[str]:
    flag = _fragment_flag(fragment_rel)
    return [
        f"pending {project}{flag}",
        f"apply {project}{flag}",
        f"reject {project}{flag}",
    ]


def _print_other_pending(project: str, fragment_rel: str | None) -> None:
    for frag, _ in model.list_pending_proposals(project):
        if frag == fragment_rel:
            continue
        print(f"  {_pending_target_label(frag)}:", file=sys.stderr)
        for cmd in _pending_commands(project, frag):
            print(f"    python scripts/project_tree.py {cmd}", file=sys.stderr)


def _apply_target(project: str, fragment_rel: str | None) -> int:
    pending = _pending_path(project, fragment_rel)
    if not pending.exists():
        others = model.list_pending_proposals(project)
        if others:
            print(
                f"Error: no pending proposal for {_pending_target_label(fragment_rel)}.",
                file=sys.stderr,
            )
            print("Pending elsewhere — use matching --fragment:", file=sys.stderr)
            _print_other_pending(project, fragment_rel)
            return 1
        print("Error: no pending proposal.", file=sys.stderr)
        return 1
    proposed = yaml_load(pending)
    target_path = (
        fragments.resolve_fragment_path(project, fragment_rel)
        if fragment_rel
        else model.nodes_path(project)
    )
    _save_target(project, fragment_rel, proposed, target_path)
    pending.unlink()
    label = _target_label(project, fragment_rel)
    print(f"Applied proposal to {label}")
    if fragment_rel:
        print(model.ascii_tree(proposed, composed=False))
    else:
        print(model.ascii_tree(_load_composed(project), composed=True))
    return 0


def _reject_target(project: str, fragment_rel: str | None) -> int:
    pending = _pending_path(project, fragment_rel)
    if not pending.exists():
        others = model.list_pending_proposals(project)
        if others:
            print(
                f"Error: no pending proposal for {_pending_target_label(fragment_rel)}.",
                file=sys.stderr,
            )
            print("Pending elsewhere — use matching --fragment:", file=sys.stderr)
            _print_other_pending(project, fragment_rel)
            return 1
        print("Error: no pending proposal.", file=sys.stderr)
        return 1
    pending.unlink()
    print("Proposal rejected.")
    return 0


def _interactive_confirm(project: str, fragment_rel: str | None, no_prompt: bool) -> int:
    flag = _fragment_flag(fragment_rel)
    if no_prompt:
        print("\nProposal pending (--no-prompt).")
        print(f"  Review: python scripts/project_tree.py pending {project}{flag}")
        print(f"  Apply:  python scripts/project_tree.py apply {project}{flag}")
        print(f"  Reject: python scripts/project_tree.py reject {project}{flag}")
        return 0
    if not sys.stdin.isatty():
        print("\nNon-interactive session — finish in your terminal:")
        print(f"  python scripts/project_tree.py pending {project}{flag}")
        print(f"  python scripts/project_tree.py apply {project}{flag}   # or reject")
        return 0
    while True:
        try:
            ans = input("\nApply this proposal? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nProposal left pending.")
            return 0
        if ans in ("y", "yes"):
            return _apply_target(project, fragment_rel)
        if ans in ("n", "no"):
            return _reject_target(project, fragment_rel)
        print("Please enter y or n.")


def _propose(
    project: str,
    fragment_rel: str | None,
    mutator: Callable[[dict], dict],
    summary: str | None = None,
    no_prompt: bool = False,
) -> int:
    existing = model.list_pending_proposals(project)
    if existing:
        print("Error: resolve pending proposal(s) before proposing again.", file=sys.stderr)
        for frag, _ in existing:
            flag = _fragment_flag(frag)
            print(f"  {_pending_target_label(frag)}:", file=sys.stderr)
            print(f"    python scripts/project_tree.py pending {project}{flag}", file=sys.stderr)
            print(f"    python scripts/project_tree.py apply {project}{flag}", file=sys.stderr)
            print(f"    python scripts/project_tree.py reject {project}{flag}", file=sys.stderr)
        return 1

    current, _ = _load_target(project, fragment_rel)
    before_text = model.dump_tree(current)
    try:
        proposed = mutator(current)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    after_text = model.dump_tree(proposed)
    label = _target_label(project, fragment_rel)
    diff = _diff(before_text, after_text, label)
    if not diff.strip():
        print("No changes.")
        return 0

    pending = _pending_path(project, fragment_rel)
    _save_target(project, fragment_rel, proposed, pending)
    if summary:
        print(f"Summary: {summary}\n")
    print(diff)
    print("\n---")
    return _interactive_confirm(project, fragment_rel, no_prompt)


def yaml_load(path: Path):
    import yaml

    with path.open() as f:
        return yaml.safe_load(f)


def _load_composed(project: str) -> dict[str, Any]:
    raw = model.load_tree(project)
    return fragments.compose_tree(raw, project)


def cmd_validate_patterns(args: argparse.Namespace) -> int:
    tree = model.load_tree(args.project)
    issues = patterns.collect_all_pattern_issues(
        args.project, tree, recursive=args.recursive
    )
    print(patterns.format_issues(issues))
    if args.strict and issues:
        return 1
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    raw = model.load_tree(args.project)
    refs = fragments.list_fragment_refs(raw)
    try:
        composed = fragments.compose_tree(raw, args.project)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    nodes = list(model.walk_nodes(composed.get("nodes") or []))
    print(f"Project: {args.project}")
    print(f"Fragments: {len(refs)}")
    for ref in refs:
        print(f"  - {ref}")
    print(f"Composed nodes: {len(nodes)}")
    if args.emit_json:
        import json as json_mod

        print(json_mod.dumps(composed, indent=2))
    return 0


def cmd_list_fragments(args: argparse.Namespace) -> int:
    tree = model.load_tree(args.project)
    refs = fragments.list_fragment_refs(tree)
    frag_dir = model.project_dir(args.project) / "fragments"
    on_disk = sorted(p.relative_to(model.project_dir(args.project)).as_posix() for p in frag_dir.glob("*.yaml")) if frag_dir.exists() else []
    print(f"Project: {args.project}")
    print("Linked subtrees:")
    if refs:
        for ref in refs:
            print(f"  - {ref}")
    else:
        print("  (none)")
    print("Fragment files on disk:")
    if on_disk:
        for path in on_disk:
            marker = " [linked]" if path in refs else " [unlinked]"
            print(f"  - {path}{marker}")
    else:
        print("  (none)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    if args.fragment:
        tree, _ = _load_target(args.project, args.fragment)
        print(model.ascii_tree(tree, composed=False))
    elif args.raw:
        tree = model.load_tree(args.project)
        print(model.ascii_tree(tree, composed=False))
    else:
        tree = _load_composed(args.project)
        print(model.ascii_tree(tree, composed=True))
    for frag, _ in model.list_pending_proposals(args.project):
        flag = _fragment_flag(frag)
        print(
            f"\n⚠ Pending on {_pending_target_label(frag)} — "
            f"pending / apply / reject {args.project}{flag}"
        )
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    pending = _pending_path(args.project, args.fragment)
    current, _ = _load_target(args.project, args.fragment)
    if not pending.exists():
        others = model.list_pending_proposals(args.project)
        if others:
            print(f"No pending proposal for {_pending_target_label(args.fragment)}.")
            print("Pending elsewhere:")
            for frag, _ in others:
                flag = _fragment_flag(frag)
                print(f"  {_pending_target_label(frag)}: python scripts/project_tree.py pending {args.project}{flag}")
            return 0
        print("No pending proposal.")
        return 0
    proposed = yaml_load(pending)
    label = _target_label(args.project, args.fragment)
    diff = _diff(model.dump_tree(current), model.dump_tree(proposed), label)
    print(diff or "No diff.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    return _apply_target(args.project, args.fragment)


def cmd_reject(args: argparse.Namespace) -> int:
    return _reject_target(args.project, args.fragment)


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
        args.fragment,
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
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "set-constraint", [key, *values]), no_prompt=args.no_prompt)

    if op == "add-child":
        if len(args.rest) < 3:
            print("Usage: propose <project> add-child <parent_id> <id> <title> [kind] [status]", file=sys.stderr)
            return 1
        parent_id, node_id, title = args.rest[0], args.rest[1], args.rest[2]
        kind = args.rest[3] if len(args.rest) > 3 else "work"
        status = args.rest[4] if len(args.rest) > 4 else "weak"
        return _propose(
            args.project,
            args.fragment,
            lambda t: ops.apply_op(t, "add-child", [parent_id, node_id, title, kind, status]),
            no_prompt=args.no_prompt,
        )

    if op == "set-data":
        node_id = args.rest[0]
        try:
            data = json.loads(args.rest[1])
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON for set-data: {e}", file=sys.stderr)
            return 1
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "set-data", [node_id, data]), no_prompt=args.no_prompt)

    if op == "set-all-weak":
        preserve = list(args.rest)
        return _propose(
            args.project,
            args.fragment,
            lambda t: ops.apply_op(t, "set-all-weak", preserve),
            summary="Set all nodes to weak (preserving: " + (", ".join(preserve) or "strong") + ")",
            no_prompt=args.no_prompt,
        )

    if op == "set-status":
        node_id, status = args.rest[0], args.rest[1]
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "set-status", [node_id, status]), no_prompt=args.no_prompt)

    if op == "mark-stale":
        node_id = args.rest[0]
        notes = args.rest[1] if len(args.rest) > 1 else None
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "mark-stale", [node_id, notes]), no_prompt=args.no_prompt)

    if op == "clear-stale":
        node_id = args.rest[0]
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "clear-stale", [node_id]), no_prompt=args.no_prompt)

    if op == "rename":
        if len(args.rest) < 2:
            print("Usage: propose <project> rename <node_id> <new_title>", file=sys.stderr)
            return 1
        node_id, title = args.rest[0], " ".join(args.rest[1:])
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "rename", [node_id, title]), no_prompt=args.no_prompt)

    if op == "reparent":
        if len(args.rest) < 2:
            print("Usage: propose <project> reparent <node_id> <new_parent_id>", file=sys.stderr)
            return 1
        node_id, new_parent_id = args.rest[0], args.rest[1]
        return _propose(
            args.project,
            args.fragment,
            lambda t: ops.apply_op(t, "reparent", [node_id, new_parent_id]),
            no_prompt=args.no_prompt,
        )

    if op == "attach-subtree":
        if len(args.rest) < 4:
            print(
                "Usage: propose <project> attach-subtree <parent_id> <id> <title> <fragment_path>",
                file=sys.stderr,
            )
            return 1
        parent_id, node_id, title, fragment_path = args.rest[0], args.rest[1], args.rest[2], args.rest[3]
        kind = args.rest[4] if len(args.rest) > 4 else "group"
        return _propose(
            args.project,
            args.fragment,
            lambda t: ops.apply_op(t, "attach-subtree", [parent_id, node_id, title, fragment_path, kind]),
            no_prompt=args.no_prompt,
        )

    if op == "add-group":
        parent_id, node_id, title = args.rest[0], args.rest[1], args.rest[2]
        return _propose(args.project, args.fragment, lambda t: ops.apply_op(t, "add-group", [parent_id, node_id, title]), no_prompt=args.no_prompt)

    print(f"Unknown operation: {op}", file=sys.stderr)
    return 1


def _extract_global_flags(argv: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Remove global flags from anywhere in argv before positional parsing."""
    opts: dict[str, Any] = {}
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--fragment" and i + 1 < len(argv):
            opts["fragment"] = argv[i + 1]
            i += 2
            continue
        if token == "--json" and i + 1 < len(argv):
            opts["json"] = argv[i + 1]
            i += 2
            continue
        if token == "--file" and i + 1 < len(argv):
            opts["file"] = argv[i + 1]
            i += 2
            continue
        if token == "--raw":
            opts["raw"] = True
            i += 1
            continue
        if token == "--recursive":
            opts["recursive"] = True
            i += 1
            continue
        if token == "--strict":
            opts["strict"] = True
            i += 1
            continue
        if token == "--emit-json":
            opts["emit_json"] = True
            i += 1
            continue
        if token == "--no-prompt":
            opts["no_prompt"] = True
            i += 1
            continue
        cleaned.append(token)
        i += 1
    return cleaned, opts


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv, global_opts = _extract_global_flags(argv)

    parser = argparse.ArgumentParser(description="Project tree CLI — propose, diff, apply, compose")
    parser.add_argument(
        "command",
        choices=[
            "show",
            "propose",
            "apply",
            "reject",
            "pending",
            "validate-patterns",
            "compose",
            "list-fragments",
        ],
    )
    parser.add_argument("project", help="Project name (meta, examples/*, or host projects/*)")
    parser.add_argument("operation", nargs="?", help="Propose operation name (or 'batch')")
    parser.add_argument("rest", nargs=argparse.REMAINDER, help="Operation arguments")
    parser.add_argument(
        "--fragment",
        metavar="PATH",
        default=None,
        help="Fragment YAML relative to project dir (for propose/apply/show)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="For show: display root nodes.yaml without composing fragments",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="For validate-patterns: also validate linked fragment files",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="For validate-patterns: exit 1 if any issue found",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="For compose: print composed tree as JSON",
    )
    parser.add_argument("--json", dest="json", default=None, help="Batch ops JSON")
    parser.add_argument("--file", dest="file", default=None, help="Batch ops JSON file")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip y/n prompt (for agents). Default: prompt in interactive terminal.",
    )

    args = parser.parse_args(argv)
    for key, value in global_opts.items():
        setattr(args, key, value)
    if not hasattr(args, "no_prompt"):
        args.no_prompt = False

    if args.command == "validate-patterns":
        return cmd_validate_patterns(args)
    if args.command == "compose":
        return cmd_compose(args)
    if args.command == "list-fragments":
        return cmd_list_fragments(args)
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
