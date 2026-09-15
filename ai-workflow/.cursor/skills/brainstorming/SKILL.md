---
name: brainstorming
description: Explore a problem before committing to a build path — classify it as spike, bounded, or architectural, generate options, and STOP at a HARD-GATE for human approval before any implementation. Use when requirements are fuzzy, multiple designs compete, or the blast radius is unclear.
disable-model-invocation: true
---

# Brainstorming

Think before building. Brainstorming produces **options and a recommendation**,
then **stops** for a human decision — it never slides straight into code.

Announce: "Using brainstorming skill."

## Three exploration modes

- **spike** — a throwaway probe to answer one question. Time-boxed; the code is
  expected to be discarded.
- **bounded** — one design for one known change. Present the plan and DONE
  criteria, then stop.
- **architectural** — multiple designs with trade-offs across modules. Compare,
  recommend, and stop for a deliberate choice.

## The HARD-GATE (one-way ratchet)

After presenting options you **must STOP** and get explicit approval before
implementing. You may only ratchet *up* in rigor (spike → bounded →
architectural) as scope grows — never quietly downgrade. When uncertain, take
the heavier mode.

## Output shape

1. Problem restated in one sentence.
2. 2–4 options, each with a one-line trade-off.
3. A recommendation with rationale.
4. **STOP** — "Approve which option before I implement?"

Cross-reference `using-ai-workflow` (path routing) and `writing-plans` (turn the
approved option into an executable plan).
