---
name: finishing-a-development-branch
description: Close out a branch cleanly — VERIFY green, review adjudicated, squash/merge or PR, then delete the branch and remove its worktree. Use as the last step of implement once a node's work is verified and reviewed.
disable-model-invocation: true
---

# Finishing a Development Branch

Land the work and leave no litter. A branch is finished only when its work is
verified, reviewed, merged, and cleaned up.

Announce: "Using finishing-a-development-branch skill."

## Checklist

- [ ] Node VERIFY is green (fresh evidence).
- [ ] Review findings adjudicated (`receiving-code-review`).
- [ ] Commit message states the node and what changed.
- [ ] Merge or open a PR per the repo's convention.
- [ ] Delete the merged branch.
- [ ] Remove the node's worktree (`git worktree remove`).
- [ ] The node is ready for the human `promote → strong` gate.

## Rules

- Never merge on red or with unadjudicated findings.
- Don't force-push shared branches or bypass hooks to "just land it".
- Promotion to `strong` is a separate, deliberate human act — finishing the
  branch does not auto-promote.
