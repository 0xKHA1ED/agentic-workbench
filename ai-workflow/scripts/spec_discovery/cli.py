from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assemble import run_assemble
from .model import decision_counts, load_document, normalize_document
from .triage import run_review


def cmd_review(args: argparse.Namespace) -> int:
    return run_review(args.file, reset=args.reset)


def cmd_assemble(args: argparse.Namespace) -> int:
    return run_assemble(args.file, output=args.output)


def cmd_status(args: argparse.Namespace) -> int:
    data = normalize_document(load_document(args.file))
    counts = decision_counts(data)
    print(f"File: {args.file}")
    print(f"Project: {data.get('project', '?')}  Node: {data.get('node', '?')}")
    print(f"GOAL approved: {data.get('goal_approved')}")
    print(
        f"Claims: {len(data['claims'])} total — "
        f"approved={counts['approved']} rejected={counts['rejected']} "
        f"skipped={counts['skipped']} pending={counts['pending']}"
    )
    if data.get("spec_path"):
        print(f"Spec: {data['spec_path']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        normalize_document(load_document(args.file))
        print("OK")
        return 0
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Invalid: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Spec discovery — triage VERIFY claims, assemble scope contracts"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_review = sub.add_parser("review", help="Interactive y/n/s triage of claims")
    p_review.add_argument("file", type=Path, help="claims JSON file")
    p_review.add_argument("--reset", action="store_true", help="Reset all decisions")

    p_assemble = sub.add_parser("assemble", help="Build scope-contract markdown from approved claims")
    p_assemble.add_argument("file", type=Path, help="claims JSON file")
    p_assemble.add_argument("-o", "--output", type=Path, default=None, help="Output .md path")

    p_status = sub.add_parser("status", help="Show triage progress")
    p_status.add_argument("file", type=Path)

    p_validate = sub.add_parser("validate", help="Validate claims JSON schema")
    p_validate.add_argument("file", type=Path)

    args = parser.parse_args(argv)

    if args.command == "review":
        return cmd_review(args)
    if args.command == "assemble":
        return cmd_assemble(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "validate":
        return cmd_validate(args)
    return 1
