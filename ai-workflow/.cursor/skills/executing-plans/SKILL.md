---
name: executing-plans
description: Execute an approved plan one checkbox at a time, verifying each step before checking it off and never batching completions. Use after writing-plans to drive a multi-step change to done with evidence at every step.
disable-model-invocation: true
---

# Executing Plans

Drive a plan to done **one checkbox at a time**. Check a box only after you have
observed its VERIFY pass.

Announce: "Using executing-plans skill."

## Protocol

1. Take the next unchecked step.
2. Do exactly that step — no more.
3. Run its VERIFY. Observe the result yourself.
4. Only then check the box. Never batch-check multiple steps.
5. If a step reveals new work, append it to the plan (never silently expand a
   step's scope).

## Rules

- One in-progress step at a time.
- A failed VERIFY means the box stays unchecked — diagnose, don't move on.
- If reality diverges from the plan, STOP and update the plan before continuing.
- Finishing the plan is not finishing the work: run the node's full VERIFY (see
  `verification-before-completion`).
