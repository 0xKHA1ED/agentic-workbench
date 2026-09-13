"""Pattern fingerprint drift scanner for verified_strong nodes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from . import fragments, model, patterns
from .verify_runner import run_verification, verification_spec_from_node_data

REPO_ROOT = model.REPO_ROOT


def _git_head_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(model.REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _verification_dict(data: dict[str, Any]) -> dict[str, Any]:
    verif = data.get("verification")
    if isinstance(verif, dict):
        return verif
    return {}


def _stored_fingerprint(data: dict[str, Any]) -> str | None:
    verif = _verification_dict(data)
    fingerprint = verif.get("fingerprint")
    if fingerprint is None:
        return None
    return str(fingerprint)


def _has_verification_spec(data: dict[str, Any]) -> bool:
    verif = data.get("verification")
    if isinstance(verif, dict):
        return bool(
            verif.get("check_type")
            or verif.get("type")
            or verif.get("command")
            or verif.get("cmd")
            or verif.get("target")
            or verif.get("file")
        )
    if isinstance(verif, str) and verif.strip():
        return True
    command = data.get("check_command") or data.get("test_command")
    return bool(command and str(command).strip())


def _pattern_intersects_changed_files(node: dict, tree: dict, changed_files: list[Path]) -> bool:
    changed = {path.resolve() for path in changed_files}
    for match in patterns.resolve_pattern_files(node, tree):
        if match.resolve() in changed:
            return True
    return False


def _raw_node_ids(raw_tree: dict[str, Any]) -> set[str]:
    return {node.get("id") for node in model.walk_nodes(raw_tree.get("nodes") or []) if node.get("id")}


def scan_decay(
    project: str,
    *,
    dry_run: bool = False,
    changed_files: list[Path] | None = None,
) -> dict[str, Any]:
    """Scan root nodes.yaml for verified_strong drift and decay or refresh nodes."""
    if changed_files is not None and len(changed_files) == 0:
        return {"scanned": 0, "decayed": 0, "refreshed": 0, "nodes": []}

    raw_tree = model.load_tree(project)
    composed_tree = fragments.compose_tree(raw_tree, project)
    raw_ids = _raw_node_ids(raw_tree)
    raw_nodes = {
        node.get("id"): node
        for node in model.walk_nodes(raw_tree.get("nodes") or [])
        if node.get("id")
    }

    scanned = 0
    decayed = 0
    refreshed = 0
    node_results: list[dict[str, Any]] = []
    dirty = False

    for node in model.walk_nodes(composed_tree.get("nodes") or []):
        node_id = node.get("id")
        if not node_id or node_id not in raw_ids:
            continue

        status = node.get("status")
        data = node.get("data") or {}
        pattern = data.get("pattern")
        if status != "verified_strong" or not pattern:
            continue

        if changed_files is not None and not _pattern_intersects_changed_files(
            node, composed_tree, changed_files
        ):
            continue

        scanned += 1
        current_fingerprint = patterns.compute_pattern_fingerprint(node, composed_tree)
        stored_fingerprint = _stored_fingerprint(data)

        if stored_fingerprint == current_fingerprint:
            continue

        raw_node = raw_nodes[node_id]
        raw_data = raw_node.setdefault("data", {})
        entry: dict[str, Any] = {
            "id": node_id,
            "previous_fingerprint": stored_fingerprint,
            "current_fingerprint": current_fingerprint,
        }

        if _has_verification_spec(raw_data):
            try:
                spec = verification_spec_from_node_data(raw_data)
                result = run_verification(spec, model.REPO_ROOT)
            except ValueError as exc:
                result = {
                    "status": "failed",
                    "exit_code": -1,
                    "stderr": str(exc),
                }

            if result.get("status") == "passed":
                verif = raw_data.setdefault("verification", {})
                if not isinstance(verif, dict):
                    verif = {}
                    raw_data["verification"] = verif
                verif["fingerprint"] = current_fingerprint
                verif["last_run_sha"] = _git_head_sha()
                verif["last_exit_code"] = 0
                refreshed += 1
                entry["action"] = "refreshed"
                dirty = True
            else:
                raw_node["status"] = "decayed_unverified"
                raw_data["decayed"] = True
                exit_code = result.get("exit_code")
                raw_data["decay_reason"] = (
                    f"pattern fingerprint changed; verification failed (exit {exit_code})"
                )
                decayed += 1
                entry["action"] = "decayed"
                dirty = True
        else:
            raw_node["status"] = "decayed_unverified"
            raw_data["decayed"] = True
            raw_data["decay_reason"] = "pattern fingerprint changed; no verification configured"
            decayed += 1
            entry["action"] = "decayed"
            dirty = True

        node_results.append(entry)

    if dirty and not dry_run:
        model.save_tree(project, raw_tree)

    return {
        "scanned": scanned,
        "decayed": decayed,
        "refreshed": refreshed,
        "nodes": node_results,
    }
