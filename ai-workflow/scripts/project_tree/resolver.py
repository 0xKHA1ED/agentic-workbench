from __future__ import annotations

from pathlib import Path


def find_repository_root(start_path: Path | None = None) -> Path:
    """
    Deterministically find the true host repository root.
    Walks up from start_path looking for:
      1. .workflow/config.yaml (v2 project marker)
      2. .git directory
    Never guesses parent directories.
    """
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr, *curr.parents]:
        if (parent / ".workflow" / "config.yaml").exists():
            return parent
        if (parent / ".git").exists():
            return parent
    return curr
