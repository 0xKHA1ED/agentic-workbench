from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_tree import model as project_tree_model


class TaskBreakdownError(ValueError):
    """Missing or unusable claims/spec inputs for tasks.md generation."""


PATH_TOKEN = re.compile(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+/?")
PHASE_HEADING = re.compile(r"^## Phase (\d+):\s*(.+?)\s*$")
PHASE_MARKER = re.compile(r"<!--\s*task-phase:\s*id=([A-Za-z0-9_-]+)\s+index=(\d+)\s*-->")
TASK_LINE = re.compile(r"^- \[([ xX])\] (T\d+)\s+(.*)$")
SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$")


def tasks_dir(project: str) -> Path:
    return project_tree_model.project_dir(project) / "tasks"


def tasks_paths(project: str, node_id: str) -> dict[str, str]:
    base = project_tree_model.project_dir(project)
    tasks = tasks_dir(project)
    md = tasks / f"{node_id}.md"
    return {
        "tasks_dir": str(tasks),
        "tasks_md": str(md),
        "claims_json": str(base / "claims" / f"{node_id}.json"),
        "spec_md": str(base / "specs" / f"{node_id}.md"),
    }


def extract_path(text: str) -> str:
    matches = PATH_TOKEN.findall(text or "")
    return matches[-1] if matches else ""


def story_label(claim_id: str) -> str:
    raw = str(claim_id or "").strip()
    if re.fullmatch(r"[cC]\d+", raw):
        return f"C{int(raw[1:])}"
    return raw.upper() or "C1"


def _file_ref(raw: str | None) -> str:
    if not raw:
        return ""
    token = str(raw).strip().strip("`")
    token = token.split()[0] if token.split() else token
    if ":" in token:
        left, right = token.rsplit(":", 1)
        if right.isdigit():
            token = left
    return token


def _rel_to_project(project: str, path: Path) -> str:
    base = project_tree_model.project_dir(project)
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def _split_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = "_preamble"
    buf: list[str] = []
    for line in markdown.splitlines():
        heading = SECTION_HEADING.match(line)
        if heading and not line.startswith("###"):
            sections[current] = "\n".join(buf).strip()
            current = heading.group(1).strip()
            buf = []
            continue
        buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def _bullets(body: str) -> list[str]:
    items: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        text = stripped[2:].strip()
        text = re.sub(r"^\[.\]\s*", "", text)
        if text:
            items.append(text)
    return items


def parse_scope_contract(markdown: str) -> dict[str, Any]:
    title = "Untitled"
    first = re.search(r"^#\s+Scope Contract:\s*(.+)$", markdown, re.M)
    if first:
        title = first.group(1).strip()
    else:
        any_h1 = re.search(r"^#\s+(.+)$", markdown, re.M)
        if any_h1:
            title = any_h1.group(1).strip()
    sections = _split_sections(markdown)
    goal_body = sections.get("GOAL", "").strip()
    goal = goal_body.split("\n", 1)[0].strip() if goal_body else ""
    return {
        "title": title,
        "goal": goal,
        "in": _bullets(sections.get("IN", "")),
        "out": _bullets(sections.get("OUT", "")),
        "must": _bullets(sections.get("MUST", "")),
        "must_not": _bullets(sections.get("MUST NOT", "")),
        "verify": _bullets(sections.get("VERIFY", "")),
    }


def _usable_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    approved = [c for c in claims if c.get("decision") == "approved"]
    if approved:
        return approved
    return [c for c in claims if c.get("decision") not in {"rejected", "skipped"}]


def _synthetic_claims_from_spec(spec: dict[str, Any], fallback_path: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for i, text in enumerate(spec.get("must") or [], 1):
        claims.append(
            {
                "id": f"must{i}",
                "kind": "must",
                "text": text,
                "decision": "approved",
                "source": fallback_path,
            }
        )
    for i, text in enumerate(spec.get("verify") or [], 1):
        claims.append(
            {
                "id": f"c{i}",
                "kind": "verify",
                "text": text,
                "decision": "approved",
                "source": fallback_path,
                "check_command": text if text.startswith(("pytest", "python")) else None,
            }
        )
    for i, text in enumerate(spec.get("must_not") or [], 1):
        claims.append(
            {
                "id": f"n{i}",
                "kind": "must_not",
                "text": text,
                "decision": "approved",
                "source": fallback_path,
            }
        )
    return claims


def load_inputs(project: str, node_id: str) -> dict[str, Any]:
    paths = tasks_paths(project, node_id)
    claims_path = Path(paths["claims_json"])
    spec_path = Path(paths["spec_md"])
    claims_data: dict[str, Any] | None = None
    spec_data: dict[str, Any] | None = None

    if claims_path.is_file():
        try:
            loaded = json.loads(claims_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TaskBreakdownError(f"Claims JSON is invalid: {exc}") from exc
        if not isinstance(loaded, dict):
            raise TaskBreakdownError("Claims JSON must be an object")
        claims_data = loaded

    if spec_path.is_file():
        spec_data = parse_scope_contract(spec_path.read_text(encoding="utf-8"))

    if claims_data is None and spec_data is None:
        raise TaskBreakdownError(
            f"No claims JSON or assembled spec for node '{node_id}'. "
            "Assemble a contract or add claims, then retry."
        )

    spec_rel = _rel_to_project(project, spec_path)
    claims_rel = _rel_to_project(project, claims_path)
    fallback_path = claims_rel if claims_path.is_file() else spec_rel

    claims_list = _usable_claims(list((claims_data or {}).get("claims") or []))
    if not claims_list and spec_data is not None:
        claims_list = _synthetic_claims_from_spec(spec_data, fallback_path)
    if not claims_list:
        raise TaskBreakdownError(
            f"No usable claims or spec VERIFY/MUST items for node '{node_id}'. "
            "Assemble a contract or add claims, then retry."
        )

    in_scope = list((claims_data or {}).get("in") or (claims_data or {}).get("in_scope") or [])
    if not in_scope and spec_data:
        in_scope = list(spec_data.get("in") or [])

    title = (
        (claims_data or {}).get("title")
        or (spec_data or {}).get("title")
        or node_id
    )
    goal = (
        str((claims_data or {}).get("goal") or "").strip()
        or str((spec_data or {}).get("goal") or "").strip()
        or f"Deliver approved requirements for {title}"
    )

    return {
        "project": project,
        "node_id": node_id,
        "title": title,
        "goal": goal,
        "in_scope": in_scope,
        "claims": claims_list,
        "claims_rel": claims_rel if claims_path.is_file() else None,
        "spec_rel": spec_rel if spec_path.is_file() else None,
        "fallback_path": fallback_path,
    }


def _claim_path(claim: dict[str, Any], fallback: str) -> str:
    source = _file_ref(claim.get("source"))
    if extract_path(source) or source.endswith((".py", ".md", ".json", ".ts", ".js", ".yaml", ".yml")):
        return source
    check = str(claim.get("check_command") or claim.get("text") or "")
    found = extract_path(check)
    if found:
        return found
    return fallback


def _looks_like_path(item: str) -> bool:
    token = item.strip().strip("`")
    return bool(extract_path(token)) or token.endswith(
        (".py", ".md", ".json", ".ts", ".js", ".yaml", ".yml")
    )


class _Builder:
    def __init__(self) -> None:
        self.n = 0
        self.lines: list[str] = []
        self.phase_index = 0

    def next_id(self) -> str:
        self.n += 1
        return f"T{self.n:03d}"

    def blank(self) -> None:
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def start_phase(self, phase_id: str, title: str, extra: list[str] | None = None) -> None:
        if self.phase_index:
            self.lines.append("---")
            self.lines.append("")
        self.phase_index += 1
        self.lines.append(f"## Phase {self.phase_index}: {title}")
        self.lines.append(f"<!-- task-phase: id={phase_id} index={self.phase_index} -->")
        self.lines.append("")
        for line in extra or []:
            self.lines.append(line)
        if extra:
            self.lines.append("")

    def task(
        self,
        description: str,
        *,
        path: str,
        parallel: bool = False,
        story: str | None = None,
    ) -> None:
        desc = description.rstrip()
        if path and path not in desc:
            desc = f"{desc} in {path}"
        bits = [f"- [ ] {self.next_id()}"]
        if parallel:
            bits.append("[P]")
        if story:
            bits.append(f"[{story}]")
        bits.append(desc)
        self.lines.append(" ".join(bits))


def generate_tasks_markdown(project: str, node_id: str) -> str:
    data = load_inputs(project, node_id)
    claims = data["claims"]
    must = [c for c in claims if c.get("kind") == "must"]
    must_not = [c for c in claims if c.get("kind") == "must_not"]
    verify = [c for c in claims if c.get("kind") == "verify"]
    fallback = data["fallback_path"]

    b = _Builder()
    b.lines.extend(
        [
            f"# Tasks: {data['title']}",
            "",
            f"**Node**: `{node_id}`",
            "**Input**: claims JSON + assembled spec",
            "**Prerequisites**: claims JSON (preferred) and/or assembled spec; plan.md is optional",
            "",
            "## Format: `[ID] [P?] [Story] Description`",
            "",
            "- **[P]**: Can run in parallel (different files, no dependencies)",
            "- **[Story]**: Claim id this task belongs to (e.g. C1)",
            "- Include exact file paths in descriptions",
            "",
        ]
    )

    b.start_phase(
        "setup",
        "Setup (Shared Infrastructure)",
        extra=["**Purpose**: Project initialization and artifact layout"],
    )
    if data["claims_rel"]:
        b.task("Confirm claims JSON at", path=data["claims_rel"])
    if data["spec_rel"]:
        b.task("Confirm assembled spec at", path=data["spec_rel"], parallel=True)
    if not data["claims_rel"] and not data["spec_rel"]:
        b.task("Load node artifacts at", path=fallback)
    in_paths = [item.strip().strip("`") for item in data["in_scope"] if _looks_like_path(str(item))]
    for item in in_paths:
        b.task(f"Review in-scope path {item}", path=item, parallel=True)
    if not in_paths:
        b.task("Review IN/OUT bounds from contract at", path=fallback, parallel=True)

    b.start_phase(
        "foundational",
        "Foundational (Blocking Prerequisites)",
        extra=[
            "**Purpose**: Core constraints that MUST be complete before claim-story work",
            "",
            "**⚠️ CRITICAL**: No claim-story work can begin until this phase is complete",
        ],
    )
    if must:
        for claim in must:
            path = _claim_path(claim, fallback)
            text = str(claim.get("text") or "").strip()
            b.task(f"Honor MUST: {text}", path=path)
    else:
        b.task("Respect IN/OUT bounds before story work at", path=fallback)
    b.blank()
    b.lines.append("**Checkpoint**: Foundation ready — claim-story implementation can begin")
    b.blank()

    for i, claim in enumerate(verify, 1):
        cid = str(claim.get("id") or f"c{i}")
        label = story_label(cid)
        phase_id = cid.lower()
        title = f"Claim {label} — verify (Priority: P{i})"
        if i == 1:
            title += " 🎯 MVP"
        path = _claim_path(claim, fallback)
        text = str(claim.get("text") or "").strip()
        check = str(claim.get("check_command") or "").strip()
        independent = check or text
        extra = [
            f"**Goal**: {text}",
            "",
            f"**Independent Test**: {independent}",
        ]
        b.start_phase(phase_id, title, extra=extra)
        b.task(f"Implement: {text}", path=path, story=label)
        test_path = extract_path(check) or path
        if check:
            b.task(
                f"Execute VERIFY `{check}` covering",
                path=test_path,
                parallel=True,
                story=label,
            )
        b.blank()
        b.lines.append(f"**Checkpoint**: Claim {label} independently testable")
        b.blank()

    b.start_phase(
        "polish",
        "Polish & Cross-Cutting Concerns",
        extra=["**Purpose**: Cross-cutting constraints and close-out"],
    )
    if must_not:
        for claim in must_not:
            path = _claim_path(claim, fallback)
            text = str(claim.get("text") or "").strip()
            b.task(f"Honor MUST NOT: {text}", path=path, parallel=True)
    b.task("Mark VERIFY complete against the contract at", path=data["spec_rel"] or fallback)
    b.blank()
    b.lines.extend(
        [
            "---",
            "",
            "## Dependencies & Execution Order",
            "",
            "- **Setup (Phase 1)**: No dependencies — start immediately",
            "- **Foundational (Phase 2)**: Depends on Setup — BLOCKS claim stories",
            "- **Claim stories (Phase 3+)**: Depend on Foundational; may proceed in listed order",
            "- **Polish (Final Phase)**: Depends on desired claim stories being complete",
            "",
            "## Implementation Strategy",
            "",
            "1. Complete Setup + Foundational",
            "2. Implement the first verify claim (MVP), then stop and validate",
            "3. Continue remaining claim phases, then Polish",
            "4. `/implement` may be scoped to one `<!-- task-phase -->` or a `T00N-T00M` range",
            "",
        ]
    )
    return "\n".join(b.lines).rstrip() + "\n"


def _slug_from_heading(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("setup"):
        return "setup"
    if lowered.startswith("foundational"):
        return "foundational"
    if "polish" in lowered:
        return "polish"
    claim = re.search(r"\bclaim\s+([A-Za-z0-9_-]+)", lowered)
    if claim:
        return claim.group(1).lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "phase"


def parse_tasks_markdown(text: str) -> dict[str, Any]:
    phases: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def ensure_phase() -> dict[str, Any]:
        nonlocal current
        if current is None:
            current = {
                "id": "phase",
                "index": len(phases) + 1,
                "title": "Untitled",
            }
            phases.append(current)
        return current

    for raw in text.splitlines():
        heading = PHASE_HEADING.match(raw)
        if heading:
            current = {
                "id": _slug_from_heading(heading.group(2)),
                "index": int(heading.group(1)),
                "title": heading.group(2).strip(),
            }
            phases.append(current)
            continue
        marker = PHASE_MARKER.search(raw)
        if marker:
            phase = current or ensure_phase()
            phase["id"] = marker.group(1)
            phase["index"] = int(marker.group(2))
            continue
        task_match = TASK_LINE.match(raw)
        if not task_match:
            continue
        phase = ensure_phase()
        done = task_match.group(1).lower() == "x"
        tid = task_match.group(2)
        rest = task_match.group(3).strip()
        parallel = False
        story = None
        if rest.startswith("[P]"):
            parallel = True
            rest = rest[3:].strip()
        story_match = re.match(r"\[([A-Za-z0-9_-]+)\]\s+(.*)$", rest)
        if story_match:
            story = story_match.group(1)
            rest = story_match.group(2).strip()
        description = rest
        path = extract_path(description)
        tasks.append(
            {
                "id": tid,
                "done": done,
                "parallel": parallel,
                "story": story,
                "description": description,
                "path": path,
                "phase_id": phase["id"],
                "phase_index": phase["index"],
            }
        )

    for phase in phases:
        phase["task_count"] = sum(1 for t in tasks if t["phase_id"] == phase["id"])
    return {"phases": phases, "tasks": tasks}


def parse_task_selector(spec: str) -> set[str]:
    raw = (spec or "").strip()
    if not raw:
        return set()
    if "-" in raw and "," not in raw:
        left, right = raw.split("-", 1)
        start = int(re.sub(r"^[Tt]", "", left.strip()))
        end = int(re.sub(r"^[Tt]", "", right.strip()))
        if start > end:
            start, end = end, start
        return {f"T{i:03d}" for i in range(start, end + 1)}
    ids: set[str] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if token[0] in "Tt" and token[1:].isdigit():
            ids.add(f"T{int(token[1:]):03d}")
        else:
            ids.add(token)
    return ids


def scope_tasks(
    parsed: dict[str, Any],
    *,
    phase: str | int | None = None,
    tasks: str | None = None,
) -> dict[str, Any]:
    selected = list(parsed.get("tasks") or [])
    if phase is not None and str(phase).strip() != "":
        key = str(phase).strip().lower()
        key = re.sub(r"^phase\s+", "", key).strip()
        if key.isdigit():
            index = int(key)
            selected = [t for t in selected if int(t["phase_index"]) == index]
        else:
            selected = [t for t in selected if str(t["phase_id"]).lower() == key]
    if tasks:
        wanted = parse_task_selector(tasks)
        selected = [t for t in selected if t["id"] in wanted]
    phases: list[dict[str, Any]] = []
    for phase_meta in parsed.get("phases") or []:
        pts = [t for t in selected if t["phase_id"] == phase_meta["id"]]
        if pts:
            entry = dict(phase_meta)
            entry["task_count"] = len(pts)
            phases.append(entry)
    return {"tasks": selected, "phases": phases}


def write_tasks(project: str, node_id: str) -> dict[str, Any]:
    markdown = generate_tasks_markdown(project, node_id)
    parsed = parse_tasks_markdown(markdown)
    paths = tasks_paths(project, node_id)
    out = Path(paths["tasks_md"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return {
        "project": project,
        "node_id": node_id,
        "tasks_md": paths["tasks_md"],
        "task_count": len(parsed["tasks"]),
        "phase_count": len(parsed["phases"]),
        "phases": [
            {
                "id": p["id"],
                "index": p["index"],
                "title": p["title"],
                "task_count": p.get("task_count", 0),
            }
            for p in parsed["phases"]
        ],
    }
