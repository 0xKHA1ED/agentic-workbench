---
name: using-git-worktrees
description: Isolate each node's implement work in its own git worktree so parallel work never collides on one working tree. Use when implementing multiple nodes at once or keeping an experiment isolated from the main checkout.
disable-model-invocation: true
---

# Using Git Worktrees

One node, one worktree. A worktree gives each line of work its own directory and
branch without re-cloning.

Announce: "Using using-git-worktrees skill."

## Core commands

```bash
git worktree add ../wt-<node> -b feat/<node>   # new branch in a sibling dir
git worktree list                               # see all worktrees
git worktree remove ../wt-<node>                # clean up when merged
```

## Rules

- Name the worktree and branch after the node being implemented.
- Never run two implements in the same working tree; use separate worktrees.
- Prune merged worktrees promptly (`git worktree remove`) — stale worktrees
  cause confusing "already checked out" errors.
- Shared caches (e.g. `.next`, `__pycache__`) can collide across worktrees; keep
  build output per-worktree.

Pairs with `subagent-driven-development` (one worktree per subagent) and
`finishing-a-development-branch` (merge + remove worktree).
