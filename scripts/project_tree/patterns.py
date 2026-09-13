from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from .model import REPO_ROOT, walk_nodes


def codebase_roots(tree: dict) -> list[Path]:
    roots: list[Path] = []
    for item in tree.get("constraints", {}).get("codebase") or []:
        roots.append(REPO_ROOT / str(item))
    if not roots:
        roots.append(REPO_ROOT)
    return roots


def split_patterns(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def pattern_matches(pattern: str, roots: list[Path]) -> bool:
    """Return True if pattern resolves to at least one path under repo."""
    candidate = REPO_ROOT / pattern
    if candidate.exists():
        return True
    matches = glob.glob(str(candidate), recursive=True)
    if matches:
        return True
    for root in roots:
        rel = pattern
        for prefix in ("sandbox/", "projects/"):
            if rel.startswith(prefix):
                rel = rel[len(prefix) :]
        anchored = root / rel
        if anchored.exists():
            return True
        matches = glob.glob(str(anchored), recursive=True)
        if matches:
            return True
    return False


def collect_pattern_issues(tree: dict) -> list[dict[str, Any]]:
    roots = codebase_roots(tree)
    issues: list[dict[str, Any]] = []

    for node in walk_nodes(tree.get("nodes") or []):
        data = node.get("data") or {}
        pattern = data.get("pattern")
        if not pattern:
            if node.get("kind") == "work" and not node.get("children"):
                issues.append(
                    {
                        "node_id": node.get("id"),
                        "title": node.get("title"),
                        "kind": "missing_pattern",
                        "message": "work leaf has no data.pattern",
                    }
                )
            continue

        for part in split_patterns(str(pattern)):
            if not pattern_matches(part, roots):
                issues.append(
                    {
                        "node_id": node.get("id"),
                        "title": node.get("title"),
                        "kind": "broken_pattern",
                        "pattern": part,
                        "message": f"pattern does not resolve: {part}",
                    }
                )

    return issues


def format_issues(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "OK — all patterns resolve"
    lines = [f"{len(issues)} issue(s):"]
    for item in issues:
        lines.append(
            f"  [{item['kind']}] {item['node_id']} ({item['title']}): {item['message']}"
        )
    return "\n".join(lines)
