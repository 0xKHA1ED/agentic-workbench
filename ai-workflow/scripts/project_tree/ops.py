from __future__ import annotations

import copy
from typing import Any, Callable

from .model import contains_descendant, find_node_in_tree

# Registry of operations for single and batch propose
OP_HANDLERS: dict[str, Callable[..., dict]] = {}


def _register(name: str):
    def decorator(fn: Callable[..., dict]):
        OP_HANDLERS[name] = fn
        return fn
    return decorator


def _ensure_children(node: dict) -> list:
    if "children" not in node:
        node["children"] = []
    return node["children"]


@_register("set-constraint")
def set_constraint(tree: dict, key: str, *values: Any) -> dict:
    out = copy.deepcopy(tree)
    out.setdefault("constraints", {})[key] = list(values)
    return out


@_register("add-child")
def add_child(
    tree: dict,
    parent_id: str,
    node_id: str,
    title: str,
    kind: str = "work",
    status: str = "weak",
) -> dict:
    out = copy.deepcopy(tree)
    parent = find_node_in_tree(out, parent_id)
    if not parent:
        raise ValueError(f"Parent node not found: {parent_id}")
    children = _ensure_children(parent)
    if any(c.get("id") == node_id for c in children):
        raise ValueError(f"Child already exists: {node_id}")
    children.append({"id": node_id, "title": title, "kind": kind, "status": status})
    return out


@_register("set-data")
def set_data(tree: dict, node_id: str, data: dict[str, Any]) -> dict:
    out = copy.deepcopy(tree)
    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")
    existing = node.get("data") or {}
    existing.update(data)
    node["data"] = existing
    return out


@_register("set-status")
def set_status(tree: dict, node_id: str, status: str) -> dict:
    out = copy.deepcopy(tree)
    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")
    node["status"] = status
    return out


@_register("mark-stale")
def mark_stale(tree: dict, node_id: str, notes: str | None = None) -> dict:
    out = copy.deepcopy(tree)
    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")
    node["stale"] = True
    if notes:
        node["notes"] = notes
    return out


@_register("clear-stale")
def clear_stale(tree: dict, node_id: str) -> dict:
    out = copy.deepcopy(tree)
    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")
    node["stale"] = False
    node.pop("notes", None)
    return out


@_register("rename")
def rename(tree: dict, node_id: str, title: str) -> dict:
    out = copy.deepcopy(tree)
    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")
    if not title.strip():
        raise ValueError("title must be non-empty")
    node["title"] = title.strip()
    return out


def _detach_node(nodes: list[dict], node_id: str) -> dict | None:
    for i, node in enumerate(nodes):
        if node.get("id") == node_id:
            return nodes.pop(i)
        children = node.get("children") or []
        found = _detach_node(children, node_id)
        if found is not None:
            return found
    return None


@_register("reparent")
def reparent(tree: dict, node_id: str, new_parent_id: str) -> dict:
    out = copy.deepcopy(tree)
    if node_id == new_parent_id:
        raise ValueError("cannot reparent node under itself")

    node = find_node_in_tree(out, node_id)
    if not node:
        raise ValueError(f"Node not found: {node_id}")

    new_parent = find_node_in_tree(out, new_parent_id)
    if not new_parent:
        raise ValueError(f"Parent node not found: {new_parent_id}")

    if contains_descendant(node, new_parent_id):
        raise ValueError("cannot reparent under a descendant")

    detached = _detach_node(out.get("nodes") or [], node_id)
    if detached is None:
        raise ValueError(f"Node not found: {node_id}")

    children = _ensure_children(new_parent)
    if any(c.get("id") == node_id for c in children):
        raise ValueError(f"Child already exists under {new_parent_id}: {node_id}")
    children.append(detached)
    return out


