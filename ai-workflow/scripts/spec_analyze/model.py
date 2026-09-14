from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from project_tree import model as project_tree_model
from project_tree.fragments import compose_tree
from project_tree.model import find_node_in_tree, load_tree
from spec_clarify.model import clarify_paths, constitution_path

VALID_STATUS = frozenset({"in_progress", "complete", "skipped"})
VALID_SEVERITY = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
VALID_CATEGORY = frozenset({"consistency", "coverage", "clarification", "constitution"})

ABORT_MESSAGE = (
    "Claims JSON or assembled scope-contract is missing. "
    "Assemble the spec (spec-discovery assemble) or skip analyze."
)

_HEADING_RE = re.compile(
    r"^##\s+(MUST NOT|MUST|GOAL|IN|OUT|VERIFY|EXAMPLES|ACCEPTANCE)\s*$",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\[.\]\s*)?(.*\S)\s*$")
_STOPWORDS = frozenset(
    "the a an and or to of in for on with is be as by at from that this it not".split()
)
_VAGUE_RE = re.compile(
    r"\b(robust(ly)?|properly|handle\b.+\bgracefully|best practices)\b",
    re.I,
)


class AnalyzeAbort(Exception):
    """Missing claims or assembled contract — do not complete; write no findings."""


def analyze_dir(project: str) -> Path:
    return project_tree_model.project_dir(project) / "analyze"


