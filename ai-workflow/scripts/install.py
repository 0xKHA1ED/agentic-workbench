#!/usr/bin/env python3
"""One-command install kit (``awf init``) — inspectable and idempotent.

Adds ai-workflow to any host repo by:
  1. writing ``.cursor/mcp.json`` from a versioned in-repo template,
  2. syncing ``.cursor/skills/`` from this package with a checksum manifest, and
  3. scaffolding ``projects/<name>/nodes.yaml``.

It is deliberately **inspectable**: it prints a diff of every planned write and
asks before touching ``.cursor/`` (no blind ``curl | bash``, no remote pipe).
Re-running is a no-op when nothing changed (idempotent).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # ai-workflow/
SKILLS_SRC = PACKAGE_ROOT / ".cursor" / "skills"
MANIFEST_NAME = ".skills-manifest.json"

MCP_TEMPLATE: dict[str, Any] = {
    "mcpServers": {
        "ai-workflow": {
            "command": "python3",
            "args": ["scripts/workflow_mcp.py"],
            "env": {"PYTHONUNBUFFERED": "1"},
        }
    }
}

SCAFFOLD_NODES = {
    "project": None,  # filled per project name
    "constraints": {"codebase": ["."]},
    "nodes": [
        {
            "id": "root",
            "title": None,  # filled per project name
            "kind": "group",
            "status": "weak",
        }
    ],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_mcp_json() -> str:
    return json.dumps(MCP_TEMPLATE, indent=2) + "\n"


def render_scaffold(project_name: str) -> str:
    import yaml

    doc = json.loads(json.dumps(SCAFFOLD_NODES))  # deep copy
    doc["project"] = project_name
    doc["nodes"][0]["title"] = project_name
    return "# Project tree — managed by scripts/project_tree.py\n" + yaml.dump(
        doc, default_flow_style=False, sort_keys=False, allow_unicode=True
    )


def _iter_skill_files(src: Path):
    if not src.is_dir():
        return
    for path in sorted(src.rglob("*")):
        if path.is_file():
            yield path


def compute_skill_manifest(src: Path = SKILLS_SRC) -> dict[str, str]:
    """Map skill-relative path → sha256 of file content."""
    manifest: dict[str, str] = {}
    for path in _iter_skill_files(src):
        rel = path.relative_to(src).as_posix()
        manifest[rel] = _sha256(path.read_bytes())
    return manifest


def plan_install(
    target: Path,
    project_name: str = "example",
    source: Path = SKILLS_SRC,
) -> dict[str, Any]:
    """Compute planned writes without touching disk. Returns a plan dict."""
    target = Path(target)
    actions: list[dict[str, str]] = []

    # 1. mcp.json
    mcp_path = target / ".cursor" / "mcp.json"
    mcp_new = render_mcp_json()
    if not mcp_path.exists():
        actions.append({"kind": "create", "path": ".cursor/mcp.json"})
    elif mcp_path.read_text(encoding="utf-8") != mcp_new:
        actions.append({"kind": "update", "path": ".cursor/mcp.json"})
    else:
        actions.append({"kind": "unchanged", "path": ".cursor/mcp.json"})

    # 2. skills sync (manifest-diffed)
    src_manifest = compute_skill_manifest(source)
    dst_skills = target / ".cursor" / "skills"
    for rel, digest in src_manifest.items():
        dst = dst_skills / rel
        if not dst.exists():
            actions.append({"kind": "create", "path": f".cursor/skills/{rel}"})
        elif _sha256(dst.read_bytes()) != digest:
            actions.append({"kind": "update", "path": f".cursor/skills/{rel}"})
        else:
            actions.append({"kind": "unchanged", "path": f".cursor/skills/{rel}"})

    # 3. project scaffold
    scaffold_path = target / "projects" / project_name / "nodes.yaml"
    if not scaffold_path.exists():
        actions.append({"kind": "create", "path": f"projects/{project_name}/nodes.yaml"})
    else:
        actions.append({"kind": "unchanged", "path": f"projects/{project_name}/nodes.yaml"})

    changed = any(a["kind"] in ("create", "update") for a in actions)
    return {
        "target": str(target),
        "project": project_name,
        "actions": actions,
        "changed": changed,
        "skill_count": len(src_manifest),
    }


def format_plan(plan: dict[str, Any]) -> str:
    lines = [f"awf init → {plan['target']} (project: {plan['project']})", ""]
    marks = {"create": "+ create", "update": "~ update", "unchanged": "  ok    "}
    for action in plan["actions"]:
        lines.append(f"  {marks.get(action['kind'], action['kind'])}  {action['path']}")
    lines.append("")
    lines.append("No changes — already up to date." if not plan["changed"] else "Writes above will touch .cursor/ — confirm to proceed.")
    return "\n".join(lines)


def install(
    target: Path,
    project_name: str = "example",
    source: Path = SKILLS_SRC,
    assume_yes: bool = False,
    confirm: Callable[[str], bool] | None = None,
    out=None,
) -> dict[str, Any]:
    """Execute the install. Prints the plan, confirms, then writes. Idempotent."""
    import shutil

    out = out or sys.stdout
    target = Path(target)
    plan = plan_install(target, project_name=project_name, source=source)
    print(format_plan(plan), file=out)

    if not plan["changed"]:
        plan["written"] = []
        return plan

    if not assume_yes:
        approved = False
        if confirm is not None:
            approved = confirm("Apply these writes to .cursor/ and projects/? [y/n]: ")
        elif sys.stdin.isatty():
            approved = input("\nApply these writes to .cursor/ and projects/? [y/n]: ").strip().lower() in ("y", "yes")
        if not approved:
            print("Aborted — nothing written.", file=out)
            plan["written"] = []
            plan["aborted"] = True
            return plan

    written: list[str] = []

    # 1. mcp.json
    mcp_path = target / ".cursor" / "mcp.json"
    mcp_new = render_mcp_json()
    if not mcp_path.exists() or mcp_path.read_text(encoding="utf-8") != mcp_new:
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_path.write_text(mcp_new, encoding="utf-8")
        written.append(".cursor/mcp.json")

    # 2. skills sync
    src_manifest = compute_skill_manifest(source)
    dst_skills = target / ".cursor" / "skills"
    for rel, digest in src_manifest.items():
        src_file = source / rel
        dst = dst_skills / rel
        if not dst.exists() or _sha256(dst.read_bytes()) != digest:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
            written.append(f".cursor/skills/{rel}")
    (dst_skills / MANIFEST_NAME).write_text(
        json.dumps(src_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 3. scaffold
    scaffold_path = target / "projects" / project_name / "nodes.yaml"
    if not scaffold_path.exists():
        scaffold_path.parent.mkdir(parents=True, exist_ok=True)
        scaffold_path.write_text(render_scaffold(project_name), encoding="utf-8")
        written.append(f"projects/{project_name}/nodes.yaml")

    plan["written"] = written
    print(f"\nWrote {len(written)} file(s).", file=out)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="awf", description="ai-workflow installer")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="Install ai-workflow into a host repo")
    p_init.add_argument("target", nargs="?", default=".", help="Target repo dir (default: cwd)")
    p_init.add_argument("--project", default="example", help="Scaffold projects/<name>/ (default: example)")
    p_init.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_init.add_argument("--plan", action="store_true", help="Print the plan and exit (no writes)")
    args = parser.parse_args(argv)

    if args.command == "init":
        target = Path(args.target).resolve()
        if args.plan:
            print(format_plan(plan_install(target, project_name=args.project)))
            return 0
        install(target, project_name=args.project, assume_yes=args.yes)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
