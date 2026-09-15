---
name: converge
description: Post-implement gap hunt — re-read the scope-contract's ACCEPTANCE/VERIFY and append any unmet items to the node's tasks as new open work, never silently closing them. Use after implement (full path) to catch drift between what was promised and what was built.
disable-model-invocation: true
---

# Converge

After implement, hunt for the gap between the **contract** and reality, and turn
each gap into tracked work. Converge only ever *appends* — it never checks off or
deletes.

Announce: "Using converge skill."

## Run it

```bash
python3 scripts/converge.py <contract.md> --tasks <tasks.md>
```

It extracts ACCEPTANCE (then VERIFY) checkboxes from the contract, finds the
items not already present in the tasks file, and appends them under
`## Converge — unmet acceptance (append-only)` as new `- [ ]` tasks.

## Rules

- Append-only: a gap becomes a new open task; converge never closes work.
- Every appended gap is real (traceable to a contract acceptance item).
- Re-run after fixing gaps until converge reports zero — then walk VERIFY (see
  `verification-before-completion`).
- Converge findings are adjudicated by a human, like review findings.
