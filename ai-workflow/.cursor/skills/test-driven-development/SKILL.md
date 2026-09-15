---
name: test-driven-development
description: Write a failing test first, watch it fail (red), make it pass (green), then refactor — before walking the VERIFY checklist. Use during implement on bounded and full paths so behavior is pinned by an executable test before the code exists.
disable-model-invocation: true
---

# Test-Driven Development

Red → Green → Refactor, then VERIFY. A test that has never failed proves nothing.

Announce: "Using test-driven-development skill."

## The loop

1. **Red** — write the smallest test that expresses the next behavior. Run it.
   Confirm it fails *for the right reason* (missing behavior, not a typo).
2. **Green** — write the minimum code to pass. Run the test. Confirm it passes.
3. **Refactor** — clean up with the test as a safety net. Re-run.

## Rules

- Never write implementation before a failing test on bounded/full paths.
- One behavior per test; name it after the behavior, not the function.
- A green run you did not personally observe does not count (see
  `verification-before-completion`).
- The node's VERIFY command is the outer loop; TDD is the inner loop that gets
  you there.

In this repo tests are stdlib `unittest` (no pytest). Run from `ai-workflow/`:
`PYTHONPATH=scripts python3 -m unittest tests.<module>`.