@_register("include-meal")
def include_meal(tree: dict, meal: str) -> dict:
    out = copy.deepcopy(tree)
    meals_constraint = list(out.setdefault("constraints", {}).get("meals") or [])
    if meal not in meals_constraint:
        meals_constraint.append(meal)
    out["constraints"]["meals"] = meals_constraint

    meals_node = find_node_in_tree(out, "meals")
    if not meals_node:
        raise ValueError("Node 'meals' not found — add meals group first")

    data = meals_node.get("data") or {}
    included = list(data.get("included") or [])
    excluded = list(data.get("excluded") or [])
    if meal in excluded:
        excluded.remove(meal)
    if meal not in included:
        included.append(meal)
    meals_node["data"] = {**data, "included": included, "excluded": excluded}

    children = _ensure_children(meals_node)
    existing = next((c for c in children if c.get("id") == meal), None)
    if existing:
        existing["stale"] = False
        if str(existing.get("notes", "")).startswith("superseded") or "excluded" in str(existing.get("notes", "")):
            existing.pop("notes", None)
    else:
        children.append({"id": meal, "title": meal.capitalize(), "kind": "work", "status": "weak"})
    return out


@_register("exclude-meal")
def exclude_meal(tree: dict, meal: str) -> dict:
    out = copy.deepcopy(tree)
    meals_constraint = list(out.setdefault("constraints", {}).get("meals") or [])
    if meal in meals_constraint:
        meals_constraint.remove(meal)
    out["constraints"]["meals"] = meals_constraint

    meals_node = find_node_in_tree(out, "meals")
    if not meals_node:
        raise ValueError("Node 'meals' not found")

    data = meals_node.get("data") or {}
    included = list(data.get("included") or [])
    excluded = list(data.get("excluded") or [])
    if meal in included:
        included.remove(meal)
    if meal not in excluded:
        excluded.append(meal)
    meals_node["data"] = {**data, "included": included, "excluded": excluded}

    for child in _ensure_children(meals_node):
        if child.get("id") == meal:
            child["stale"] = True
            child["notes"] = "excluded — meal not in plan"
    return out


@_register("add-group")
def add_group(tree: dict, parent_id: str, node_id: str, title: str) -> dict:
    return add_child(tree, parent_id, node_id, title, kind="group", status="weak")


@_register("attach-subtree")
def attach_subtree(
    tree: dict,
    parent_id: str,
    node_id: str,
    title: str,
    fragment_path: str,
    kind: str = "group",
) -> dict:
    """Add a stub node that composes children from a fragment YAML file."""
    out = add_child(tree, parent_id, node_id, title, kind=kind, status="weak")
    return set_data(out, node_id, {"subtree": fragment_path})


@_register("add-allergies")
def add_allergies(
    tree: dict,
    parent_id: str,
    *allergies: str,
    as_children: bool = False,
) -> dict:
    out = copy.deepcopy(tree)
    parent = find_node_in_tree(out, parent_id)
    if not parent:
        raise ValueError(f"Parent node not found: {parent_id}")

    if as_children and len(allergies) <= 6:
        children = _ensure_children(parent)
        for allergy in allergies:
            slug = allergy.lower().replace(" ", "-")
            if any(c.get("id") == slug for c in children):
                continue
            children.append({"id": slug, "title": allergy, "kind": "data", "status": "discussing"})
    else:
        data = parent.get("data") or {}
        existing = list(data.get("allergies") or [])
        for a in allergies:
            if a not in existing:
                existing.append(a)
        parent["data"] = {**data, "allergies": existing}
    return out


def apply_op(tree: dict, op: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> dict:
    if op not in OP_HANDLERS:
        raise ValueError(f"Unknown operation: {op}")
    args = args or []
    kwargs = kwargs or {}
    return OP_HANDLERS[op](tree, *args, **kwargs)


@_register("set-all-weak")
def set_all_weak(tree: dict, *preserve: Any) -> dict:
    """Set every node to weak except statuses listed in preserve (default: strong)."""
    preserve_set = set(preserve) if preserve else {"strong"}
    out = copy.deepcopy(tree)
    from .model import walk_nodes

    for node in walk_nodes(out.get("nodes") or []):
        if node.get("status") not in preserve_set:
            node["status"] = "weak"
    return out


def apply_batch(tree: dict, operations: list[dict[str, Any]]) -> dict:
    out = tree
    for i, step in enumerate(operations):
        op = step.get("op")
        if not op:
            raise ValueError(f"Batch step {i}: missing 'op'")
        out = apply_op(out, op, step.get("args") or [], step.get("kwargs") or {})
    return out
