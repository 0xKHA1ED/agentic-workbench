from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from project_tree import model as project_tree_model
from project_tree.model import PACKAGE_ROOT, host_root

VALID_STATUS = frozenset({"in_progress", "complete", "skipped"})
VALID_TAXONOMY = frozenset({"full", "tooling"})

TOOLING_PATTERN = re.compile(
    r"(\.cursor/|scripts/|tools/|meta/docs/|AGENTS\.md|INSTALL\.md)",
    re.I,
)


def clarifications_dir(project: str) -> Path:
    return project_tree_model.project_dir(project) / "clarifications"


def clarify_paths(project: str, node_id: str) -> dict[str, str]:
    base = clarifications_dir(project)
    md = base / f"{node_id}.md"
    decisions = base / f"{node_id}.decisions.json"
    return {
        "clarifications_dir": str(base),
        "clarifications_md": str(md),
        "decisions_json": str(decisions),
    }


def constitution_path(project: str) -> Path | None:
    proj = project_tree_model.project_dir(project)
    for candidate in (
        proj / "constitution.md",
        PACKAGE_ROOT / "meta" / "constitution.md",
        host_root() / "constitution.md",
        host_root() / "memory" / "constitution.md",
    ):
        if candidate.is_file():
            return candidate
    return None


def infer_taxonomy_mode(node_data: dict[str, Any] | None) -> str:
    data = node_data or {}
    explicit = data.get("clarify_taxonomy")
    if explicit in VALID_TAXONOMY:
        return str(explicit)
    pattern = str(data.get("pattern") or "")
    if TOOLING_PATTERN.search(pattern):
        return "tooling"
    return "full"


def _default_decisions(project: str, node_id: str, taxonomy_mode: str) -> dict[str, Any]:
    return {
        "project": project,
        "node_id": node_id,
        "status": "in_progress",
        "taxonomy_mode": taxonomy_mode,
        "decisions": [],
        "deferred_categories": [],
        "outstanding_categories": [],
        "questions_asked": 0,
        "updated": date.today().isoformat(),
    }


