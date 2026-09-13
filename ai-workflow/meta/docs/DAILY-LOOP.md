# Daily loop

The compounding pipeline we're building tooling for.

```
Open Cursor
    → Orient     (what to work on? — tree + viewer + weak nodes)
    → Understand (why is this weak? — investigate, pain on node)
    → Spec       (what proves done? — discovery + contract)
    → Implement  (agent executes VERIFY)
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
| Tree change | `propose` → terminal y/n |
| Claim triage | `spec_discovery review` → y/n/s per claim |
| Spec approve | scope-contract REVIEW or assembled spec |
| Promote trust | `set-status <id> strong` — user only |
