---
name: systematic-debugging
description: Debug by forming and testing one hypothesis at a time instead of guessing — reproduce, isolate, hypothesize, test, fix, verify. Use when a VERIFY fails or behavior is wrong, and pair it with /understand for weak nodes that are weak because of a bug.
disable-model-invocation: true
---

# Systematic Debugging

Guessing is not debugging. Form one hypothesis, test it, and let evidence — not
intuition — drive the next move.

Announce: "Using systematic-debugging skill."

## The loop

1. **Reproduce** — get a reliable, minimal repro. If you can't reproduce it, you
   can't fix it.
2. **Isolate** — bisect the surface (input, layer, commit) until the failure is
   cornered.
3. **Hypothesize** — state one falsifiable cause: "if X, then changing Y flips
   the result."
4. **Test** — change exactly one thing and observe.
5. **Fix** — address the root cause, not the symptom.
6. **Verify** — re-run the failing VERIFY and confirm green (see
   `verification-before-completion`); add a regression test.

## Rules

- One hypothesis at a time. Revert changes that didn't help before trying the
  next.
- Never "fix" by masking a symptom (retry loops, broadened excepts, sleeps).
- When the bug explains a weak node, capture the finding as `data.pain` on that
  node so the tree remembers.
