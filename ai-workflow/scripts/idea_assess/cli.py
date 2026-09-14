from __future__ import annotations

import argparse
import json
import sys

from .model import (
    assessment_paths,
    handoff_for,
    init_assessment,
    normalize_slug,
    slug_from_idea,
)


def _print_payload(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def cmd_paths(args: argparse.Namespace) -> int:
    try:
        payload = assessment_paths(args.project, args.slug)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    payload["handoff"] = handoff_for(payload.get("verdict"), args.node_id)
    _print_payload(payload, args.json)
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    slug = args.slug or slug_from_idea(args.idea or "")
    slug = normalize_slug(slug)
    if not slug:
        print("Error: init requires a slug or --idea to derive one", file=sys.stderr)
        return 1
    try:
        payload = init_assessment(
            args.project,
            slug,
            idea=args.idea,
            unique=args.unique,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["intake_md"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idea assess — go/kill funnel paths and intake scaffolding"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Resolve assessment artifact paths for a slug")
    p_paths.add_argument("project")
    p_paths.add_argument("slug")
    p_paths.add_argument("--node-id", default=None, help="Existing tree node to hand off on go")
    p_paths.add_argument("--json", action="store_true")

    p_init = sub.add_parser("init", help="Create assessments/<slug>/intake.md")
    p_init.add_argument("project")
    p_init.add_argument("slug", nargs="?", default=None)
    p_init.add_argument("--idea", default=None, help="Raw idea text for intake.md")
    p_init.add_argument("--unique", action="store_true", help="Suffix -2, -3 if slug exists")
    p_init.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "init":
        return cmd_init(args)
    return 1
