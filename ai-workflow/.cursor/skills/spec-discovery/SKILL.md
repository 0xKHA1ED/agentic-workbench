---
name: spec-discovery
description: Discover specs via triage — AI proposes falsifiable claims as JSON, user approves one at a time in terminal, assemble scope-contract. Use after picking a weak tree node and explaining pain. Manual-only — never auto-invoke.
disable-model-invocation: true
---

# Spec Discovery

Turn pain + investigation into an approved scope contract **without prose in chat**. AI proposes **claims**; user triages in terminal; script assembles the spec.

Announce: "Using spec-discovery skill."

Run from repo root:

```bash
python scripts/spec_discovery.py <command> ...
```

## When to use

After:
1. `project-tree show <project>` — picked a **weak** node (or new child)
2. User explained **why it hurts** (capture in node `data.pain` via project-tree)
3. Optional: decomposed into child nodes via project-tree batch

## Workflow

### 1 — Investigate + discuss (chat)

- Read node `data` (pain, paths) and relevant codebase
- Ask **≤2 questions** only if VERIFY cannot be inferred
- Do **not** write scope-contract prose in chat

### 2 — Write claims JSON (AI)

Save to `<project-dir>/claims/<node-id>.json` (e.g. `meta/claims/`, or `projects/<name>/claims/` in host repo):

```json
{
  "project": "my-project",
  "node": "validation-layer",
  "title": "Short title",
  "goal": "One sentence observable outcome",
  "in": ["boundary nouns"],
  "out": ["explicit exclusions"],
  "claims": [
    {
      "id": "c1",
      "kind": "verify",
      "text": "Falsifiable statement — command or observable behavior",
      "source": "path/to/file.py:42",
      "rationale": "optional one line",
      "examples": [{"case": "edge", "input": "...", "expected": "..."}]
    }
  ]
}
```

**Claim kinds:** `verify` | `must` | `must_not`

**Rules (same as scope-contract):**
- Max **15 claims** per file; prioritize riskiest first
- Every `text` must be falsifiable — ban "handle gracefully", "robust", "properly"
- `goal` is required; shown once for y/n before claims
- Do **not** set `decision` fields — triage script owns those

Validate before handing off:

```bash
python scripts/spec_discovery.py validate projects/<project>/claims/<node-id>.json
```

Tell user:

```bash
python scripts/spec_discovery.py review projects/<project>/claims/<node-id>.json
```

### 3 — User triages (terminal)

User runs `review` — **not the agent**. One claim at a time:

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

```bash
python scripts/project_tree.py propose <project> set-data <node-id> '{"spec":"specs/<node-id>.md","pain":"..."}' --no-prompt
python scripts/project_tree.py propose <project> set-status <node-id> spec_approved --no-prompt
```

User approves tree diff in terminal.

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
