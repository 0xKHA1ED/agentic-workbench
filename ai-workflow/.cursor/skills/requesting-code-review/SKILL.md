---
name: requesting-code-review
description: After implement, request a focused review by handing the reviewer the contract, the diff, and the VERIFY evidence — and asking for specific findings, not a rubber stamp. Use before finishing a development branch on bounded and full paths.
disable-model-invocation: true
---

# Requesting Code Review

A review request is a **package**, not a "please look." Give the reviewer
everything they need to find real problems fast.

Announce: "Using requesting-code-review skill."

## The request package

1. **Contract** — the node's GOAL / IN / OUT / VERIFY.
2. **Diff** — the change under review, scoped to this node.
3. **VERIFY evidence** — the command and its passing exit code.
4. **Ask** — specific questions ("is the traversal check correct?"), not "LGTM?".

## Rules

- Never request review on red. VERIFY passes *before* review (see
  `verification-before-completion`).
- Scope the diff to one node; unrelated changes get their own review.
- Invite falsification: ask the reviewer to try to break it.

Findings come back through `receiving-code-review`.
