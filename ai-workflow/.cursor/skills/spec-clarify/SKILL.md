---
name: spec-clarify
description: Requirements clarification before claims — Spec Kit–inspired taxonomy, ≤5 one-at-a-time questions, MC+Recommended, persist clarifications.md + decisions JSON. Gate before workflow_stage_contract_claims. Use after /understand when needs_clarify or requirements are fuzzy.
disable-model-invocation: true
---

# Spec Clarify

Resolve **requirements ambiguity** for a tree node **before** falsifiable claims are staged. Clarify answers *what must be true for DONE* — not architecture (see brainstorming) and not claim triage (see spec-discovery).

Announce: "Using spec-clarify skill."

## When to use

After **Understand** (pain + hypothesis on node), **before** `workflow_stage_contract_claims`, when:

- `data.needs_clarify` is true on the node, or
- GOAL / OUT / MUST would need more than two scope-contract questions, or
- Multiple reasonable interpretations would produce different VERIFY strategies.

**Skip** for bounded, small nodes — warn that rework risk increases (user may say `skip` → `workflow_clarify_complete` with `status: skipped`).

## Hard gate (Superpowers-inspired)

Do **not** call `workflow_stage_contract_claims` until:

- `workflow_clarify_complete` with `status: complete`, or
- user explicitly skips (`status: skipped`).

MCP enforces this when `needs_clarify` is true or a session is `in_progress`.

---

## Step 0 — Context (`workflow_clarify_context`)

```json
{ "project": "<project>", "node_id": "<node_id>" }
```

Use returned:

| Field | Use |
|-------|-----|
| `pain`, `pattern` | Investigation context |
| `taxonomy_mode` | `full` (product) vs `tooling` (scripts/skills/viewer) |
| `constitution_excerpt` | MUST principles — do not contradict. Also available via `workflow_get_constitution`. |
| `session` | Prior Q→A; do not repeat |
| `paths` | Where artifacts are written |

CLI equivalent:

```bash
python3 scripts/spec_clarify.py paths meta <node_id> --json
```

---

## Step 1 — Taxonomy scan (internal)

Mark each category **Clear / Partial / Missing**. **Do not dump the full map** unless zero questions will be asked.

### Full taxonomy (product / host `projects/*`)

Functional scope & behavior; domain & data model; interaction & UX; NFRs (performance, security, observability, compliance); integrations; edge cases & failure handling; constraints & tradeoffs; terminology; completion signals; placeholders/TODOs.

### Tooling taxonomy (`meta`, `scripts/**`, `.cursor/**`, `tools/**`)

Scope & OUT; VERIFY strategy; Cockpit/CLI UX; compatibility (MCP, existing skills); edge cases; terminology.

Pick mode from `workflow_clarify_context.taxonomy_mode` unless user overrides via tree `data.clarify_taxonomy`.

---

## Step 2 — Question queue (max 5)

- Prioritize **Impact × Uncertainty**; balance categories.
- **Maximum 5 questions** for the session.
- **One question at a time** in chat.
- Each question: full interrogative ending in `?`, then **Why it matters**, then:
  - **Recommended:** Option X — reasoning
  - MC table (2–5 options) or short answer (≤5 words)
  - User may reply `yes` / `recommended` to accept recommendation.

Skip plan-level-only detail unless it blocks correctness.

---

## Step 3 — Record each answer (`workflow_clarify_record`)

After user accepts an answer:

```json
{
  "project": "<project>",
  "node_id": "<node_id>",
  "question": "<exact question>",
  "answer": "<final answer>",
  "category": "<taxonomy category slug>"
}
```

Persists:

- `<project-dir>/clarifications/<node-id>.md` — session bullets
- `<project-dir>/clarifications/<node-id>.decisions.json` — structured decisions

**Do not** stage claims in the same turn as recording an answer.

---

## Step 4 — Completion block (B+)

When queue is exhausted or user says **done**, call:

```json
{
  "project": "<project>",
  "node_id": "<node_id>",
  "deferred_categories": ["observability"],
  "outstanding_categories": [],
  "status": "complete"
}
```

Or skip:

```json
{ "project": "<project>", "node_id": "<node_id>", "status": "skipped" }
```

Present **Deferred** / **Outstanding** lists and ask: **Proceed to spec-discovery anyway?**

Propose clearing the flag on the node (user approves diff):

```json
{
  "project": "<project>",
  "target_node_id": "<node_id>",
  "operation": "set_data",
  "payload": { "needs_clarify": false, "clarify": "complete" }
}
```

---

## Step 5 — Handoff to spec-discovery

Tell the user to run **spec-discovery**. When staging claims:

- Read `decisions_json`; encode decisions into GOAL, IN, OUT, and claims — **do not re-ask** settled questions.
- spec-discovery Step 1: **≤2 questions** only for VERIFY gaps not covered by clarify.

---

## Anti-patterns

- Staging claims before `workflow_clarify_complete`
- Batch multiple clarify questions in one message (escape hatch: user insists → max 3, warn)
- Architecture brainstorm in clarify (reparent to `/brainstorm` or Understand)
- Editing `nodes.yaml` or clarify files by hand (use MCP record/complete)
- Marking `[x]` on requirements checklists (that is `/requirements-checklist` — reviewer-only)

---

## Reference

Inspired by Spec Kit `templates/commands/clarify.md` (B+ profile). Requirements checklist files are `/requirements-checklist`. Cockpit Q&A UI is **`ref-cockpit-clarify-ui`**, not required for this skill.
