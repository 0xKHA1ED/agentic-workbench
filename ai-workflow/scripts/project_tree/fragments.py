from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .model import REPO_ROOT, project_dir, walk_nodes


def resolve_fragment_path(project: str, rel_path: str) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute():
        raise ValueError(f"subtree must be relative to project dir: {rel_path}")
    base = project_dir(project).resolve()
    full = (base / rel).resolve()
    if not str(full).startswith(str(base)):
        raise ValueError(f"subtree escapes project dir: {rel_path}")
    return full


def load_fragment_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Fragment not found: {path}")
    with path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Fragment must be a mapping: {path}")
    if "nodes" not in data or not isinstance(data["nodes"], list):
        raise ValueError(f"Fragment must have a nodes list: {path}")
    return data


def fragment_as_tree(fragment: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "project": label,
        "nodes": copy.deepcopy(fragment.get("nodes") or []),
        "constraints": copy.deepcopy(fragment.get("constraints") or {}),
    }


def tree_as_fragment(tree: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"nodes": copy.deepcopy(tree.get("nodes") or [])}
    constraints = tree.get("constraints") or {}
    if constraints:
        out["constraints"] = copy.deepcopy(constraints)
    return out


def save_fragment_file(path: Path, fragment: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Project tree fragment — managed by scripts/project_tree.py\n")
        yaml.dump(tree_as_fragment(fragment), f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def fragment_proposed_path(fragment_path: Path) -> Path:
    return fragment_path.with_suffix(fragment_path.suffix + ".proposed")


def list_fragment_refs(tree: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for node in walk_nodes(tree.get("nodes") or []):
        subtree = (node.get("data") or {}).get("subtree")
        if subtree:
            refs.append(str(subtree))
    return refs


def compose_nodes(nodes: list[dict], project: str, seen: set[str] | None = None) -> list[dict]:
    seen = seen or set()
    return [compose_node(node, project, seen) for node in nodes]


def compose_node(node: dict[str, Any], project: str, seen: set[str]) -> dict[str, Any]:
    out = copy.deepcopy(node)
    data = dict(out.get("data") or {})
    subtree = data.get("subtree")

    if subtree:
        frag_path = resolve_fragment_path(project, str(subtree))
        key = str(frag_path)
        if key in seen:
            raise ValueError(f"circular subtree reference: {subtree}")
        seen.add(key)
        fragment = load_fragment_file(frag_path)
        frag_constraints = fragment.get("constraints") or {}
        if frag_constraints.get("codebase"):
            data["codebase"] = frag_constraints["codebase"]
        data["_composed_from"] = str(subtree)
        out["data"] = data
        out["children"] = compose_nodes(fragment.get("nodes") or [], project, seen)
    else:
        out["children"] = compose_nodes(out.get("children") or [], project, seen)

    return out


def compose_tree(tree: dict[str, Any], project: str) -> dict[str, Any]:
    out = copy.deepcopy(tree)
    out["nodes"] = compose_nodes(out.get("nodes") or [], project, set())
    out["composed"] = True
    return out


def collect_fragment_sources(tree: dict[str, Any], project: str) -> list[tuple[str, dict[str, Any]]]:
    """Return (subtree path, fragment-as-tree) for validation and tooling."""
    sources: list[tuple[str, dict[str, Any]]] = []

    def visit(nodes: list[dict]) -> None:
        for node in nodes:
            subtree = (node.get("data") or {}).get("subtree")
            if subtree:
                path = resolve_fragment_path(project, str(subtree))
                fragment = load_fragment_file(path)
                label = f"{project}:{subtree}"
                sources.append((str(subtree), fragment_as_tree(fragment, label)))
            visit(node.get("children") or [])

    visit(tree.get("nodes") or [])
    return sources
