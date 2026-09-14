---
name: technical-plan
description: Optional HOW plan.md separate from scope-contract WHEN/WHY. Use after an approved spec when architecture or file map is non-obvious, before /implement. Skip for bounded nodes. Persist plans/<node-id>.plan.md and link via tree data.plan.
disable-model-invocation: true
---

# Technical Plan

Scope-contract is **WHEN/WHY** — GOAL, IN, OUT, MUST, VERIFY. This skill writes **HOW** — approach, file map, sequencing — in an **optional** plan file. The contract stays the source of truth for DONE.

Announce: "Using technical-plan skill."

## When to use

After **scope-contract is approved** (assembled spec / `spec_approved`), **before** `/implement`, when:

- Multiple reasonable architectures would still pass the same VERIFY, or
- File map / sequencing is non-obvious, or
- The user asks for a plan.

**Skip** for bounded nodes — `/implement` can follow IN + VERIFY directly. Plans are optional; implement does **not** require `data.plan`.

## Hard rule (Spec Kit specify vs plan)

- Do **not** put architecture, approach, or implementation steps in the scope contract.
- Do **not** treat the plan as a VERIFY source — contract VERIFY still gates DONE.
- Do **not** change GOAL / IN / OUT because the plan prefers a different HOW — change the contract first.
- Task checklists belong in `ref-p2-task-breakdown` (`tasks.md`), not this file.

---

## Step 0 — Resolve paths (`plan_paths`)

```bash
python3 scripts/plan_paths.py paths <project> <node_id> --json
```

| Field | Use |
|-------|-----|
| `plan_md` | Absolute path to write |
| `plan_rel` | Value for tree `data.plan` |
| `exists` | Whether a plan file already exists |
| `data_plan` | Current `data.plan` on the node (if any) |

Canonical artifact:

```text
<project-dir>/plans/<node-id>.plan.md
```

Tree link (relative to the project dir):

```text
data.plan: plans/<node-id>.plan.md
```

Stub (does not overwrite):

```bash
python3 scripts/plan_paths.py init <project> <node_id> --json
```

---

## Step 1 — Write HOW only

Fill (or replace the stub) using this structure. No GOAL restatement beyond one line pointing at the contract.

```markdown
# Technical Plan: <short title>

**Node:** `<node-id>`
**Contract:** `specs/<node-id>.md` (WHEN/WHY — source of truth for DONE)
**This file:** HOW only. Not a VERIFY source.

## Approach
<2–3 sentences — architecture / sequencing, not requirements>

## File map
- Create: `<path>`
- Modify: `<path>`
- Test: `<path>`

## Sequencing
1. <step that produces something testable>
2. …

## Risks
- <HOW risk that does not change VERIFY>
```

Keep it short. If a step would change IN / OUT / VERIFY, stop and update the contract instead.

---

## Step 2 — Link on the tree

Propose (user applies):

```json
{
  "project": "<project>",
  "target_node_id": "<node_id>",
  "operation": "set_data",
  "payload": { "plan": "plans/<node-id>.plan.md" }
}
```

CLI equivalent:

```bash
python3 scripts/project_tree.py propose <project> set-data <node_id> '{"plan":"plans/<node-id>.plan.md"}'
```

Do **not** edit `nodes.yaml` by hand.

---

## Step 3 — Handoff to implement

Tell the user to run **`/implement`**. When implementing:

- If `data.plan` is set, read that file for HOW (file map / order).
- Execute strictly against contract IN / OUT / MUST / VERIFY.
- Ignore plan steps that contradict the contract.

---

## Anti-patterns

- Putting HOW in the scope contract (approach, file lists as requirements, phased implementation)
- Requiring a plan before `/implement` (it is optional)
- Treating plan checkboxes as VERIFY
- Writing `tasks.md` here (separate node)
- Copying Spec Kit `research.md` / `data-model.md` / `contracts/` in v1

---

## Reference

Inspired by Spec Kit `templates/commands/plan.md` (lean: one `plan.md`, no Phase 0/1 sidecar docs) and Superpowers `writing-plans` (file map + sequencing). Full Spec Kit specify-dir layout is **`ref-sk-feature-dirs`**.
