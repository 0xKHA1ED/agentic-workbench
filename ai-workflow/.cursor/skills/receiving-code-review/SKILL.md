---
name: receiving-code-review
description: Turn review findings into adjudicated action — accept, push back with reason, or defer as a tracked item — never silently dismiss. Use when review comes back, before finishing a development branch.
disable-model-invocation: true
---

# Receiving Code Review

Every finding gets a **decision**. Silence is not a valid response to a review
comment.

Announce: "Using receiving-code-review skill."

## Adjudicate each finding

- **Accept** — fix it now; re-run VERIFY after the fix.
- **Push back** — disagree with a stated reason the reviewer can weigh.
- **Defer** — legitimate but out of this node's scope → capture as a new claim,
  task, or `data.pain` on the relevant node so it is not lost.

## Rules

- No finding is dropped without a recorded decision.
- A fix is not done until its VERIFY is green again.
- Deferrals become tracked work, never a quiet "won't do".
- Don't take it personally; the review is about the code, not you.

Once findings are adjudicated and VERIFY is green, proceed to
`finishing-a-development-branch`.
