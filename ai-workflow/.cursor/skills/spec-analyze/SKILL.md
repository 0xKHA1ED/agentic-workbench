---
name: spec-analyze
description: Read-only claims/contract consistency gate before /implement — findings JSON + complete/skip status. Never edits claims, contract, tree, or constitution. Use after spec-discovery assemble.
disable-model-invocation: true
---

# Spec Analyze

Read-only **claims ↔ assembled scope-contract** consistency check for a tree node **after** assemble and **before** `/implement`. Analyze reports findings; it never writes spec artifacts.

Announce: "Using spec-analyze skill."

## When to use

After **spec-discovery assemble** (claims JSON + `specs/<node-id>.md`), before `/implement`.

**Skip** for tiny nodes — warn that coverage gaps may surface in implement (`skip` → `workflow_analyze_skip` or `workflow_analyze_complete` with `status: skipped`).

## Hard gate

Do **not** start `/implement` until:

- `workflow_analyze_complete` with `status: complete`, or
- user explicitly skips (`status: skipped` / `workflow_analyze_skip`).

`workflow_execute_verification` enforces the same gate when an assembled contract exists or analyze is `in_progress`.

**CRITICAL findings do not hard-block** after complete or skip. Report them; proceed unless the user stops.

---

## Step 0 — Context (`workflow_analyze_context`)

```json
{ "project": "<project>", "node_id": "<node_id>" }
```

Use returned `paths` and `session.status`. CLI:

```bash
python3 scripts/spec_analyze.py paths meta <node_id> --json
```

Artifacts (resolved outstanding `findings-path-and-mcp-ids`):

| File | Path |
|------|------|
| Findings | `<project-dir>/analyze/<node-id>.findings.json` |
| Status | `<project-dir>/analyze/<node-id>.analyze.json` |

---

## Step 1 — Inputs (read-only)

Must exist or **abort** (do not mark complete; write **no** findings file; tell the user to **assemble** or **skip**):

- claims JSON
- assembled scope-contract

Also read when present:

- clarifications `*.decisions.json`
- `constitution.md` (missing → finding, not abort)

`plan.md` and `tasks.md` are **not** required. Do not run Spec Kit duplication/ambiguity/underspec prose-lint (that is `ref-sk-analyze-cross`).

**MUST NOT** modify claims JSON, assembled contract markdown, `nodes.yaml`, fragment YAML, or `constitution.md`.

---

## Step 2 — Run (`workflow_analyze_run`)

```json
{ "project": "<project>", "node_id": "<node_id>" }
```

Read-only vs spec artifacts. Persists findings JSON and `in_progress` status only.

Findings include `category` and `severity` in `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`, covering:

- claims vs GOAL / IN / OUT / MUST / MUST NOT / VERIFY
- clarification contradictions
- constitution MUST when `constitution.md` exists
- unmapped claims or VERIFY

CLI:

```bash
python3 scripts/spec_analyze.py run <project> <node_id>
```

---

## Step 3 — Complete or skip

```json
{ "project": "<project>", "node_id": "<node_id>", "status": "complete" }
```

Or skip (no claims/contract required):

```json
{ "project": "<project>", "node_id": "<node_id>", "status": "skipped" }
```

CLI:

```bash
python3 scripts/spec_analyze.py complete <project> <node_id>
python3 scripts/spec_analyze.py skip <project> <node_id>
```

Present CRITICAL/HIGH counts. Ask: **Proceed to /implement anyway?** (complete/skip already unblocks the gate.)

---

## Step 4 — Handoff to /implement

`/implement` Phase 1 **STOPS** when analyze status is missing or `in_progress`. After complete or skip, implement may run even if findings contain CRITICAL.

---

## Anti-patterns

- Editing claims, contract, tree, or constitution from analyze
- Blocking `/implement` solely because findings contain CRITICAL after complete/skip
- Requiring `plan.md` or `tasks.md`
- Cockpit findings UI (deferred)
- Spec Kit prose-lint (deferred to `ref-sk-analyze-cross`)

---

## Reference

Inspired by Spec Kit `templates/commands/analyze.md` (v1: claims + assembled contract, not spec/plan/tasks triad).
