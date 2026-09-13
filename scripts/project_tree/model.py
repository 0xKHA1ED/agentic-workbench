from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = REPO_ROOT / "projects"


def project_dir(name: str) -> Path:
    return PROJECTS_DIR / name


def nodes_path(name: str) -> Path:
    return project_dir(name) / "nodes.yaml"


def proposed_path(name: str) -> Path:
    return project_dir(name) / "nodes.yaml.proposed"


def load_tree(name: str) -> dict[str, Any]:
    path = nodes_path(name)
    if not path.exists():
        raise FileNotFoundError(f"No tree at {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def dump_tree(tree: dict[str, Any]) -> str:
    return yaml.dump(tree, default_flow_style=False, sort_keys=False, allow_unicode=True)


def save_tree(name: str, tree: dict[str, Any], path: Path | None = None) -> None:
    target = path or nodes_path(name)
    tree["updated"] = date.today().isoformat()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as f:
        f.write("# Project tree — managed by scripts/project_tree.py\n")
        yaml.dump(tree, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def find_node(nodes: list[dict], node_id: str) -> dict | None:
    for node in nodes:
        if node.get("id") == node_id:
            return node
        children = node.get("children") or []
        found = find_node(children, node_id)
        if found:
            return found
    return None


def find_node_in_tree(tree: dict, node_id: str) -> dict | None:
    return find_node(tree.get("nodes") or [], node_id)


def walk_nodes(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("children") or [])


def ascii_tree(tree: dict) -> str:
    lines = [f"{tree.get('project', '?')} — updated {tree.get('updated', '?')}"]
    constraints = tree.get("constraints") or {}
    if constraints:
        lines.append(f"constraints: {constraints}")

    def render(node: dict, prefix: str = "") -> None:
        stale = " [stale]" if node.get("stale") else ""
        kind = node.get("kind", "?")
        status = node.get("status", "?")
        title = node.get("title", node.get("id", "?"))
        data_hint = ""
        if node.get("data"):
            data_hint = f" — {node['data']}"
        lines.append(f"{prefix}{title} [{kind}] {status}{stale}{data_hint}")
        for child in node.get("children") or []:
            render(child, prefix + "  ")

    for root in tree.get("nodes") or []:
        render(root)
    return "\n".join(lines)