def analyze_paths(project: str, node_id: str) -> dict[str, str | None]:
    """Resolve findings/status plus read-only input artifact paths.

    Findings and run status live under ``<project>/analyze/``:
    ``<node-id>.findings.json`` and ``<node-id>.analyze.json``.
    """
    proj = project_tree_model.project_dir(project)
    base = proj / "analyze"
    claims = proj / "claims" / f"{node_id}.json"
    contract = proj / "specs" / f"{node_id}.md"
    try:
        composed = compose_tree(load_tree(project), project)
        node = find_node_in_tree(composed, node_id)
        data = (node or {}).get("data") or {}
        for key in ("contract", "spec"):
            rel = data.get(key)
            if rel:
                p = Path(str(rel))
                contract = p if p.is_absolute() else proj / rel
                break
        claims_rel = data.get("claims")
        if claims_rel:
            p = Path(str(claims_rel))
            if p.suffix == ".json":
                claims = p if p.is_absolute() else proj / claims_rel
    except Exception:
        pass

    clar = clarify_paths(project, node_id)
    const = constitution_path(project)
    plan = _first_existing(
        [
            proj / "specs" / node_id / "plan.md",
            proj / "plan.md",
        ]
    )
    tasks = _first_existing(
        [
            proj / "specs" / node_id / "tasks.md",
            proj / "tasks.md",
        ]
    )
    return {
        "analyze_dir": str(base),
        "findings_json": str(base / f"{node_id}.findings.json"),
        "status_json": str(base / f"{node_id}.analyze.json"),
        "claims_json": str(claims),
        "contract_md": str(contract),
        "decisions_json": clar["decisions_json"],
        "constitution_path": str(const) if const else None,
        "plan_md": str(plan) if plan else None,
        "tasks_md": str(tasks) if tasks else None,
    }


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_status(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Analyze status file must be a JSON object")
    status = data.get("status", "in_progress")
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid analyze status '{status}'")
    data["status"] = status
    return data


def save_status(path: Path, data: dict[str, Any]) -> None:
    status = data.get("status", "in_progress")
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid analyze status '{status}'")
    data["status"] = status
    data["updated"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def save_findings(path: Path, data: dict[str, Any]) -> None:
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ValueError("'findings' must be a list")
    for i, item in enumerate(findings):
        if not isinstance(item, dict):
            raise ValueError(f"Finding {i} must be an object")
        sev = item.get("severity")
        if sev not in VALID_SEVERITY:
            raise ValueError(f"Finding {i} has invalid severity '{sev}'")
        cat = item.get("category")
        if cat not in VALID_CATEGORY:
            raise ValueError(f"Finding {i} has invalid category '{cat}'")
    data["updated"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _require_artifacts(project: str, node_id: str) -> dict[str, str | None]:
    paths = analyze_paths(project, node_id)
    claims = Path(paths["claims_json"] or "")
    contract = Path(paths["contract_md"] or "")
    if not claims.is_file() or not contract.is_file():
        raise AnalyzeAbort(ABORT_MESSAGE)
    return paths


def parse_contract(text: str) -> dict[str, Any]:
    sections: dict[str, Any] = {
        "goal": "",
        "in": [],
        "out": [],
        "must": [],
        "must_not": [],
        "verify": [],
    }
    heading_map = {
        "GOAL": "goal",
        "IN": "in",
        "OUT": "out",
        "MUST": "must",
        "MUST NOT": "must_not",
        "VERIFY": "verify",
    }
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if current is None:
            buf = []
            return
        body = "\n".join(buf).strip()
        if current == "goal":
            sections["goal"] = " ".join(line.strip() for line in body.splitlines() if line.strip())
        else:
            items: list[str] = []
            for line in body.splitlines():
                m = _BULLET_RE.match(line)
                if not m:
                    continue
                item = m.group(1).strip()
                if item and item.lower() not in {"(none)", "none"}:
                    items.append(item)
            sections[current] = items
        buf = []

    for line in text.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            flush()
            key = heading_map.get(m.group(1).upper())
            current = key
            continue
        buf.append(line)
    flush()
    return sections


def _tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {t for t in cleaned.split() if t not in _STOPWORDS and len(t) > 2}


def _overlap(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    na, nb = a.lower().strip(), b.lower().strip()
    if na in nb or nb in na:
        return 1.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _best_match(text: str, items: list[str]) -> float:
    if not items:
        return 0.0
    return max(_overlap(text, item) for item in items)


def _new_finding(
    findings: list[dict[str, Any]],
    *,
    category: str,
    severity: str,
    summary: str,
    location: str = "",
    recommendation: str = "",
) -> None:
    findings.append(
        {
            "id": f"f{len(findings) + 1}",
            "category": category,
            "severity": severity,
            "summary": summary,
            "location": location,
            "recommendation": recommendation,
        }
    )


def _load_claims(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise AnalyzeAbort(ABORT_MESSAGE)
    claims = data.get("claims")
    if not isinstance(claims, list):
        data["claims"] = []
    return data


def _active_claims(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("decision") == "rejected":
            continue
        if not str(claim.get("text") or "").strip():
            continue
        out.append(claim)
    return out


def _kind_section(kind: str) -> str:
    if kind == "must_not":
        return "must_not"
    if kind == "must":
        return "must"
    return "verify"


def compute_findings(
    project: str,
    node_id: str,
    *,
    claims_doc: dict[str, Any],
    contract_text: str,
    decisions: dict[str, Any] | None,
    constitution_text: str | None,
    constitution_missing: bool,
) -> dict[str, Any]:
    contract = parse_contract(contract_text)
    claims = _active_claims(claims_doc)
    findings: list[dict[str, Any]] = []

    goal = str(contract.get("goal") or "").strip()
    if not goal:
        _new_finding(
            findings,
            category="consistency",
            severity="HIGH",
            summary="Assembled contract has an empty GOAL.",
            location="contract:GOAL",
            recommendation="Assemble GOAL from approved claims before implement.",
        )

    mapped_claims = 0
    for claim in claims:
        kind = str(claim.get("kind") or "verify")
        text = str(claim["text"])
        section_key = _kind_section(kind)
        section_items = list(contract.get(section_key) or [])
        score = _best_match(text, section_items)
        if kind == "verify":
            score = max(score, _best_match(text, list(contract.get("verify") or [])))
        in_score = _best_match(text, list(contract.get("in") or []))
        out_score = _best_match(text, list(contract.get("out") or []))
        goal_score = _overlap(text, goal) if goal else 0.0
        if score >= 0.25 or goal_score >= 0.5 or in_score >= 0.4:
            mapped_claims += 1
        else:
            _new_finding(
                findings,
                category="coverage",
                severity="HIGH",
                summary=f"Claim {claim.get('id', '?')} is not mapped to contract {section_key.upper()}.",
                location=f"claims:{claim.get('id', '')}",
                recommendation="Align claim text with GOAL/IN/OUT/MUST/MUST NOT/VERIFY or drop the claim.",
            )
        if kind != "must_not" and out_score >= 0.5 and out_score > score:
            _new_finding(
                findings,
                category="consistency",
                severity="HIGH",
                summary=f"Claim {claim.get('id', '?')} overlaps OUT more than its target section.",
                location=f"claims:{claim.get('id', '')}",
                recommendation="Move the boundary to OUT or rewrite the claim.",
            )

    verify_items = list(contract.get("verify") or [])
    mapped_verify = 0
    verify_claims = [c for c in claims if c.get("kind", "verify") == "verify"]
    for item in verify_items:
        if _best_match(item, [str(c.get("text") or "") for c in verify_claims]) >= 0.25:
            mapped_verify += 1
        else:
            _new_finding(
                findings,
                category="coverage",
                severity="MEDIUM",
                summary="VERIFY item has no mapped verify claim.",
                location="contract:VERIFY",
                recommendation="Add a verify claim or remove the orphan VERIFY bullet.",
            )

    if claims and not verify_items and any(c.get("kind", "verify") == "verify" for c in claims):
        _new_finding(
            findings,
            category="consistency",
            severity="HIGH",
            summary="Verify claims exist but contract VERIFY is empty.",
            location="contract:VERIFY",
            recommendation="Assemble VERIFY from approved verify claims.",
        )

    if decisions:
        for entry in decisions.get("decisions") or []:
            if not isinstance(entry, dict):
                continue
            question = str(entry.get("question") or "")
            answer = str(entry.get("answer") or "").strip()
            if not answer:
                continue
            qlow = question.lower()
            in_score = _best_match(answer, list(contract.get("in") or []))
            out_score = _best_match(answer, list(contract.get("out") or []))
            if ("out" in qlow or "scope" in qlow) and in_score >= 0.5 and in_score > out_score:
                _new_finding(
                    findings,
                    category="clarification",
                    severity="HIGH",
                    summary="Clarification answer appears in IN while the question was about exclusion/OUT.",
                    location=f"clarifications:{entry.get('id', '')}",
                    recommendation="Reconcile clarifications decisions with IN/OUT.",
                )
            if "in" in qlow and out_score >= 0.5 and out_score > in_score:
                _new_finding(
                    findings,
                    category="clarification",
                    severity="HIGH",
                    summary="Clarification answer appears in OUT while the question was about IN.",
                    location=f"clarifications:{entry.get('id', '')}",
                    recommendation="Reconcile clarifications decisions with IN/OUT.",
                )
            if in_score >= 0.5 and out_score >= 0.5:
                _new_finding(
                    findings,
                    category="clarification",
                    severity="CRITICAL",
                    summary="Clarification answer is present in both IN and OUT.",
                    location=f"clarifications:{entry.get('id', '')}",
                    recommendation="Remove the contradiction before implement (or skip analyze).",
                )

    if constitution_missing:
        _new_finding(
            findings,
            category="constitution",
            severity="MEDIUM",
            summary="constitution.md is not present; constitution MUST checks were skipped.",
            location="constitution.md",
            recommendation="Add constitution.md or accept the fallback when one exists.",
        )
    elif constitution_text:
        must_chunk = constitution_text
        m = re.search(r"^##\s+MUST\b.*?(?=^##\s+|\Z)", constitution_text, re.I | re.M | re.S)
        if m:
            must_chunk = m.group(0)
        contract_blob = " ".join(
            [
                goal,
                " ".join(contract.get("must") or []),
                " ".join(contract.get("in") or []),
                " ".join(c.get("text") or "" for c in claims),
            ]
        )
        if _VAGUE_RE.search(contract_blob) and re.search(r"\bMUST\b", must_chunk):
            _new_finding(
                findings,
                category="constitution",
                severity="CRITICAL",
                summary="Contract or claims use vague language banned by constitution MUST (falsifiable VERIFY).",
                location="constitution:MUST",
                recommendation="Rewrite vague GOAL/claims; do not dilute the constitution.",
            )
        principles = re.findall(r"^###\s+(.+)$", must_chunk, re.M)
        out_blob = " ".join(contract.get("out") or [])
        must_not_blob = " ".join(contract.get("must_not") or [])
        for title in principles:
            if _overlap(title, out_blob) >= 0.6:
                _new_finding(
                    findings,
                    category="constitution",
                    severity="CRITICAL",
                    summary=f"Constitution MUST principle '{title.strip()}' overlaps contract OUT.",
                    location="constitution:MUST",
                    recommendation="Adjust the spec, not the constitution.",
                )
            if _overlap(title, must_not_blob) >= 0.6:
                _new_finding(
                    findings,
                    category="constitution",
                    severity="HIGH",
                    summary=f"Constitution MUST principle '{title.strip()}' overlaps contract MUST NOT.",
                    location="constitution:MUST",
                    recommendation="Check whether the red line contradicts a non-negotiable principle.",
                )

    findings = findings[:50]
    return {
        "project": project,
        "node_id": node_id,
        "checks": ["consistency", "coverage", "clarification", "constitution"],
        "findings": findings,
        "coverage": {
            "claims_total": len(claims),
            "claims_mapped": mapped_claims,
            "verify_total": len(verify_items),
            "verify_mapped": mapped_verify,
        },
        "critical_count": sum(1 for f in findings if f.get("severity") == "CRITICAL"),
    }


def run_analyze(project: str, node_id: str, *, persist: bool = True) -> dict[str, Any]:
    """Read artifacts, compute findings. Writes findings + in_progress status only.

    Never writes claims, assembled contract, nodes.yaml, fragments, or constitution.
    plan.md / tasks.md are optional — absence does not abort.
    """
    paths = _require_artifacts(project, node_id)
    claims_doc = _load_claims(Path(paths["claims_json"] or ""))
    contract_text = Path(paths["contract_md"] or "").read_text(encoding="utf-8")

    decisions = None
    decisions_path = Path(paths["decisions_json"] or "")
    if decisions_path.is_file():
        with decisions_path.open() as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            decisions = raw

    const_path = paths.get("constitution_path")
    constitution_text = None
    constitution_missing = True
    if const_path and Path(const_path).is_file():
        constitution_missing = False
        constitution_text = Path(const_path).read_text(encoding="utf-8")

    doc = compute_findings(
        project,
        node_id,
        claims_doc=claims_doc,
        contract_text=contract_text,
        decisions=decisions,
        constitution_text=constitution_text,
        constitution_missing=constitution_missing,
    )
    if persist:
        save_findings(Path(paths["findings_json"] or ""), doc)
        save_status(
            Path(paths["status_json"] or ""),
            {
                "project": project,
                "node_id": node_id,
                "status": "in_progress",
                "findings_json": paths["findings_json"],
                "critical_count": doc.get("critical_count", 0),
            },
        )
    return doc


def complete_analyze(project: str, node_id: str, *, status: str = "complete") -> dict[str, Any]:
    if status not in ("complete", "skipped"):
        raise ValueError("status must be 'complete' or 'skipped'")
    if status == "skipped":
        return skip_analyze(project, node_id)
    doc = run_analyze(project, node_id, persist=True)
    paths = analyze_paths(project, node_id)
    status_doc = {
        "project": project,
        "node_id": node_id,
        "status": "complete",
        "findings_json": paths["findings_json"],
        "critical_count": doc.get("critical_count", 0),
    }
    save_status(Path(paths["status_json"] or ""), status_doc)
    return status_doc


def skip_analyze(project: str, node_id: str) -> dict[str, Any]:
    paths = analyze_paths(project, node_id)
    status_doc = {
        "project": project,
        "node_id": node_id,
        "status": "skipped",
        "findings_json": paths["findings_json"],
        "critical_count": 0,
    }
    save_status(Path(paths["status_json"] or ""), status_doc)
    return status_doc


def analyze_blocks_implement(project: str, node_id: str) -> str | None:
    """Return an error if /implement Phase 1 must stop.

    CRITICAL findings do not hard-block after status is complete or skipped.
    """
    paths = analyze_paths(project, node_id)
    path = Path(paths["status_json"] or "")
    if not path.is_file():
        return (
            "Analyze status is missing. Run /spec-analyze or skip "
            "(workflow_analyze_skip / workflow_analyze_complete status=skipped) before /implement."
        )
    try:
        doc = load_status(path)
    except (ValueError, json.JSONDecodeError):
        return "Analyze status file is invalid. Re-run /spec-analyze or skip before /implement."
    st = doc.get("status")
    if st == "in_progress":
        return "Analyze is in_progress. Complete or skip before /implement."
    if st in ("complete", "skipped"):
        return None
    return f"Analyze status '{st}' is not complete or skipped."


def analyze_blocks_verification(project: str, node_id: str) -> str | None:
    """Gate workflow_execute_verification for implement-ready nodes.

    Always blocks in_progress. Blocks missing status only when an assembled
    contract exists (claims-only or verification-only nodes stay runnable).
    CRITICAL after complete/skip does not block.
    """
    paths = analyze_paths(project, node_id)
    status_path = Path(paths["status_json"] or "")
    if status_path.is_file():
        try:
            doc = load_status(status_path)
        except (ValueError, json.JSONDecodeError):
            return analyze_blocks_implement(project, node_id)
        if doc.get("status") == "in_progress":
            return analyze_blocks_implement(project, node_id)
        if doc.get("status") in ("complete", "skipped"):
            return None
    contract = Path(paths["contract_md"] or "")
    if contract.is_file():
        return analyze_blocks_implement(project, node_id)
    return None
