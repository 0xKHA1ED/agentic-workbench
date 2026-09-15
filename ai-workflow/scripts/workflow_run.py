#!/usr/bin/env python3
"""Resumable daily-loop workflow runner (Epic E).

Runs a YAML workflow of ``step`` and ``gate`` nodes to the first gate and pauses,
persisting state so a later ``resume`` continues from exactly where it stopped.

Quality invariant (never automated away): **every gate pauses for a human.** The
runner never advances past a gate without an explicit ``approve``; ``reject`` on
a gate with ``on_reject: abort`` aborts the run. Automation orchestrates the
sequence and records hooks/overlays; humans make the gate decisions.

Features:
  - **run / resume / status** with persisted state.
  - **overlays** — insert steps (e.g. verify, lint) after a named step.
  - **phase hooks** — ``before_<step>`` / ``after_<step>`` recorded in history.
  - **feature dirs** — ``<project>/specs/<node>/feature.json`` pointer per run.
  - **path integration** — ``spike`` / ``bounded`` / ``full`` skip optional steps
    (a step's ``paths`` list) by policy while keeping every gate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = PACKAGE_ROOT / "meta" / "workflows" / "daily-loop.yaml"
VALID_PATHS = ("spike", "bounded", "full")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_workflow(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        raise ValueError(f"Workflow must be a mapping with a steps list: {path}")
    return doc


def apply_overlays(steps: list[dict], overlays: list[dict] | None) -> list[dict]:
    """Insert overlay steps after their anchor step id."""
    if not overlays:
        return list(steps)
    out = list(steps)
    for overlay in overlays:
        anchor = overlay.get("after")
        insert = overlay.get("insert") or []
        idx = next((i for i, s in enumerate(out) if s.get("id") == anchor), None)
        if idx is None:
            continue
        for offset, extra in enumerate(insert, start=1):
            out.insert(idx + offset, dict(extra))
    return out


def active_steps(steps: list[dict], path_mode: str) -> list[dict]:
    """Filter steps by path: a step with a ``paths`` list runs only on those paths.

    Steps without ``paths`` are always active. Result annotates each step with
    ``active`` so callers can report skipped-by-policy phases.
    """
    result: list[dict] = []
    for step in steps:
        entry = dict(step)
        paths = step.get("paths")
        entry["active"] = paths is None or path_mode in paths
        result.append(entry)
    return result


def _state_path(project: str, node_id: str, state_dir: Path | None) -> Path:
    if state_dir is not None:
        base = Path(state_dir)
    else:
        from project_tree import model

        base = model.project_dir(project) / "workflow"
    return base / f"{node_id}.json"


def _feature_dir(project: str, node_id: str, feature_root: Path | None) -> Path:
    if feature_root is not None:
        base = Path(feature_root)
    else:
        from project_tree import model

        base = model.project_dir(project) / "specs"
    return base / node_id


def status(project: str, node_id: str, state_dir: Path | None = None) -> dict[str, Any] | None:
    path = _state_path(project, node_id, state_dir)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict[str, Any], project: str, node_id: str, state_dir: Path | None) -> None:
    state["updated"] = _now()
    path = _state_path(project, node_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _hooks_for(workflow: dict, phase: str, step_id: str) -> list[str]:
    hooks = workflow.get("hooks") or {}
    return list(hooks.get(f"{phase}_{step_id}") or [])


def _advance(state: dict[str, Any], steps: list[dict], workflow: dict) -> dict[str, Any]:
    """Process steps from the cursor until a gate pauses the run or steps end."""
    i = state["cursor"]
    while i < len(steps):
        step = steps[i]
        step_id = step["id"]

        if not step.get("active", True):
            state["history"].append({"step": step_id, "action": "skipped_by_path"})
            state.setdefault("skipped", []).append(step_id)
            i += 1
            continue

        for hook in _hooks_for(workflow, "before", step_id):
            state["history"].append({"step": step_id, "hook": "before", "value": hook})

        if step.get("type") == "gate":
            state["cursor"] = i
            state["current_step"] = step_id
            state["status"] = "paused"
            state["history"].append({"step": step_id, "action": "gate_paused"})
            return state

        # Non-gate step auto-completes (agent/human performs the phase off-runner).
        state["history"].append({"step": step_id, "action": "done"})
        for hook in _hooks_for(workflow, "after", step_id):
            state["history"].append({"step": step_id, "hook": "after", "value": hook})
        i += 1

    state["cursor"] = len(steps)
    state["current_step"] = None
    state["status"] = "complete"
    state["history"].append({"step": None, "action": "complete"})
    return state


def run(
    project: str,
    node_id: str,
    workflow_path: Path | str = DEFAULT_WORKFLOW,
    path: str = "full",
    state_dir: Path | None = None,
    feature_root: Path | None = None,
) -> dict[str, Any]:
    """Start a run; execute to the first gate and pause. Idempotent per node id."""
    if path not in VALID_PATHS:
        raise ValueError(f"path must be one of {VALID_PATHS}, got {path!r}")

    workflow = load_workflow(workflow_path)
    steps = active_steps(apply_overlays(workflow["steps"], workflow.get("overlays")), path)

    feature_dir = _feature_dir(project, node_id, feature_root)
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_json = feature_dir / "feature.json"
    feature_json.write_text(
        json.dumps(
            {"project": project, "node": node_id, "workflow": workflow.get("name"), "created": _now()},
            indent=2,
        ),
        encoding="utf-8",
    )

    state: dict[str, Any] = {
        "project": project,
        "node_id": node_id,
        "workflow": workflow.get("name"),
        "path": path,
        "status": "running",
        "cursor": 0,
        "current_step": None,
        "history": [],
        "skipped": [],
        "feature_dir": str(feature_dir),
        "steps": [s["id"] for s in steps],
    }
    state = _advance(state, steps, workflow)
    _save_state(state, project, node_id, state_dir)
    return state


def resume(
    project: str,
    node_id: str,
    decision: str | None = None,
    workflow_path: Path | str = DEFAULT_WORKFLOW,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Resume a paused gate with an explicit decision (approve advances; reject aborts)."""
    state = status(project, node_id, state_dir)
    if state is None:
        raise ValueError(f"No workflow run for node '{node_id}' in project '{project}'")
    if state["status"] in ("complete", "aborted"):
        return state
    if state["status"] != "paused":
        raise ValueError(f"Run is '{state['status']}', not paused; nothing to resume")

    workflow = load_workflow(workflow_path)
    steps = active_steps(apply_overlays(workflow["steps"], workflow.get("overlays")), state["path"])
    gate = steps[state["cursor"]]
    on_reject = gate.get("on_reject", "abort")

    if decision is None:
        raise ValueError(f"Gate '{gate['id']}' requires a decision: approve or reject")
    if decision not in (gate.get("options") or ["approve", "reject"]):
        raise ValueError(f"Invalid decision '{decision}' for gate '{gate['id']}'")

    if decision == "reject":
        state["history"].append({"step": gate["id"], "action": "gate_rejected"})
        if on_reject == "abort":
            state["status"] = "aborted"
            state["current_step"] = gate["id"]
            state["history"].append({"step": gate["id"], "action": "aborted"})
            _save_state(state, project, node_id, state_dir)
            return state
        # Non-abort reject stays paused for another decision.
        _save_state(state, project, node_id, state_dir)
        return state

    # approve → record, run after-hook, advance past the gate.
    state["history"].append({"step": gate["id"], "action": "gate_approved"})
    for hook in _hooks_for(workflow, "after", gate["id"]):
        state["history"].append({"step": gate["id"], "hook": "after", "value": hook})
    state["cursor"] += 1
    state["status"] = "running"
    state = _advance(state, steps, workflow)
    _save_state(state, project, node_id, state_dir)
    return state


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="workflow_run", description="Daily-loop workflow runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Start a run to the first gate")
    p_run.add_argument("project")
    p_run.add_argument("node_id")
    p_run.add_argument("--path", default="full", choices=VALID_PATHS)
    p_run.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))

    p_resume = sub.add_parser("resume", help="Resume a paused gate")
    p_resume.add_argument("project")
    p_resume.add_argument("node_id")
    p_resume.add_argument("--decision", choices=["approve", "reject"], required=True)
    p_resume.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))

    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("project")
    p_status.add_argument("node_id")

    args = parser.parse_args(argv)
    if args.command == "run":
        print(json.dumps(run(args.project, args.node_id, args.workflow, path=args.path), indent=2))
    elif args.command == "resume":
        print(json.dumps(resume(args.project, args.node_id, decision=args.decision, workflow_path=args.workflow), indent=2))
    elif args.command == "status":
        st = status(args.project, args.node_id)
        print(json.dumps(st, indent=2) if st else "No run found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
