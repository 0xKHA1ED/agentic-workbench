"""Requirements-quality checklists for tree nodes (Spec Kit parity).

Checkboxes are reviewer-owned. Generators always emit `[ ]`. Status/MCP
scans are read-only and must never rewrite markers.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from project_tree.fragments import compose_tree
from project_tree.model import PACKAGE_ROOT, find_node_in_tree, load_tree, project_dir
from spec_discovery.model import claims_dir, specs_dir

ITEM_RE = re.compile(
    r"^(?P<indent>\s*)-\s+\[(?P<mark>[ xX])\]\s+(?:(?P<id>CHK\d{3})\s+)?(?P<text>.+?)\s*$"
)
DOMAIN_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
CHK_PREFIX_RE = re.compile(r"^CHK\d{3}\s+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

MAX_CLAIM_ITEMS = 24
MAX_TOTAL_ITEMS = 40

CORE_ITEMS: list[tuple[str, str]] = [
    (
        "Requirement Completeness",
        "Is GOAL documented as one observable outcome? [Completeness]",
    ),
    (
        "Requirement Completeness",
        "Are IN-scope surfaces listed and non-empty? [Completeness]",
    ),
    (
        "Requirement Completeness",
        "Are OUT-of-scope exclusions explicit? [Completeness]",
    ),
    (
        "Requirement Clarity",
        "Are MUST items specific and unambiguous (no vague language)? [Clarity]",
    ),
    (
        "Requirement Consistency",
        "Do MUST NOT items conflict with GOAL or MUST? [Consistency]",
    ),
    (
        "Acceptance Criteria Quality",
        "Is at least one VERIFY claim present and measurable? [Measurability]",
    ),
    (
        "Scenario Coverage",
        "Are failure and edge-case requirements addressed in OUT or MUST NOT? [Coverage]",
    ),
    (
        "Dependencies & Assumptions",
        "Are assumptions and dependencies documented or explicitly absent? [Completeness]",
    ),
]


def checklists_dir(project: str, node_id: str) -> Path:
    return project_dir(project) / "checklists" / node_id


def checklist_paths(project: str, node_id: str) -> dict[str, str]:
    base = checklists_dir(project, node_id)
    return {
        "checklists_dir": str(base),
        "requirements_md": str(base / "requirements.md"),
    }


def template_path() -> Path:
    candidates = (
        PACKAGE_ROOT / "meta" / "templates" / "requirements-checklist-template.md",
        Path(__file__).resolve().parent / "assets" / "requirements-checklist-template.md",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "requirements-checklist-template.md not found under meta/templates/ or spec_checklist/assets/"
    )


def read_template() -> str:
    return template_path().read_text(encoding="utf-8")


def sanitize_domain(domain: str) -> str:
    value = (domain or "requirements").strip().lower()
    if not DOMAIN_RE.match(value):
        raise ValueError(
            f"Invalid checklist domain '{domain}': use lowercase letters, digits, and hyphens"
        )
    return value


def checklist_filename(domain: str) -> str:
    return f"{sanitize_domain(domain)}.md"


def is_custom_checklist(filename: str) -> bool:
    return Path(filename).name != "requirements.md"


def normalize_item_text(text: str) -> str:
    stripped = CHK_PREFIX_RE.sub("", (text or "").strip())
    return re.sub(r"\s+", " ", stripped).lower()


def parse_checklist_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = ITEM_RE.match(line)
        if not match:
            continue
        mark = match.group("mark")
        items.append(
            {
                "line": line_no,
                "indent": match.group("indent") or "",
                "checked": mark.lower() == "x",
                "id": match.group("id"),
                "text": (match.group("text") or "").strip(),
                "raw": line,
            }
        )
    return items


def next_chk_number(items: list[dict[str, Any]]) -> int:
    highest = 0
    for item in items:
        ident = item.get("id") or ""
        if ident.startswith("CHK") and ident[3:].isdigit():
            highest = max(highest, int(ident[3:]))
    return highest + 1


def format_chk(number: int) -> str:
    return f"CHK{number:03d}"


def validate_checklist_text(
    text: str,
    *,
    require_unchecked: bool = False,
    require_ids: bool = True,
) -> list[dict[str, Any]]:
    """Validate checkbox structure. Raises ValueError on failure.

    require_unchecked: generation contract — every item must still be `[ ]`
    (user-only ownership; agents must not pre-check).
    """
    items = parse_checklist_items(text)
    if not items:
        raise ValueError("Checklist has no checkbox items")

    seen_ids: set[str] = set()
    for i, item in enumerate(items):
        ident = item.get("id")
        if require_ids and not ident:
            raise ValueError(f"Checklist item on line {item['line']} is missing a CHK id")
        if ident:
            if ident in seen_ids:
                raise ValueError(f"Duplicate checklist id {ident}")
            seen_ids.add(ident)
        if require_unchecked and item["checked"]:
            raise ValueError(
                f"Item {ident or i} is checked; generation and agents must leave "
                "checkboxes unchecked for the reviewer (user-only)"
            )
    return items


def validate_checklist_file(path: Path, *, require_unchecked: bool = False) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Checklist file not found: {path}")
    return validate_checklist_text(
        path.read_text(encoding="utf-8"),
        require_unchecked=require_unchecked,
    )


def _node_title(project: str, node_id: str) -> str:
    try:
        node = find_node_in_tree(compose_tree(load_tree(project), project), node_id)
        if node and node.get("title"):
            return str(node["title"])
    except Exception:
        pass
    return node_id


def load_node_sources(project: str, node_id: str) -> dict[str, Any]:
    claims_path = claims_dir(project) / f"{node_id}.json"
    spec_path = specs_dir(project) / f"{node_id}.md"
    claims: dict[str, Any] | None = None
    if claims_path.is_file():
        raw = json.loads(claims_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            claims = raw
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else None
    return {
        "claims": claims,
        "spec_text": spec_text,
        "claims_path": claims_path if claims_path.is_file() else None,
        "spec_path": spec_path if spec_path.is_file() else None,
        "title": (claims or {}).get("title") or _node_title(project, node_id),
        "goal": (claims or {}).get("goal"),
    }


def plan_items(sources: dict[str, Any]) -> list[tuple[str, str]]:
    """Build (category, question) pairs from claims / assembled spec."""
    planned: list[tuple[str, str]] = list(CORE_ITEMS)
    claims = sources.get("claims")
    spec_text = sources.get("spec_text")

    if claims is None and not spec_text:
        planned.append(
            (
                "Requirement Completeness",
                "Are claims JSON or an assembled spec present for this node? [Gap]",
            )
        )
        return planned[:MAX_TOTAL_ITEMS]

    if spec_text:
        planned.append(
            (
                "Requirement Completeness",
                "Does the assembled spec include GOAL, IN, OUT, MUST, MUST NOT, and VERIFY sections? [Completeness, Spec]",
            )
        )
        if claims and str(claims.get("goal") or "").strip():
            planned.append(
                (
                    "Requirement Consistency",
                    "Does assembled spec GOAL match the claims GOAL? [Consistency, Spec]",
                )
            )

    if not isinstance(claims, dict):
        return planned[:MAX_TOTAL_ITEMS]

    claim_list = claims.get("claims") if isinstance(claims.get("claims"), list) else []
    pending = [c for c in claim_list if isinstance(c, dict) and c.get("decision", "pending") == "pending"]
    if pending:
        planned.append(
            (
                "Requirement Completeness",
                "Are all claims triaged (no pending decisions remain)? [Gap]",
            )
        )

    verify_claims = [
        c for c in claim_list if isinstance(c, dict) and c.get("kind", "verify") == "verify"
    ]
    if claim_list and not verify_claims:
        planned.append(
            (
                "Acceptance Criteria Quality",
                "Is a VERIFY claim with an executable check documented? [Gap]",
            )
        )

    added = 0
    for claim in claim_list:
        if added >= MAX_CLAIM_ITEMS:
            planned.append(
                (
                    "Scenario Coverage",
                    "Are remaining claims covered by the items above? [Coverage]",
                )
            )
            break
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("id") or f"c{added + 1}")
        kind = str(claim.get("kind") or "verify")
        planned.append(
            (
                "Requirement Clarity",
                f"Is {kind} claim {claim_id} falsifiable and unambiguous? [Clarity, Claim {claim_id}]",
            )
        )
        added += 1
        if kind == "verify":
            has_check = bool(
                str(claim.get("check_command") or "").strip()
                or (isinstance(claim.get("execution"), dict) and claim["execution"])
            )
            if not has_check:
                planned.append(
                    (
                        "Acceptance Criteria Quality",
                        f"Does VERIFY claim {claim_id} name an executable check? [Gap, Claim {claim_id}]",
                    )
                )
                added += 1

    return planned[:MAX_TOTAL_ITEMS]


def _format_body(planned: list[tuple[str, str]], start_number: int) -> str:
    grouped: list[tuple[str, list[str]]] = []
    for category, text in planned:
        if not grouped or grouped[-1][0] != category:
            grouped.append((category, []))
        grouped[-1][1].append(text)

    number = start_number
    parts: list[str] = []
    for category, texts in grouped:
        parts.append(f"## {category}")
        parts.append("")
        for text in texts:
            parts.append(f"- [ ] {format_chk(number)} {text}")
            number += 1
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_checklist_markdown(
    *,
    checklist_type: str,
    feature_name: str,
    created: str,
    feature_link: str,
    node_id: str,
    purpose: str,
    body: str,
) -> str:
    tpl = read_template()
    replacements = {
        "[CHECKLIST TYPE]": checklist_type,
        "[FEATURE NAME]": feature_name,
        "[DATE]": created,
        "[Link to spec.md or relevant documentation]": feature_link,
        "[NODE_ID]": node_id,
        "[PURPOSE]": purpose,
        "[BODY]": body.rstrip(),
    }
    for placeholder, value in replacements.items():
        tpl = tpl.replace(placeholder, value)
    tpl = HTML_COMMENT_RE.sub("", tpl)
    return tpl.strip() + "\n"


def _feature_link(sources: dict[str, Any]) -> str:
    spec_path = sources.get("spec_path")
    claims_path = sources.get("claims_path")
    if spec_path:
        return str(spec_path)
    if claims_path:
        return str(claims_path)
    return "(no assembled spec or claims JSON)"


def _insert_before_notes(text: str, addition: str) -> str:
    marker = "## Notes"
    block = addition.rstrip() + "\n\n"
    if marker in text:
        head, tail = text.split(marker, 1)
        return head.rstrip() + "\n\n" + block + marker + tail.lstrip("\n")
    return text.rstrip() + "\n\n" + block


def generate_checklist(
    project: str,
    node_id: str,
    *,
    domain: str = "requirements",
) -> dict[str, Any]:
    """Create or append a checklist. Newly written items are always unchecked."""
    domain = sanitize_domain(domain)
    filename = checklist_filename(domain)
    dest_dir = checklists_dir(project, node_id)
    dest = dest_dir / filename
    sources = load_node_sources(project, node_id)
    planned = plan_items(sources)

    if dest.is_file():
        existing_text = dest.read_text(encoding="utf-8")
        existing_items = parse_checklist_items(existing_text)
        known = {normalize_item_text(item["text"]) for item in existing_items}
        new_planned = [
            (category, text)
            for category, text in planned
            if normalize_item_text(text) not in known
        ]
        if not new_planned:
            validate_checklist_text(existing_text, require_ids=True)
            return {
                "path": str(dest),
                "created": False,
                "appended": 0,
                "total_items": len(existing_items),
                "checked": sum(1 for item in existing_items if item["checked"]),
                "domain": domain,
                "kind": "custom" if is_custom_checklist(filename) else "requirements",
            }
        body = _format_body(new_planned, next_chk_number(existing_items))
        dest.write_text(_insert_before_notes(existing_text, body), encoding="utf-8")
        merged = parse_checklist_items(dest.read_text(encoding="utf-8"))
        validate_checklist_text(dest.read_text(encoding="utf-8"), require_ids=True)
        return {
            "path": str(dest),
            "created": False,
            "appended": len(new_planned),
            "total_items": len(merged),
            "checked": sum(1 for item in merged if item["checked"]),
            "domain": domain,
            "kind": "custom" if is_custom_checklist(filename) else "requirements",
        }

    dest_dir.mkdir(parents=True, exist_ok=True)
    body = _format_body(planned, 1)
    checklist_type = "Requirements Quality" if domain == "requirements" else domain.replace("-", " ").title()
    purpose = (
        "Validate specification completeness and quality before implement"
        if domain == "requirements"
        else f"Reviewer-owned {domain} requirements-quality checks before implement"
    )
    markdown = render_checklist_markdown(
        checklist_type=checklist_type,
        feature_name=str(sources.get("title") or node_id),
        created=date.today().isoformat(),
        feature_link=_feature_link(sources),
        node_id=node_id,
        purpose=purpose,
        body=body,
    )
    validate_checklist_text(markdown, require_unchecked=True, require_ids=True)
    dest.write_text(markdown, encoding="utf-8")
    items = parse_checklist_items(markdown)
    return {
        "path": str(dest),
        "created": True,
        "appended": len(items),
        "total_items": len(items),
        "checked": 0,
        "domain": domain,
        "kind": "custom" if is_custom_checklist(filename) else "requirements",
    }


def _file_status(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    items = parse_checklist_items(text)
    checked = sum(1 for item in items if item["checked"])
    total = len(items)
    unchecked = total - checked
    return {
        "file": path.name,
        "path": str(path),
        "kind": "custom" if is_custom_checklist(path.name) else "requirements",
        "total": total,
        "checked": checked,
        "unchecked": unchecked,
        "status": "pass" if unchecked == 0 and total > 0 else "fail" if total else "empty",
        "items": [
            {
                "id": item.get("id"),
                "checked": item["checked"],
                "text": item["text"],
            }
            for item in items
            if not item["checked"]
        ],
    }


def scan_checklist_status(project: str, node_id: str) -> dict[str, Any]:
    """Read-only checkbox counts. Never writes files or markers."""
    base = checklists_dir(project, node_id)
    payload: dict[str, Any] = {
        "project": project,
        "node_id": node_id,
        "checklists_dir": str(base),
        "exists": base.is_dir(),
        "read_only": True,
        "checklists": [],
        "total": 0,
        "checked": 0,
        "unchecked": 0,
        "unchecked_custom": 0,
        "unchecked_requirements": 0,
        "overall": "absent",
        "blocks_implement": False,
        "note": "Read-only counts. Do not modify [ ] / [x] markers.",
    }
    if not base.is_dir():
        return payload

    files = sorted(
        (path for path in base.glob("*.md") if path.is_file()),
        key=lambda p: (p.name != "requirements.md", p.name),
    )
    rows = [_file_status(path) for path in files]
    payload["checklists"] = [
        {k: v for k, v in row.items() if k != "items"} | {"unchecked_items": row["items"]}
        for row in rows
    ]
    payload["total"] = sum(row["total"] for row in rows)
    payload["checked"] = sum(row["checked"] for row in rows)
    payload["unchecked"] = sum(row["unchecked"] for row in rows)
    payload["unchecked_custom"] = sum(
        row["unchecked"] for row in rows if row["kind"] == "custom"
    )
    payload["unchecked_requirements"] = sum(
        row["unchecked"] for row in rows if row["kind"] == "requirements"
    )
    if not rows or payload["total"] == 0:
        payload["overall"] = "absent"
        payload["blocks_implement"] = False
    elif payload["unchecked"] == 0:
        payload["overall"] = "pass"
        payload["blocks_implement"] = False
    else:
        payload["overall"] = "fail"
        # Custom checklists are the user-only implement gate; requirements.md
        # unchecked also blocks so a generated-but-unreviewed spec cannot skip review.
        payload["blocks_implement"] = True
    return payload


def checklist_blocks_implement(project: str, node_id: str) -> str | None:
    """Return a stop message when unchecked checklist items block /implement."""
    status = scan_checklist_status(project, node_id)
    if not status.get("blocks_implement"):
        return None
    custom = status.get("unchecked_custom") or 0
    kind = "custom checklist" if custom else "requirements checklist"
    return (
        f"{status['unchecked']} unchecked {kind} item(s) for {project}/{node_id}. "
        "Reviewer must mark [x] (user-only). Agents must not toggle markers. "
        "Call workflow_checklist_status for counts."
    )
