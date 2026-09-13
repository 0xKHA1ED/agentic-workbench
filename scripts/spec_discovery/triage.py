from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .model import is_vague, pending_claims, save_document


def _read_key(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nProgress saved. Resume with the same review command.")
        raise SystemExit(0) from None


def _confirm_goal(data: dict[str, Any]) -> bool:
    goal = str(data.get("goal") or "").strip()
    if not goal:
        return True
    if data.get("goal_approved") is True:
        return True

    title = data.get("title") or data.get("node") or "spec"
    print(f"\n{'=' * 60}")
    print(f"GOAL for: {title}")
    print(f"{'=' * 60}")
    print(goal)
    if data.get("in"):
        print("\nIN:")
        for item in data["in"]:
            print(f"  - {item}")
    if data.get("out"):
        print("\nOUT:")
        for item in data["out"]:
            print(f"  - {item}")

    while True:
        ans = _read_key("\nApprove this GOAL? [y/n]: ")
        if ans in ("y", "yes"):
            data["goal_approved"] = True
            return True
        if ans in ("n", "no"):
            print("Fix GOAL in chat, then regenerate claims.json.")
            return False
        print("Please enter y or n.")


def _edit_claim_text(claim: dict[str, Any]) -> None:
    current = claim["text"]
    print(f"\nCurrent: {current}")
    print("New text (empty = keep current):")
    try:
        new = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nEdit cancelled.")
        return
    if new:
        claim["text"] = new


def _show_claim(index: int, total: int, claim: dict[str, Any]) -> None:
    kind = claim.get("kind", "verify").upper()
    print(f"\n{'=' * 60}")
    print(f"[{index}/{total}] {kind}")
    print(f"{'=' * 60}")
    print(claim["text"])
    if claim.get("source"):
        print(f"\nsource: {claim['source']}")
    if claim.get("rationale"):
        print(f"note: {claim['rationale']}")
    if is_vague(claim["text"]):
        print("\n⚠  Warning: looks vague / non-falsifiable (scope-contract rules)")


def _decide_claim(claim: dict[str, Any]) -> str | None:
    while True:
        ans = _read_key("\ny approve  n reject  s skip  e edit  q quit: ")
        if ans in ("y", "yes"):
            if is_vague(claim["text"]):
                confirm = _read_key("  Claim looks vague. Approve anyway? [y/n]: ")
                if confirm not in ("y", "yes"):
                    continue
            return "approved"
        if ans in ("n", "no"):
            return "rejected"
        if ans in ("s", "skip"):
            return "skipped"
        if ans in ("e", "edit"):
            _edit_claim_text(claim)
            _show_claim(0, 0, claim)
            continue
        if ans in ("q", "quit"):
            return None
        print("Please enter y, n, s, e, or q.")


def run_review(path: Path, reset: bool = False) -> int:
    from .model import load_document, normalize_document

    data = normalize_document(load_document(path))

    if reset:
        data["goal_approved"] = None
        for claim in data["claims"]:
            claim["decision"] = "pending"

    if not _confirm_goal(data):
        save_document(path, data)
        return 1

    queue = pending_claims(data)
    total = len(data["claims"])
    if not queue:
        print("No pending claims. Run assemble or pass --reset to triage again.")
        save_document(path, data)
        return 0

    print(f"\nTriage: {path}")
    print(f"Pending: {len(queue)} / {total} claims")

    done = 0
    for claim in queue:
        decided = sum(1 for c in data["claims"] if c["decision"] != "pending")
        _show_claim(decided + 1, total, claim)
        decision = _decide_claim(claim)
        if decision is None:
            break
        claim["decision"] = decision
        done += 1
        save_document(path, data)

    remaining = len(pending_claims(data))
    print(f"\nSaved {path}")
    print(f"Approved: {len([c for c in data['claims'] if c['decision'] == 'approved'])}")
    print(f"Rejected: {len([c for c in data['claims'] if c['decision'] == 'rejected'])}")
    print(f"Skipped:  {len([c for c in data['claims'] if c['decision'] == 'skipped'])}")
    print(f"Pending:  {remaining}")

    if remaining == 0 and data.get("goal_approved"):
        print(f"\nAll claims triaged. Assemble spec:")
        print(f"  python scripts/spec_discovery.py assemble {path}")
    return 0
