from __future__ import annotations

import glob
import hashlib
from pathlib import Path
from typing import Any

from .fragments import fragment_as_tree, list_fragment_refs, load_fragment_file, resolve_fragment_path
from .model import PACKAGE_ROOT, REPO_ROOT, walk_nodes


def _codebase_path(item: str) -> Path:
    if item in (".", "ai-workflow"):
        return PACKAGE_ROOT
    return REPO_ROOT / item


def codebase_roots(tree: dict, node_data: dict | None = None) -> list[Path]:
    roots: list[Path] = []
    data = node_data or {}
    for item in data.get("codebase") or []:
        roots.append(_codebase_path(str(item)))
    for item in tree.get("constraints", {}).get("codebase") or []:
        roots.append(_codebase_path(str(item)))
    if not roots:
        roots.append(REPO_ROOT)
    return roots


def split_patterns(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def _collect_pattern_paths(pattern: str, roots: list[Path]) -> list[Path]:
    """Resolve a single pattern to concrete file paths."""
    found: set[Path] = set()

    def add_candidate(base: Path) -> None:
        if base.is_file():
            found.add(base.resolve())
            return
        matches = glob.glob(str(base), recursive=True)
        for match in matches:
            path = Path(match).resolve()
            if path.is_file():
                found.add(path)

    candidate = (REPO_ROOT / pattern).resolve()
    add_candidate(candidate)

    for root in roots:
        rel = pattern
        for prefix in ("sandbox/", "projects/"):
            if rel.startswith(prefix):
                rel = rel[len(prefix) :]
        anchored = (root / rel).resolve()
        add_candidate(anchored)

    return sorted(found)


def resolve_pattern_files(node: dict, tree: dict) -> list[Path]:
    """Return all files matching a node's data.pattern within the tree context."""
    data = node.get("data") or {}
    pattern = data.get("pattern")
    if not pattern:
        return []

    roots = codebase_roots(tree, data)
    files: set[Path] = set()
    for part in split_patterns(str(pattern)):
        files.update(_collect_pattern_paths(part, roots))
    return sorted(files)


def _relative_repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _file_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_pattern_fingerprint(node: dict, tree: dict) -> str:
    """SHA-256 hex digest of sorted rel_path:content_hash entries for pattern files."""
    entries = []
    for path in resolve_pattern_files(node, tree):
        try:
            content_hash = _file_content_hash(path)
        except OSError:
            # File removed between resolution and hashing; skip it rather than
            # aborting the whole decay scan.
            continue
        rel_path = _relative_repo_path(path)
        entries.append(f"{rel_path}:{content_hash}")
    entries.sort()
    payload = "\n".join(entries)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def collect_pattern_issues(
    tree: dict,
    *,
    source: str = "root",
    skip_subtree_stubs: bool = False,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for node in walk_nodes(tree.get("nodes") or []):
        data = node.get("data") or {}
        if skip_subtree_stubs and data.get("subtree"):
            continue

        roots = codebase_roots(tree, data)
        pattern = data.get("pattern")
        if not pattern:
            if node.get("kind") == "work" and not node.get("children") and not data.get("subtree"):
                issues.append(
                    {
                        "source": source,
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
                        "source": source,
                        "node_id": node.get("id"),
                        "title": node.get("title"),
                        "kind": "broken_pattern",
                        "pattern": part,
                        "message": f"pattern does not resolve: {part}",
                    }
                )

    return issues


def collect_all_pattern_issues(project: str, tree: dict, recursive: bool = False) -> list[dict[str, Any]]:
    issues = collect_pattern_issues(tree, source="nodes.yaml", skip_subtree_stubs=recursive)
    if not recursive:
        return issues

    for ref in list_fragment_refs(tree):
        try:
            path = resolve_fragment_path(project, ref)
            if not path.exists():
                issues.append(
                    {
                        "source": ref,
                        "node_id": "?",
                        "title": "?",
                        "kind": "missing_fragment",
                        "message": f"subtree file not found: {ref}",
                    }
                )
                continue
            fragment = load_fragment_file(path)
            fragment_tree = fragment_as_tree(fragment, f"{project}:{ref}")
            issues.extend(
                collect_pattern_issues(fragment_tree, source=ref, skip_subtree_stubs=False)
            )
        except (ValueError, FileNotFoundError) as exc:
            issues.append(
                {
                    "source": ref,
                    "node_id": "?",
                    "title": "?",
                    "kind": "fragment_error",
                    "message": str(exc),
                }
            )
    return issues


def format_issues(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "OK — all patterns resolve"
    lines = [f"{len(issues)} issue(s):"]
    for item in issues:
        src = item.get("source", "?")
        lines.append(
            f"  [{item['kind']}] {src} :: {item['node_id']} ({item['title']}): {item['message']}"
        )
    return "\n".join(lines)
