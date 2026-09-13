from __future__ import annotations

from pathlib import Path
from typing import Any

from .model import approved_claims, save_document, spec_output_path


def _bullets(items: list[str]) -> str:
    if not items:
        return "- (none)\n"
    return "".join(f"- {item}\n" for item in items)


def _section_claims(claims: list[dict[str, Any]], kind: str) -> list[str]:
    return [c["text"] for c in claims if c.get("kind") == kind]


def _format_verify_bullet(claim: dict[str, Any]) -> str:
    execution = claim.get("execution")
    if not execution:
        return claim["text"]

    exec_type = execution["type"]
    if exec_type in ("command", "pytest"):
        command = execution["command"]
        return f"check_type: {exec_type} | `{command}`"

    file_path = execution["file"]
    symbols = ", ".join(execution["symbols"])
    return f"check_type: ast_symbol | `{file_path}` exports `[{symbols}]`"


def _examples_table(claims: list[dict[str, Any]]) -> str:
    rows: list[tuple[str, str, str]] = []
    for claim in claims:
        for ex in claim.get("examples") or []:
            if not isinstance(ex, dict):
                continue
            case = str(ex.get("case") or claim.get("id") or "case")
            inp = str(ex.get("input") or ex.get("situation") or "")
            expected = str(ex.get("expected") or "")
            if inp or expected:
                rows.append((case, inp, expected))
    if not rows:
        return ""
    lines = [
        "## EXAMPLES",
        "| Case | Input / Situation | Expected |",
        "|------|-------------------|----------|",
    ]
    for case, inp, expected in rows[:4]:
        lines.append(f"| {case} | {inp} | {expected} |")
    return "\n".join(lines) + "\n"


def build_markdown(data: dict[str, Any]) -> str:
    if not data.get("goal_approved"):
        raise ValueError("GOAL not approved — run review and approve GOAL first")

    approved = approved_claims(data)
    if not approved:
        raise ValueError("No approved claims — run review first")

    title = data.get("title") or data.get("node") or "Untitled"
    goal = str(data.get("goal") or f"Deliver approved requirements for {title}").strip()

    must = _section_claims(approved, "must")
    must_not = _section_claims(approved, "must_not")
    verify_claims = [c for c in approved if c.get("kind") == "verify"]
    verify_bullets = [_format_verify_bullet(c) for c in verify_claims]
    acceptance_bullets = [c["text"] for c in verify_claims]

    in_scope = list(data.get("in") or [])
    out_scope = list(data.get("out") or [])

    parts = [
        f"# Scope Contract: {title}",
        "",
        "## GOAL",
        goal,
        "",
        "## IN",
        _bullets(in_scope).rstrip(),
        "",
        "## OUT",
        _bullets(out_scope).rstrip(),
        "",
        "## MUST",
        _bullets(must).rstrip() if must else "- (none)",
        "",
        "## MUST NOT",
        _bullets(must_not).rstrip() if must_not else "- (none)",
        "",
        "## VERIFY",
    ]
    if verify_bullets:
        parts.extend(f"- [ ] {item}" for item in verify_bullets)
    else:
        parts.append("- [ ] (none)")

    examples = _examples_table(approved)
    if examples:
        parts.extend(["", examples.rstrip()])

    parts.extend(
        [
            "",
            "## ACCEPTANCE",
        ]
    )
    for item in acceptance_bullets:
        parts.append(f"- [ ] {item}")

    node = data.get("node")
    project = data.get("project")
    if node and project:
        parts.extend(["", f"<!-- spec-discovery: project={project} node={node} -->"])

    return "\n".join(parts) + "\n"


def run_assemble(claims_path: Path, output: Path | None = None) -> int:
    from .model import load_document, normalize_document

    data = normalize_document(load_document(claims_path))
    markdown = build_markdown(data)
    out = output or spec_output_path(data, claims_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown)
    try:
        data["spec_path"] = str(out.relative_to(out.parents[2]))
    except ValueError:
        data["spec_path"] = str(out)
    save_document(claims_path, data)
    print(f"Wrote {out}")
    return 0
