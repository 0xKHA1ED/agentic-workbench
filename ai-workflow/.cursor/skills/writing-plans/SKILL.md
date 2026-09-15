---
name: writing-plans
description: Turn an approved design into a concrete, checkbox-structured implementation plan artifact before executing. Use on full-path work so a multi-step change has an ordered, reviewable plan that another session (or subagent) can execute.
disable-model-invocation: true
---

# Writing Plans

A plan is an **executable artifact**, not prose. It is an ordered list of
checkboxes small enough that each is unambiguous and verifiable.

Announce: "Using writing-plans skill."

## Structure

```
# Plan: <node / feature>
## Goal
<one sentence>
## Steps
- [ ] 1. <action> — VERIFY: <how you'll know it worked>
- [ ] 2. <action> — VERIFY: <...>
## Risks
- <risk> → <mitigation>
```

## Rules

- Every step names its own VERIFY. No step is "done" without evidence.
- Steps are ordered by dependency; a later step never blocks an earlier one.
- The plan is a HOW artifact — it is **not** a source of DONE criteria (that is
  the scope-contract's VERIFY).
- Keep steps small enough to check off in one sitting; split anything vague.

Hand the finished plan to `executing-plans`.