def load_decisions(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Decisions file must be a JSON object")
    return normalize_decisions(data)


def normalize_decisions(data: dict[str, Any]) -> dict[str, Any]:
    status = data.get("status", "in_progress")
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status '{status}'")
    mode = data.get("taxonomy_mode", "full")
    if mode not in VALID_TAXONOMY:
        raise ValueError(f"Invalid taxonomy_mode '{mode}'")
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("'decisions' must be a list")
    for i, entry in enumerate(decisions):
        if not isinstance(entry, dict):
            raise ValueError(f"Decision {i} must be an object")
        if not str(entry.get("question") or "").strip():
            raise ValueError(f"Decision {i} missing question")
        if not str(entry.get("answer") or "").strip():
            raise ValueError(f"Decision {i} missing answer")
    data["status"] = status
    data["taxonomy_mode"] = mode
    data["decisions"] = decisions
    data.setdefault("deferred_categories", [])
    data.setdefault("outstanding_categories", [])
    data.setdefault("questions_asked", len(decisions))
    return data


def save_decisions(path: Path, data: dict[str, Any]) -> None:
    data = normalize_decisions(data)
    data["updated"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def ensure_decisions(project: str, node_id: str, taxonomy_mode: str) -> dict[str, Any]:
    paths = clarify_paths(project, node_id)
    path = Path(paths["decisions_json"])
    if path.exists():
        doc = load_decisions(path)
        if doc.get("taxonomy_mode") != taxonomy_mode and doc.get("status") == "in_progress":
            doc["taxonomy_mode"] = taxonomy_mode
        return doc
    doc = _default_decisions(project, node_id, taxonomy_mode)
    save_decisions(path, doc)
    return doc


def append_decision(
    project: str,
    node_id: str,
    *,
    question: str,
    answer: str,
    category: str = "general",
    taxonomy_mode: str | None = None,
) -> dict[str, Any]:
    mode = taxonomy_mode or "full"
    doc = ensure_decisions(project, node_id, mode)
    if doc["status"] != "in_progress":
        raise ValueError(f"Clarify session is '{doc['status']}' — start a new session or reset")
    if doc["questions_asked"] >= 5:
        raise ValueError("Maximum 5 clarification questions per session (Spec Kit parity)")
    entry = {
        "id": f"d{len(doc['decisions']) + 1}",
        "category": category.strip() or "general",
        "question": question.strip(),
        "answer": answer.strip(),
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    doc["decisions"].append(entry)
    doc["questions_asked"] = len(doc["decisions"])
    paths = clarify_paths(project, node_id)
    save_decisions(Path(paths["decisions_json"]), doc)
    append_markdown_session(
        Path(paths["clarifications_md"]),
        node_id=node_id,
        question=entry["question"],
        answer=entry["answer"],
    )
    return doc


def append_markdown_session(
    md_path: Path,
    *,
    node_id: str,
    question: str,
    answer: str,
    title: str | None = None,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    session_heading = f"### Session {today}"
    bullet = f"- Q: {question} → A: {answer}"

    if not md_path.exists():
        heading = title or node_id
        md_path.write_text(
            f"# Clarifications: {heading}\n\n## Clarifications\n\n{session_heading}\n\n{bullet}\n",
            encoding="utf-8",
        )
        return

    text = md_path.read_text(encoding="utf-8")
    if session_heading in text:
        text = text.rstrip() + "\n" + bullet + "\n"
    else:
        if "## Clarifications" not in text:
            text = text.rstrip() + "\n\n## Clarifications\n\n"
        text = text.rstrip() + f"\n\n{session_heading}\n\n{bullet}\n"
    md_path.write_text(text, encoding="utf-8")


def complete_clarify(
    project: str,
    node_id: str,
    *,
    deferred_categories: list[str] | None = None,
    outstanding_categories: list[str] | None = None,
    status: str = "complete",
) -> dict[str, Any]:
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status '{status}'")
    paths = clarify_paths(project, node_id)
    path = Path(paths["decisions_json"])
    if not path.exists():
        doc = _default_decisions(project, node_id, "full")
    else:
        doc = load_decisions(path)
    doc["status"] = status
    doc["deferred_categories"] = list(deferred_categories or [])
    doc["outstanding_categories"] = list(outstanding_categories or [])
    save_decisions(path, doc)
    _write_completion_block(
        Path(paths["clarifications_md"]),
        deferred=doc["deferred_categories"],
        outstanding=doc["outstanding_categories"],
        status=status,
    )
    return doc


def _write_completion_block(
    md_path: Path,
    *,
    deferred: list[str],
    outstanding: list[str],
    status: str,
) -> None:
    if not md_path.exists():
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(f"# Clarifications\n\n## Completion\n\nStatus: {status}\n", encoding="utf-8")
    text = md_path.read_text(encoding="utf-8")
    block = "## Completion\n\n"
    block += f"Status: **{status}**\n\n"
    if deferred:
        block += "Deferred categories:\n" + "".join(f"- {c}\n" for c in deferred)
    else:
        block += "Deferred categories: _(none)_\n"
    if outstanding:
        block += "\nOutstanding (low impact):\n" + "".join(f"- {c}\n" for c in outstanding)
    else:
        block += "\nOutstanding: _(none)_\n"
    if "## Completion" in text:
        head, _, _tail = text.partition("## Completion")
        text = head.rstrip() + "\n\n" + block
    else:
        text = text.rstrip() + "\n\n" + block
    md_path.write_text(text, encoding="utf-8")


def clarify_blocks_claims(project: str, node_id: str, node_data: dict[str, Any] | None) -> str | None:
    """Return error message if claims staging must not proceed yet."""
    data = node_data or {}
    paths = clarify_paths(project, node_id)
    path = Path(paths["decisions_json"])
    needs = data.get("needs_clarify") is True

    if not path.exists():
        if needs:
            return (
                "Node has needs_clarify=true but no clarify session. "
                "Run /spec-clarify or workflow_clarify_complete with status skipped."
            )
        return None

    doc = load_decisions(path)
    status = doc.get("status")
    if status == "in_progress":
        return "Clarify session in_progress — complete or skip before staging claims."
    if status == "skipped":
        return None
    if status == "complete":
        return None
    if needs:
        return "Clarify required before staging claims."
    return None
