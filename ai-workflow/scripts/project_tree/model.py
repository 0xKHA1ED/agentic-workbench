from __future__ import annotations

import copy
from datetime import date
import difflib
from pathlib import Path
from typing import Any

import yaml

# ai-workflow/scripts/project_tree/model.py → package root
PACKAGE_ROOT = Path(__file__).resolve().parents[2]

PROJECT_ALIASES = {"ai-workflow": "meta"}


from project_tree.resolver import find_repository_root


def host_root() -> Path:
    """Repository that hosts the package."""
    return find_repository_root(PACKAGE_ROOT)


# Codebase paths in data.pattern resolve against the host repo
REPO_ROOT = host_root()


def resolve_project_name(name: str) -> str:
    return PROJECT_ALIASES.get(name, name)


def project_dir(name: str) -> Path:
    name = resolve_project_name(name)
    if name == "meta":
        return PACKAGE_ROOT / "meta"
    example = PACKAGE_ROOT / "examples" / name
    if (example / "nodes.yaml").exists():
        return example
    return host_root() / "projects" / name


def list_projects() -> list[str]:
    names: set[str] = set()
    if (PACKAGE_ROOT / "meta" / "nodes.yaml").exists():
        names.add("meta")
    examples_dir = PACKAGE_ROOT / "examples"
    if examples_dir.exists():
        for path in sorted(examples_dir.iterdir()):
            if path.is_dir() and (path / "nodes.yaml").exists():
                names.add(path.name)
    host_projects = host_root() / "projects"
    if host_projects.exists():
        for path in sorted(host_projects.iterdir()):
            if path.is_dir() and (path / "nodes.yaml").exists():
                names.add(path.name)
    return sorted(names)


def nodes_path(name: str) -> Path:
    return project_dir(name) / "nodes.yaml"


def proposed_path(name: str) -> Path:
    return project_dir(name) / "nodes.yaml.proposed"


def list_pending_proposals(name: str) -> list[tuple[str | None, Path]]:
    """Return (fragment_rel or None for root, pending path) for each staged proposal."""
    name = resolve_project_name(name)
    base = project_dir(name)
    pending: list[tuple[str | None, Path]] = []
    root = proposed_path(name)
    if root.exists():
        pending.append((None, root))
    frag_dir = base / "fragments"
    if frag_dir.is_dir():
        for path in sorted(frag_dir.glob("*.yaml.proposed")):
            rel = f"fragments/{path.name.removesuffix('.proposed')}"
            pending.append((rel, path))
    return pending


def _resolve_proposal_paths(project: str, fragment_rel: str | None = None) -> tuple[Path, Path]:
    from project_tree import fragments

    if fragment_rel:
        target_path = fragments.resolve_fragment_path(project, fragment_rel)
        pending_path = fragments.fragment_proposed_path(target_path)
    else:
        target_path = nodes_path(project)
        pending_path = proposed_path(project)
    return target_path, pending_path


def get_pending_proposal_diff(project: str, fragment_rel: str | None = None) -> str:
    """Return unified diff for pending proposal on project (or fragment), or empty string if none."""
    from project_tree import fragments

    target_path, pending_path = _resolve_proposal_paths(project, fragment_rel)
    if not pending_path.exists():
        return ""

    if fragment_rel:
        current_data = fragments.load_fragment_file(target_path)
        current_tree = fragments.fragment_as_tree(current_data, f"{project}:{fragment_rel}")
        with pending_path.open() as f:
            proposed_data = yaml.safe_load(f)
        if isinstance(proposed_data, dict) and "project" not in proposed_data:
            proposed_tree = fragments.fragment_as_tree(proposed_data, f"{project}:{fragment_rel}")
        else:
            proposed_tree = proposed_data
    else:
        current_tree = load_tree(project)
        with pending_path.open() as f:
            proposed_tree = yaml.safe_load(f)

    base = project_dir(project)
    try:
        rel = base.relative_to(host_root())
    except ValueError:
        rel = base
    label = f"{rel}/{fragment_rel}" if fragment_rel else f"{rel}/nodes.yaml"

    before_text = dump_tree(current_tree)
    after_text = dump_tree(proposed_tree)

    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )


def apply_pending_proposal(project: str, fragment_rel: str | None = None) -> dict[str, Any]:
    """Apply staged pending proposal to target file (root or fragment), unlink .proposed file, and return applied tree data."""
    from project_tree import fragments

    target_path, pending_path = _resolve_proposal_paths(project, fragment_rel)
    if not pending_path.exists():
        raise FileNotFoundError(f"No pending proposal found for {fragment_rel or 'root'} at {pending_path}")

    with pending_path.open() as f:
        proposed_data = yaml.safe_load(f)

    if fragment_rel:
        fragments.save_fragment_file(target_path, proposed_data)
    else:
        save_tree(project, proposed_data, path=target_path)

    pending_path.unlink()
    return proposed_data


def reject_pending_proposal(project: str, fragment_rel: str | None = None) -> None:
    """Unlink the .proposed file for the target proposal."""
    _, pending_path = _resolve_proposal_paths(project, fragment_rel)
    if not pending_path.exists():
        raise FileNotFoundError(f"No pending proposal found for {fragment_rel or 'root'} at {pending_path}")
    pending_path.unlink()


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


def find_parent(nodes: list[dict], node_id: str) -> dict | None:
    for node in nodes:
        for child in node.get("children") or []:
            if child.get("id") == node_id:
                return node
            found = find_parent([child], node_id)
            if found:
                return found
    return None


def find_parent_in_tree(tree: dict, node_id: str) -> dict | None:
    return find_parent(tree.get("nodes") or [], node_id)


def contains_descendant(node: dict, target_id: str) -> bool:
    for child in node.get("children") or []:
        if child.get("id") == target_id:
            return True
        if contains_descendant(child, target_id):
            return True
    return False


def walk_nodes(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("children") or [])


def ascii_tree(tree: dict, composed: bool = False) -> str:
    mode = "composed" if composed or tree.get("composed") else "raw"
    lines = [f"{tree.get('project', '?')} — updated {tree.get('updated', '?')} ({mode})"]
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
            data = dict(node["data"])
            data.pop("_composed_from", None)
            if data:
                data_hint = f" — {data}"
        frag = ""
        if (node.get("data") or {}).get("subtree") and not (node.get("children") or []):
            frag = " [fragment]"
        lines.append(f"{prefix}{title} [{kind}] {status}{stale}{frag}{data_hint}")
        for child in node.get("children") or []:
            render(child, prefix + "  ")

    for root in tree.get("nodes") or []:
        render(root)
    return "\n".join(lines)
