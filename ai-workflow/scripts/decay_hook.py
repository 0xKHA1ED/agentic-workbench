#!/usr/bin/env python3
"""Post-commit hook entrypoint: scan verified_strong nodes for pattern drift."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_tree import decay, model

HOOK_MARKER_START = (
    "# === ai-workflow decay-scan hook (installed by project_tree install-decay-hook) ==="
)
HOOK_MARKER_END = "# === end ai-workflow decay-scan hook ==="


def get_changed_files_from_latest_commit(repo_root: Path | None = None) -> list[Path]:
    """Return paths changed in the latest commit via git diff-tree."""
    root = repo_root or model.REPO_ROOT
    try:
        proc = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    changed: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if rel:
            changed.append((root / rel).resolve())
    return changed


def run_hook_scan(
    *,
    changed_files: list[Path] | None = None,
    dry_run: bool = False,
    repo_root: Path | None = None,
) -> dict:
    """Run decay scan across all discovered projects."""
    if changed_files is None:
        changed_files = get_changed_files_from_latest_commit(repo_root)

    if not changed_files:
        return {
            "projects": {},
            "scanned": 0,
            "decayed": 0,
            "refreshed": 0,
            "nodes": [],
            "skipped": True,
        }

    projects = model.list_projects()
    project_results: dict[str, dict] = {}
    totals = {"scanned": 0, "decayed": 0, "refreshed": 0, "nodes": []}

    for project in projects:
        try:
            result = decay.scan_decay(project, dry_run=dry_run, changed_files=changed_files)
        except FileNotFoundError:
            continue
        project_results[project] = result
        totals["scanned"] += result.get("scanned", 0)
        totals["decayed"] += result.get("decayed", 0)
        totals["refreshed"] += result.get("refreshed", 0)
        totals["nodes"].extend(result.get("nodes", []))

    return {
        "projects": project_results,
        "scanned": totals["scanned"],
        "decayed": totals["decayed"],
        "refreshed": totals["refreshed"],
        "nodes": totals["nodes"],
    }


def main() -> int:
    changed_files = get_changed_files_from_latest_commit()
    if not changed_files:
        return 0
    run_hook_scan(changed_files=changed_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
