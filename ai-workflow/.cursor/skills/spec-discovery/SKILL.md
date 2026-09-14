---
name: spec-discovery
description: Discover specs via triage — AI stages falsifiable claims directly via workflow_stage_contract_claims MCP tool, user approves in Cockpit or terminal, assemble scope-contract. Use after picking a weak tree node and explaining pain.
disable-model-invocation: true
---

# Spec Discovery

Turn pain + investigation into an approved scope contract **without prose in chat**. AI stages **claims** via MCP; user triages in terminal or Cockpit; script assembles the spec.

Announce: "Using spec-discovery skill."

## When to use

After:
1. `workflow_orient` or `project-tree show <project>` — picked a **weak** node (or new child)
2. User explained **why it hurts** (capture in node `data.pain` via `workflow_propose_tree_mutation`)
3. Optional: decomposed into child nodes via project-tree batch

### 0 — Clarify gate (before claims)

If any of the following, run **`/spec-clarify`** first (see `.cursor/skills/spec-clarify/SKILL.md`):

- Node `data.needs_clarify` is true
- `workflow_get_node` → `clarify.status` is `in_progress`
- Requirements are ambiguous (would need >2 scope-contract questions)

Do **not** call `workflow_stage_contract_claims` until `workflow_clarify_complete` (`complete` or `skipped`).

When staging claims, read `<project>/clarifications/<node-id>.decisions.json` and **do not re-ask** recorded decisions.

## Workflow

### 1 — Investigate + discuss (chat)

- Fetch node details via `workflow_get_node` (pain, paths, existing contract) and read relevant codebase
- Ask **≤2 questions** only if VERIFY cannot be inferred
- Do **not** write scope-contract prose in chat

### 2 — Stage claims via MCP (`workflow_stage_contract_claims`)

**Agents invoke `workflow_stage_contract_claims` directly via MCP.** Do NOT require the user to copy-paste or manually write JSON files:

```json
{
  "project": "my-project",
  "node_id": "validation-layer",
  "goal": "One sentence observable outcome",
  "claims": [
    {
      "id": "c1",
      "kind": "verify",
      "text": "pytest services/inspection-certs/tests/test_validate.py::test_expired_root passes",
      "check_command": "pytest services/inspection-certs/tests/test_validate.py::test_expired_root",
      "source": "services/inspection-certs/validate/root.py:42",
      "examples": [{"case": "expired cert", "input": "cert with exp 2020-01-01", "expected": "ExpiredSignatureError"}]
    },
    {
      "id": "c2",
      "kind": "must",
      "text": "Raise ExpiredSignatureError with exact expiry timestamp in message"
    },
    {
      "id": "c3",
      "kind": "must_not",
      "text": "Silently swallow validation errors or accept unsigned certs"
    }
  ],
  "in_scope": ["boundary nouns"],
  "out_scope": ["explicit exclusions"]
}
```

**Claim kinds:** `verify` | `must` | `must_not`

**Rules (same as scope-contract):**
- Max **15 claims** per node; prioritize riskiest first
- Every `text` must be falsifiable — ban "handle gracefully", "robust", "properly"
- `goal` is required; shown once for y/n before claims
- Do **not** set `decision` fields — triage owns those

The tool automatically validates claims against vague language, saves to `<project-dir>/claims/<node-id>.json`, and notifies Cockpit.

Tell the user:
> Staged claims for `<node-id>`. Review in Cockpit or run:
> `python scripts/spec_discovery.py review projects/<project>/claims/<node-id>.json`

### 3 — User triages (terminal or Cockpit)

User runs `review` (or reviews in Cockpit) — **not the agent**. One claim at a time:

| Key | Action |
|-----|--------|
| y | approve |
| n | reject |
| s | skip (review later) |
| e | edit claim text inline |
| q | quit (progress saved) |

GOAL shown first for y/n. Vague claims warn before approve.

Check progress:

```bash
python scripts/spec_discovery.py status projects/<project>/claims/<node-id>.json
```

### 4 — Assemble scope contract

After all claims triaged (or enough approved):

```bash
python scripts/spec_discovery.py assemble projects/<project>/claims/<node-id>.json
```

Writes `projects/<project>/specs/<node-id>.md` (scope-contract format).

### 5 — Link to tree

Agent calls `workflow_propose_tree_mutation` directly via MCP:

```json
{
  "project": "<project>",
  "target_node_id": "<node-id>",
  "operation": "set_data",
  "payload": {
    "spec": "specs/<node-id>.md",
    "contract": "specs/<node-id>.md"
  }
}
```

Followed by:

```json
{
  "project": "<project>",
  "target_node_id": "<node-id>",
  "operation": "set_status",
  "payload": {
    "status": "spec_approved"
  }
}
```

User approves tree diff in terminal or Cockpit.

## Decomposition (split pain into nodes)

When pain spans multiple aspects, propose child nodes via **one** project-tree batch — not separate chats per fact.

Then run spec-discovery **per child node** (one claims file each).

## Anti-patterns

- Writing full scope-contract in chat instead of claims JSON
- More than 15 claims in one file — split into child nodes
- Running `review` or `assemble` for the user in agent session (non-interactive)
- Vague claims without concrete expected behavior
- Skipping GOAL approval

## Commands reference

| Command | Purpose |
|---------|---------|
| `validate <file>` | Check JSON schema |
| `review <file>` | Interactive triage |
| `review <file> --reset` | Re-triage from scratch |
| `status <file>` | Progress counts |
| `assemble <file>` | Build scope-contract .md |
| `assemble <file> -o path.md` | Custom output path |
