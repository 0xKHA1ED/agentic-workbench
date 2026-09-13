from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = REPO_ROOT / "projects"

VALID_KINDS = frozenset({"verify", "must", "must_not"})
VALID_DECISIONS = frozenset({"pending", "approved", "rejected", "skipped"})

VAGUE_PATTERNS = [
    re.compile(r"\bhandle\b.+\bgracefully\b", re.I),
    re.compile(r"\bproperly\b", re.I),
    re.compile(r"\brobust(ly)?\b", re.I),
    re.compile(r"\bscalable\b", re.I),
    re.compile(r"\bbest practices\b", re.I),
    re.compile(r"\bshould be (fast|performant)\b", re.I),
    re.compile(r"\bimprove\b.+\bquality\b", re.I),
]


def claims_dir(project: str) -> Path:
    return PROJECTS_DIR / project / "claims"


def specs_dir(project: str) -> Path:
    return PROJECTS_DIR / project / "specs"


def load_document(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Claims file must be a JSON object")
    return data


def save_document(path: Path, data: dict[str, Any]) -> None:
    data["updated"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def normalize_document(data: dict[str, Any]) -> dict[str, Any]:
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("'claims' must be a non-empty list")

    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"Claim {i} must be an object")
        if "text" not in claim or not str(claim["text"]).strip():
            raise ValueError(f"Claim {i} missing non-empty 'text'")
        kind = claim.get("kind", "verify")
        if kind not in VALID_KINDS:
            raise ValueError(f"Claim {i} has invalid kind '{kind}'")
        claim["kind"] = kind
        if "id" not in claim or not claim["id"]:
            claim["id"] = f"c{i + 1}"
        decision = claim.get("decision", "pending")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"Claim {claim['id']} has invalid decision '{decision}'")
        claim["decision"] = decision

    data.setdefault("goal_approved", None)
    return data


def is_vague(text: str) -> bool:
    return any(p.search(text) for p in VAGUE_PATTERNS)


def pending_claims(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in data["claims"] if c.get("decision") == "pending"]


def approved_claims(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in data["claims"] if c.get("decision") == "approved"]


def decision_counts(data: dict[str, Any]) -> dict[str, int]:
    counts = {d: 0 for d in VALID_DECISIONS}
    for claim in data["claims"]:
        counts[claim.get("decision", "pending")] += 1
    return counts


def spec_output_path(data: dict[str, Any], claims_path: Path) -> Path:
    project = data.get("project")
    node = data.get("node")
    if project and node:
        return specs_dir(str(project)) / f"{node}.md"
    return claims_path.with_suffix(".md")
