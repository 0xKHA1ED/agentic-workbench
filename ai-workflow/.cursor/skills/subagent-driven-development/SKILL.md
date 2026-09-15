---
name: subagent-driven-development
description: Decompose implement work into independent tasks, dispatch one subagent per task with a crisp brief, and review each result before integrating. Use on full-path work with parallelizable tasks that each have a self-contained contract and VERIFY.
disable-model-invocation: true
---

# Subagent-Driven Development

Split implement into **independent tasks**, give each to a subagent with a
self-contained brief, and **review every result** before it lands.

Announce: "Using subagent-driven-development skill."

## When it fits

- Tasks are independent (no shared in-flight state).
- Each task has its own contract + VERIFY the subagent can run.
- The integrating session reviews and adjudicates every returned change.

## Brief template (per subagent)

```
GOAL: <one sentence>
CONTEXT: <files, constraints>
DONE WHEN: <VERIFY command that must pass>
OUT OF SCOPE: <what not to touch>
RETURN: <what to report back>
```

## Rules

- One task = one brief = one VERIFY. Never hand a subagent a fuzzy goal.
- The integrator runs `requesting-code-review` on each result — subagent output
  is trusted but **verified**, never auto-merged.
- Conflicts are resolved by the integrator, not the subagents.
