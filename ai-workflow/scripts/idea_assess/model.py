from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from project_tree import model as project_tree_model

VALID_VERDICTS = frozenset({"go", "kill", "needs-clarification"})

STAGE_FILES = {
    "intake": "intake.md",
    "research": "research.md",
    "problem": "problem.md",
    "concept": "concept.md",
    "decision": "decision.md",
}

_SLUG_KEEP = re.compile(r"[^a-z0-9-]+")
_VERDICT_RE = re.compile(
    r"^\s*(?:-\s*)?\*\*Verdict\*\*\s*:\s*(go|kill|needs-clarification)\b",
    re.I | re.M,
)


def normalize_slug(raw: str) -> str:
    """Lowercase kebab-case; strip path separators and other unsafe chars."""
    text = str(raw or "").strip().lower().replace("_", "-").replace(" ", "-")
    text = text.replace("/", "-").replace("\\", "-").replace(".", "-")
    text = _SLUG_KEEP.sub("-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def slug_from_idea(idea: str, *, max_words: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", (idea or "").lower())
    return normalize_slug("-".join(words[:max_words]))


def assessments_dir(project: str) -> Path:
    return project_tree_model.project_dir(project) / "assessments"


def assessment_dir(project: str, slug: str) -> Path:
    normalized = normalize_slug(slug)
    if not normalized:
        raise ValueError("empty slug after normalization")
    base = assessments_dir(project)
    root = base.resolve()
    target = (base / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("assessment path escapes assessments directory") from exc
    if target == root:
        raise ValueError("assessment path escapes assessments directory")
    return target


def assessment_paths(project: str, slug: str) -> dict[str, Any]:
    normalized = normalize_slug(slug)
    directory = assessment_dir(project, normalized)
    files = {name: str(directory / filename) for name, filename in STAGE_FILES.items()}
    exists = {name: Path(path).is_file() for name, path in files.items()}
    verdict = None
    decision_path = Path(files["decision"])
    if decision_path.is_file():
        verdict = parse_verdict(decision_path.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "project": project,
        "slug": normalized,
        "assessments_dir": str(assessments_dir(project)),
        "assessment_dir": str(directory),
        **{f"{name}_md": path for name, path in files.items()},
        "exists": exists,
        "verdict": verdict,
    }
    payload["handoff"] = handoff_for(verdict)
    return payload


def parse_verdict(markdown: str) -> str | None:
    match = _VERDICT_RE.search(markdown or "")
    if not match:
        return None
    value = match.group(1).lower()
    return value if value in VALID_VERDICTS else None


def handoff_for(verdict: str | None, node_id: str | None = None) -> dict[str, Any]:
    """On go: spec-clarify if a node exists, else project-tree attach. Else none."""
    if verdict != "go":
        return {"skill": None, "node_id": node_id, "reason": _handoff_reason(verdict)}
    if node_id:
        return {
            "skill": "spec-clarify",
            "node_id": node_id,
            "reason": "go with existing tree node — clarify requirements before claims",
        }
    return {
        "skill": "project-tree",
        "node_id": None,
        "reason": "go without a node — attach a weak work child, then spec-clarify",
    }


def _handoff_reason(verdict: str | None) -> str:
    if verdict == "kill":
        return "killed — assessment closed; do not attach a tree node"
    if verdict == "needs-clarification":
        return "refine the named artifact in place, then revise decision.md"
    return "no verdict yet — continue intake→decide"


def init_assessment(
    project: str,
    slug: str,
    *,
    idea: str | None = None,
    unique: bool = False,
) -> dict[str, Any]:
    normalized = normalize_slug(slug) or slug_from_idea(idea or "")
    if not normalized:
        raise ValueError("empty slug after normalization — pass --slug or --idea")
    directory = assessment_dir(project, normalized)
    if directory.exists():
        if unique:
            normalized = _unique_slug(project, normalized)
            directory = assessment_dir(project, normalized)
        elif any(directory.iterdir()) if directory.is_dir() else True:
            raise FileExistsError(
                f"assessment already exists: {directory} (pass --unique to suffix -2, -3, …)"
            )
    directory.mkdir(parents=True, exist_ok=True)
    intake = directory / STAGE_FILES["intake"]
    if intake.exists():
        raise FileExistsError(f"intake.md already exists: {intake}")
    intake.write_text(_intake_skeleton(normalized, idea), encoding="utf-8")
    return assessment_paths(project, normalized)


def _unique_slug(project: str, slug: str) -> str:
    n = 2
    while assessment_dir(project, f"{slug}-{n}").exists():
        n += 1
        if n > 99:
            raise ValueError("could not allocate a unique slug")
    return f"{slug}-{n}"


def _intake_skeleton(slug: str, idea: str | None) -> str:
    quoted = (idea or "").strip() or "[NEEDS CLARIFICATION: paste the idea]"
    return (
        f"# Intake: {slug}\n\n"
        f"- **Slug**: {slug}\n"
        f"- **Created**: {date.today().isoformat()}\n"
        f"- **Source**: pasted-text\n"
        f"- **Idea type**: [NEEDS CLARIFICATION: new-capability | improvement | fix | exploration | other]\n\n"
        f"## Original\n\n"
        f"> {quoted}\n\n"
        f"## Restatement\n\n"
        f"[NEEDS CLARIFICATION: one or two neutral sentences]\n\n"
        f"## Origin & context\n\n"
        f"[NEEDS CLARIFICATION: who raised it, when, trigger]\n\n"
        f"## First-glance unknowns\n\n"
        f"- [NEEDS CLARIFICATION: …]\n"
    )
