---
name: task-breakdown
description: Generate phased Spec Kit–style tasks.md from claims/spec, then scope /implement by phase markers or T00N ranges. Use after an assembled contract (or claims JSON) and before or during /implement on large nodes.
disable-model-invocation: true
---

# Task Breakdown

Turn approved **claims** and/or an assembled **scope contract** into a dependency-ordered `tasks.md` so `/implement` can run one phase (or a task range) at a time.

Announce: "Using task-breakdown skill."

## When to use

After spec-discovery / assemble, **before** or **during** `/implement`, when the node is too large to execute as a single VERIFY walk.

**Skip** for tiny nodes — `/implement` still runs from the contract alone if `tasks/<node-id>.md` is absent.

## Artifacts

Writes:

```text
<project-dir>/tasks/<node-id>.md
```

Reads (either is enough):

| Input | Path |
|-------|------|
| Claims JSON | `<project-dir>/claims/<node-id>.json` |
| Assembled spec | `<project-dir>/specs/<node-id>.md` |

Missing **both** → abort, write nothing, tell the user to assemble or add claims.

Does **not** require `plan.md` (that is `ref-p2-technical-plan`).

---

## Step 0 — Paths (`workflow_tasks_paths`)

```json
{ "project": "<project>", "node_id": "<node_id>" }
```

CLI:

```bash
python3 scripts/task_breakdown.py paths <project> <node_id> --json
```

---

## Step 1 — Generate

```bash
python3 scripts/task_breakdown.py generate <project> <node_id> --json
```

Generated file uses Spec Kit phases plus machine markers:

1. **Setup** — `<!-- task-phase: id=setup index=1 -->`
2. **Foundational** — blocking MUST claims (`id=foundational`)
3. **One phase per approved `verify` claim** — `id=<claim-id>` (e.g. `c1`), story label `[C1]`
4. **Polish** — MUST NOT + close-out (`id=polish`)

Checklist format (required):

```text
- [ ] T001 Description with file path
- [ ] T005 [P] Parallelizable task in path/to/file.py
- [ ] T012 [P] [C1] Story task in path/to/file.py
```

---

## Step 2 — Scope for implement

```bash
python3 scripts/task_breakdown.py scope <project> <node_id> --phase 2 --json
python3 scripts/task_breakdown.py scope <project> <node_id> --phase setup --json
python3 scripts/task_breakdown.py scope <project> <node_id> --tasks T001-T004 --json
```

Hand the scoped task list to `/implement`. Contract **IN / OUT / MUST / MUST NOT** still win over a task path.

---

## Step 3 — Handoff

Tell the user they can:

- `/implement` the full node (all incomplete tasks, phase by phase), or
- `/implement phase 2` / `/implement T001-T004` for a scoped run

Mark completed checkboxes `[x]` in `tasks.md` as work finishes.

## Anti-patterns

- Generating without claims or spec (silent empty file)
- Implementing later phases before Foundational is complete
- Ignoring IN/OUT because a task mentioned an out-of-scope path
- Regenerating `tasks.md` to wipe `[x]` progress without saying so (generate overwrites)

## Reference

Inspired by Spec Kit `templates/commands/tasks.md` and scoped `/speckit.implement`. Superpowers-style “T1–T4 only” execution is the implement-skill half of this node.
