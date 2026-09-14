---
name: requirements-checklist
description: Spec Kit requirements checklist — unit tests for English. Generate reviewer-owned checklists from claims/assembled spec; user-only [x] markers; read-only implement gate. Use after spec-discovery assemble, before /implement, or when the user runs /requirements-checklist.
disable-model-invocation: true
---

# Requirements Checklist

Generate and review **unit tests for requirements writing** — not tests of implementation. Checkboxes are **user/reviewer-only**. Agents must not mark `[x]`.

Announce: "Using requirements-checklist skill."

## When to use

After **spec-discovery assemble** (claims JSON + `specs/<node-id>.md`), **before `/implement`**, when:

- The spec might still be incomplete, vague, or internally inconsistent
- The user asks for a requirements checklist / `/requirements-checklist`
- `/implement` reports unchecked custom checklist items

**Skip** for tiny, already-triaged nodes if the user says so — warn that rework risk increases.

## Hard gate (implement)

`/implement` Phase 1 calls **`workflow_checklist_status`** (read-only counts). If `blocks_implement` is true (any unchecked `[ ]` in `checklists/<node-id>/`), **STOP** and ask the reviewer to mark items or confirm they want to proceed. **Do not toggle markers.**

`[x]` means the reviewer accepted **requirements quality**. It does **not** mean implementation is done.

---

## Step 0 — Paths / status

MCP (read-only):

```json
{ "project": "<project>", "node_id": "<node_id>" }
```

Tool: `workflow_checklist_status`

CLI:

```bash
python3 scripts/spec_checklist.py paths meta <node_id> --json
python3 scripts/spec_checklist.py status meta <node_id> --json
```

Artifacts live at `<project-dir>/checklists/<node-id>/`:

| File | Kind |
|------|------|
| `requirements.md` | Built-in spec-quality checklist |
| `<domain>.md` (e.g. `ux.md`) | Custom, reviewer-owned |

---

## Step 1 — Generate from claims / assembled spec

```bash
python3 scripts/spec_checklist.py generate <project> <node_id> --json
python3 scripts/spec_checklist.py generate <project> <node_id> --domain ux --json
```

Rules:

- Source: `claims/<node-id>.json` and/or `specs/<node-id>.md` (works if only one exists)
- Every **new** item is `- [ ] CHK### …` — never pre-checked
- Existing files are **appended**, never rewritten; existing `[x]` stays `[x]`
- Items ask about **what is written** (completeness, clarity, consistency, measurability, coverage) — not runtime behavior
- Banned item shapes: “Verify/Test/Confirm the button works”, code execution, click/navigate/render

Then:

```bash
python3 scripts/spec_checklist.py validate <project-dir>/checklists/<node-id>/requirements.md --require-unchecked
```

`--require-unchecked` is the **user-only** generation contract: fail if any box is already `[x]`.

---

## Step 2 — Reviewer marks boxes

The **human** edits markdown in the editor (or Cockpit later). Agent may **summarize** unchecked items when asked. Agent may **not** change `[ ]` / `[x]`.

If gaps appear, loop back to `/spec-clarify` or spec-discovery — then regenerate (append-only).

---

## Step 3 — Handoff to implement

When `workflow_checklist_status` returns `blocks_implement: false` (or the user explicitly proceeds), run **`/implement`**.

Implement must:

1. Print the status table (file / total / checked / unchecked)
2. If unchecked **custom** checklists (`*.md` other than `requirements.md`) — **STOP** (user-only gate)
3. Count only — **read-only**; never write checklist files

---

## Anti-patterns

- Marking `[x]` as the implementing agent
- Writing implementation-test items (“verify the API returns 200”)
- Deleting or rewriting a checklist that already has reviewer marks
- Skipping the status call when `checklists/<node-id>/` exists

## Reference

Inspired by Spec Kit `templates/commands/checklist.md` + `checklist-template.md` and the `/speckit.implement` read-only checkbox gate.
