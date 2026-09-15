"""Unified read-only node status aggregator (Epic A).

`node_status` collapses the scattered per-node signals — tree status, pain,
pattern, contract/verify/dogfood links, claims triage, clarify/analyze/checklist
gate state — into one payload so a session (MCP tool, REST `/api/node`, Cockpit
HUD) can answer "where is this node in the loop?" with a single call.

This module is **read-only**: it never mutates the tree, claims, or any gate
artifact. Gate readers are imported lazily so the aggregator degrades gracefully
when the higher-level spec_* packages are unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import model
from .fragments import compose_tree
from .model import find_node_in_tree, find_parent_in_tree, walk_nodes

_SPEC_APPROVED_STATUSES = {"spec_approved", "done", "verified_strong", "strong"}


def _claims_summary(project: str, node_id: str) -> dict[str, Any]:
    path = model.project_dir(project) / "claims" / f"{node_id}.json"
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "total": 0,
        "approved": 0,
        "pending": 0,
        "rejected": 0,
        "skipped": 0,
        "goal_approved": None,
    }
    if not path.is_file():
        return summary
    try:
        with path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError):
        summary["invalid"] = True
        return summary
    claims = doc.get("claims") if isinstance(doc, dict) else None
    if isinstance(claims, list):
        summary["total"] = len(claims)
        for claim in claims:
            decision = (claim or {}).get("decision", "pending")
            if decision in summary and isinstance(summary[decision], int):
                summary[decision] += 1
    summary["goal_approved"] = doc.get("goal_approved") if isinstance(doc, dict) else None
    return summary


def _gate_states(project: str, node_id: str, data: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    gates: dict[str, Any] = {
        "needs_clarify": data.get("needs_clarify"),
        "clarify_status": None,
        "clarify_questions": 0,
        "analyze_status": "missing",
        "analyze_critical": 0,
        "checklist_total": 0,
        "checklist_checked": 0,
        "checklist_unchecked": 0,
        "contract_present": bool(data.get("contract")),
        "verify_present": bool(data.get("verify") or data.get("verification") or data.get("check_command")),
    }

    # Clarify session state (lazy import — read-only).
    try:
        from spec_clarify.model import clarify_paths, load_decisions

        decisions_path = Path(clarify_paths(project, node_id)["decisions_json"])
        if decisions_path.exists():
            try:
                doc = load_decisions(decisions_path)
                gates["clarify_status"] = doc.get("status")
                gates["clarify_questions"] = doc.get("questions_asked", 0)
            except ValueError:
                gates["clarify_status"] = "invalid"
    except Exception:
        pass

    # Analyze run state (lazy import — read-only).
    try:
        from spec_analyze.model import analyze_paths, load_status

        a_paths = analyze_paths(project, node_id)
        status_path = Path(a_paths.get("status_json") or "")
        if status_path.is_file():
            try:
                status_doc = load_status(status_path)
                gates["analyze_status"] = status_doc.get("status") or "missing"
                gates["analyze_critical"] = status_doc.get("critical_count", 0)
            except (ValueError, json.JSONDecodeError):
                gates["analyze_status"] = "invalid"
    except Exception:
        pass

    # Requirements-checklist counts (lazy import — read-only).
    try:
        from spec_checklist.model import scan_checklist_status

        checklist = scan_checklist_status(project, node_id)
        total = checklist.get("total", checklist.get("total_items", 0)) or 0
        checked = checklist.get("checked", checklist.get("checked_items", 0)) or 0
        gates["checklist_total"] = total
        gates["checklist_checked"] = checked
        gates["checklist_unchecked"] = max(total - checked, 0)
    except Exception:
        pass

    gates["spec_approved"] = _is_spec_approved(data, claims)
    return gates


def _is_spec_approved(data: dict[str, Any], claims: dict[str, Any]) -> bool:
    if data.get("spec_approved"):
        return True
    if claims.get("exists") and claims.get("total", 0) > 0:
        if claims.get("pending", 0) == 0 and claims.get("goal_approved") is True:
            return True
    return False


def _children_summary(node: dict[str, Any]) -> dict[str, Any] | None:
    children = node.get("children") or []
    if not children:
        return None
    leaves = [n for n in walk_nodes(children) if not (n.get("children"))]
    strong = sum(1 for n in leaves if n.get("status") == "strong")
    weak = sum(1 for n in leaves if n.get("status") == "weak")
    total = len(leaves)
    return {
        "total_leaves": total,
        "strong": strong,
        "weak": weak,
        "other": total - strong - weak,
        "all_strong": total > 0 and strong == total,
    }


def node_status(project: str, node_id: str) -> dict[str, Any]:
    """Aggregate read-only status for a single node. Raises ValueError if missing."""
    composed = compose_tree(model.load_tree(project), project)
    node = find_node_in_tree(composed, node_id)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found in project '{project}'")

    parent = find_parent_in_tree(composed, node_id)
    data = dict(node.get("data") or {})
    claims = _claims_summary(project, node_id)

    verify_cmd = data.get("verify") or data.get("check_command")
    if verify_cmd is None:
        verification = data.get("verification")
        if isinstance(verification, str):
            verify_cmd = verification
        elif isinstance(verification, dict):
            verify_cmd = verification.get("command") or verification.get("cmd")

    return {
        "project": project,
        "node_id": node_id,
        "id": node.get("id"),
        "title": node.get("title"),
        "kind": node.get("kind"),
        "status": node.get("status"),
        "stale": bool(node.get("stale")),
        "pain": data.get("pain"),
        "pattern": data.get("pattern"),
        "contract": data.get("contract"),
        "verify_cmd": verify_cmd,
        "dogfood": data.get("dogfood"),
        "claims": claims,
        "gate_states": _gate_states(project, node_id, data, claims),
        "children_summary": _children_summary(node),
        "parent_id": parent.get("id") if parent else None,
        "read_only": True,
    }
