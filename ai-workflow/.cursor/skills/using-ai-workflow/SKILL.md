---
name: using-ai-workflow
description: Route a request onto the daily loop before acting — classify it as spike / bounded / full, announce the path, turn optional phases on or off by policy, and enforce the approval HARD-GATE. Use at the very start of any work session, before orient/clarify/spec/implement, so small work skips optional ceremony without ever skipping human approval.
disable-model-invocation: true
---

# Using AI Workflow (path router)

**Route before acting.** Before touching orient / clarify / spec / analyze /
implement, classify the request onto one of three paths and announce it. The
path decides *which optional phases run* — it never removes a human gate.

Announce: "Using using-ai-workflow skill — path: <spike|bounded|full>."

## The three paths (one-way ratchet)

| Path | When | Feels like |
|------|------|-----------|
| **spike** | throwaway probe, question, or <~15-line fix; reversible; no new contract needed | "let me just check / try one thing" |
| **bounded** | one node, one clear change, known blast radius | "I know what DONE means; go" |
| **full** | new product area, fuzzy requirements, multi-node or architectural change | "we need to think before we build" |

**One-way ratchet:** you may only escalate mid-flight (spike → bounded → full),
never quietly downgrade. If a spike uncovers real scope, STOP and re-announce as
bounded or full. When in doubt, pick the **heavier** path.

## Path → phase policy

`data.path` on the node records the choice. `✓` = run, `—` = skipped **by policy**
(not by neglect), `GATE` = mandatory human gate that never scales away.

| Phase | spike | bounded | full |
|-------|:-----:|:-------:|:----:|
| Orient | ✓ | ✓ | ✓ |
| Understand (pain) | ✓ | ✓ | ✓ |
| Clarify | — | — | ✓ |
| Spec / contract | — | ✓ | ✓ |
| **Approval** | **GATE** | **GATE** | **GATE** |
| Analyze | — | ✓ / skip | ✓ |
| Checklist | — | — | ✓ (if custom items) |
| Plan | — | — | optional |
| Tasks | — | — | ✓ (if multi-phase) |
| Implement | ✓ | ✓ | ✓ |
| VERIFY-before-done | ✓ | ✓ | ✓ |
| Promote → strong | GATE | GATE | GATE |

## The approval HARD-GATE (non-negotiable)

The approval gate **never** scales away with the path:

- **spike:** still state intent in one line and get a nod before writing code.
- **bounded:** still present a short design / the DONE criteria and **STOP for a yes**.
- **full:** clarify + spec + analyze, then STOP for explicit spec approval.

Skipping *optional* phases (Clarify/Checklist/Plan/Tasks/Analyze) is allowed on
lighter paths. Skipping *approval* is never allowed. Promotion to `strong` is
always a separate, deliberate human act — never a side effect of finishing work.

## VERIFY-before-done (applies to every path)

No path is "done" without a fresh, passing VERIFY (see
`verification-before-completion`). A spike that becomes real work inherits the
full VERIFY discipline of its escalated path.

## Cross-references

- `brainstorming` — deeper spike/bounded/architectural exploration + HARD-GATE.
- `verification-before-completion` — the Iron Law that gates every "done".
- `test-driven-development`, `using-git-worktrees`, `requesting-code-review` —
  process skills the `full` path pulls in during implement.
