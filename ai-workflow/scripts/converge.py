#!/usr/bin/env python3
"""Converge — post-implement gap hunt (Epic H).

After implement, converge re-reads the scope-contract's ACCEPTANCE / VERIFY items
and **appends** any that are not yet reflected in the node's tasks file as new
open tasks. It only ever *adds* work — it never silently closes or checks items
(quality invariant: converge appends, humans adjudicate).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CONVERGE_HEADING = "## Converge — unmet acceptance (append-only)"
_CHECKBOX = re.compile(r"^\s*-\s*\[[ xX]\]\s*(.+?)\s*$")


def _section(markdown: str, heading: str) -> str:
    """Return the body of a ``## heading`` section, or empty string."""
    lines = markdown.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        if line.strip().startswith("## "):
            if capturing:
                break
            capturing = line.strip().lower() == f"## {heading}".lower()
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def contract_acceptance_items(contract_md: str) -> list[str]:
    """Extract ACCEPTANCE (then VERIFY) checkbox item texts from a contract."""
    items: list[str] = []
    for heading in ("ACCEPTANCE", "VERIFY"):
        body = _section(contract_md, heading)
        for line in body.splitlines():
            m = _CHECKBOX.match(line)
            if m:
                text = m.group(1).strip()
                if text and text.lower() != "(none)":
                    items.append(text)
    # De-dup preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            unique.append(it)
    return unique


def find_gaps(contract_md: str, tasks_md: str) -> list[str]:
    """Acceptance items whose text is not already present in the tasks doc."""
    acceptance = contract_acceptance_items(contract_md)
    tasks_lower = (tasks_md or "").lower()
    return [item for item in acceptance if item.lower() not in tasks_lower]


def converge(contract_path: Path | str, tasks_path: Path | str | None = None) -> dict[str, Any]:
    """Compute gaps and append them to the tasks file as new open tasks."""
    contract_path = Path(contract_path)
    contract_md = contract_path.read_text(encoding="utf-8")
    tasks_md = ""
    if tasks_path is not None:
        tasks_path = Path(tasks_path)
        if tasks_path.is_file():
            tasks_md = tasks_path.read_text(encoding="utf-8")

    gaps = find_gaps(contract_md, tasks_md)

    appended = 0
    if tasks_path is not None and gaps:
        block = [""] if tasks_md and not tasks_md.endswith("\n") else []
        if CONVERGE_HEADING not in tasks_md:
            block.append(CONVERGE_HEADING)
        block.extend(f"- [ ] {gap}" for gap in gaps)
        block.append("")
        with Path(tasks_path).open("a", encoding="utf-8") as f:
            f.write("\n".join(block))
        appended = len(gaps)

    return {
        "contract": str(contract_path),
        "tasks": str(tasks_path) if tasks_path is not None else None,
        "gaps": gaps,
        "appended": appended,
    }


def _cli(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(prog="converge", description="Post-implement gap hunt")
    parser.add_argument("contract", type=Path, help="Scope-contract markdown")
    parser.add_argument("--tasks", type=Path, default=None, help="Tasks markdown to append gaps to")
    args = parser.parse_args(argv)
    result = converge(args.contract, tasks_path=args.tasks)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
