from __future__ import annotations

from pathlib import Path
from typing import Any

from project_tree import model as project_tree_model

PLAN_REL_PREFIX = "plans"


def validate_node_id(node_id: str) -> str:
    nid = str(node_id or "").strip()
    if not nid or nid in (".", "..") or "/" in nid or "\\" in nid or "\x00" in nid:
        raise ValueError(f"invalid node_id: {node_id!r}")
    return nid


def plans_dir(project: str) -> Path:
    return project_tree_model.project_dir(project) / PLAN_REL_PREFIX


def plan_rel(node_id: str) -> str:
    return f"{PLAN_REL_PREFIX}/{validate_node_id(node_id)}.plan.md"


def plan_paths(project: str, node_id: str) -> dict[str, Any]:
    nid = validate_node_id(node_id)
    rel = plan_rel(nid)
    base = plans_dir(project)
    md = base / f"{nid}.plan.md"
    return {
        "plans_dir": str(base),
        "plan_md": str(md),
        "plan_rel": rel,
        "exists": md.is_file(),
    }


def plan_stub(*, node_id: str, title: str | None = None) -> str:
    nid = validate_node_id(node_id)
    heading = title or nid
    return (
        f"# Technical Plan: {heading}\n\n"
        f"**Node:** `{nid}`\n"
        f"**Contract:** `specs/{nid}.md` (WHEN/WHY — source of truth for DONE)\n"
        "**This file:** HOW only. Not a VERIFY source.\n\n"
        "## Approach\n\n"
        "<2–3 sentences — architecture / sequencing, not requirements>\n\n"
        "## File map\n\n"
        "- Create: `<path>`\n"
        "- Modify: `<path>`\n"
        "- Test: `<path>`\n\n"
        "## Sequencing\n\n"
        "1. <step that produces something testable>\n\n"
        "## Risks\n\n"
        "- <HOW risk that does not change VERIFY>\n"
    )


def init_plan(
    project: str,
    node_id: str,
    *,
    title: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    paths = plan_paths(project, node_id)
    md = Path(paths["plan_md"])
    created = False
    if md.is_file() and not overwrite:
        return {**paths, "created": False, "written": False}
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(plan_stub(node_id=node_id, title=title), encoding="utf-8")
    created = not paths["exists"]
    return {
        **plan_paths(project, node_id),
        "created": created,
        "written": True,
    }
