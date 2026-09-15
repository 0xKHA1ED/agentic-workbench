---
name: verification-before-completion
description: The Iron Law — never claim a task done without running its VERIFY in this session and observing it pass. Use at the end of every implement, on every path, before saying "done" or promoting a node.
disable-model-invocation: true
---

# Verification Before Completion (Iron Law)

**No completion claim without fresh, first-hand evidence.**

Announce: "Using verification-before-completion skill."

## The Iron Law

> You may not report a task complete unless you personally ran its VERIFY in this
> session and watched it pass. A test you *believe* passes, a command you *think*
> succeeds, or work that "should" be correct does **not** count.

## Protocol

1. Identify the node's VERIFY command (`data.verify`).
2. Run it now. Read the exit code and the failure count.
3. If it fails: it is not done. Diagnose (see `systematic-debugging`).
4. If it passes: capture the evidence (command + exit 0) in the dogfood note.
5. Only then may you say "done" — and promotion to `strong` is still a separate
   human act.

## Applies to

Every path (spike, bounded, full), every implement, subagent results, and the
certification of a node to `strong`. There is no exception for "small" work.
