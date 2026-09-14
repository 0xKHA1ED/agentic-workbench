# Daily loop

The compounding pipeline we're building tooling for.

```
Open Cursor
    → Assess     (optional — go/kill new ideas before tree nodes; /idea-assess)
    → Orient     (what to work on? — tree + viewer + weak nodes)
    → Understand (why is this weak? — investigate, pain on node)
    → Clarify    (optional — requirements Q&A before claims; /spec-clarify)
    → Spec       (what proves done? — discovery + contract — WHEN/WHY)
    → Analyze    (read-only claims/contract gate; /spec-analyze or skip)
    → Checklist  (optional — unit tests for requirements; /requirements-checklist)
    → Plan       (optional — HOW; /technical-plan — not a VERIFY source)
    → Tasks      (optional — /task-breakdown → tasks/<node>.md; scoped /implement)
    → Implement  (agent executes VERIFY; may scope to a task phase)
    → Strong     (user promotes when trusted)
```

## Principles

1. **Early steps compound** — good orient/spec makes implement trivial
2. **Tree is memory, not chat** — `nodes.yaml` + fragments persist across sessions
3. **Default weak** — everything unexplored until user promotes to `strong`
4. **AI authors, CLI persists** — propose → diff → y/n
5. **Done = falsifiable VERIFY** — scope-contract + spec-discovery

## Gates (human-in-the-loop)

| Step | Gate |
|------|------|
| Idea assess | `decision.md` go/kill; go → project-tree attach or `/spec-clarify` |
| Tree change | `propose` → terminal y/n |
| Clarify complete | `workflow_clarify_complete` or skip; blocks claims if `needs_clarify` |
| Claim triage | `spec_discovery review` → y/n/s per claim |
| Spec approve | scope-contract REVIEW or assembled spec |
| Analyze complete | `workflow_analyze_complete` or skip; blocks `/implement` if missing/`in_progress`; CRITICAL does not hard-block after complete/skip |
| Requirements checklist | User marks `[x]` on `checklists/<node>/`; `workflow_checklist_status` is read-only; unchecked custom items block `/implement` |
| Technical plan | optional; `data.plan` → `plans/<node-id>.plan.md`; not a VERIFY gate |
| Task breakdown | optional; `tasks/<node-id>.md`; `/implement` may scope to a phase |
| Promote trust | `set-status <id> strong` — user only |
