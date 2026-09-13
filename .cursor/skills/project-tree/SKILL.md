---
name: project-tree
description: Maintain project trees via scripts/project_tree.py only. Use for any project with projects/<name>/nodes.yaml — show tree, propose mutations (diff), apply/reject after user approval. Never edit nodes.yaml directly.
disable-model-invocation: true
---

# Project Tree (programmatic)

**AI must never edit `nodes.yaml` or `nodes.yaml.proposed` directly.** All mutations go through the CLI.

Announce: "Using project-tree skill."

Run from repo root:

```bash
python scripts/project_tree.py <command> <project> [args]
```

Install once: `pip install -r requirements.txt`

## Commands

| Command | Purpose |
|---------|---------|
| `show <project>` | ASCII tree + pending warning |
| `propose <project> <op> [args]` | Compute change, write `.proposed`, print **diff**, wait for user |
| `pending <project>` | Re-show diff if user asks |
| `apply <project>` | **Only after user says approve** |
| `reject <project>` | **Only after user says reject** |

## Multi-aspect messages (long discussions)

**Memory = `nodes.yaml`, not chat.** After each approved apply, facts live in the tree. Month-later sessions: `show` first, then continue.

When user mentions **multiple things in one message**:
1. Parse all intents (constraints + new nodes + status changes…)
2. Ask **only** if something is ambiguous or contradictory — not one question per fact
3. Build **one batch** → **one diff** → **one approve**
4. If some items are unclear, propose the clear subset + ask about the rest in ≤2 questions

```bash
python scripts/project_tree.py propose my-feature batch --json '{
  "summary": "Add auth module + API constraints",
  "ops": [
    {"op": "add-group", "args": ["root", "auth", "Authentication"]},
    {"op": "set-constraint", "args": ["must_use", "existing-jwt-middleware"]},
    {"op": "add-child", "args": ["auth", "login-endpoint", "POST /login", "work", "empty"]}
  ]
}'
```

Or write ops to `projects/<name>/batch.json` and use `--file`.

**Do not** run five separate proposes for five facts in one message — batch them.

Across **many sessions**: each approve commits state; never rely on chat history for facts already in tree.

## Propose operations

| Operation | Args | Example |
|-----------|------|---------|
| `batch` | `--json` or `--file` | Multi-op atomic proposal (see above) |
| `set-constraint` | key val [val...] | `propose my-feature set-constraint layer domain-only` |
| `add-group` | parent_id id title | `propose my-feature add-group root payments Payments` |
| `add-child` | parent id title [kind] [status] | `propose my-feature add-child payments retry-handler Retry handler work empty` |
| `set-data` | node_id '{"k":"v"}'` | `propose my-feature set-data auth '{"pattern":"src/auth/middleware.ts"}'` |
| `set-status` | node_id status | `propose my-feature set-status retry-handler spec_ready` |
| `mark-stale` | node_id [notes] | `propose my-feature mark-stale old-approach superseded` |

Add domain-specific composite ops in `ops.py` when a pattern repeats.

## Workflow (mandatory)

1. `show` — orient user
2. Discuss — gather **criteria and structure**, not AI-generated content (requirements, feature names, etc. come from user unless asked)
3. **`propose`** — run CLI; script shows diff then **`Apply this proposal? [y/n]`** in terminal
4. **AI uses `--no-prompt`** — never `apply`/`reject` for the user; tell them to run propose in terminal or run `apply`/`reject` themselves
5. User types **y** or **n** in terminal (or runs apply/reject manually)
6. Never edit yaml directly; never invent user-owned content (ideas, names, requirements) without explicit ask

```bash
# User runs in terminal (interactive y/n):
python scripts/project_tree.py propose my-feature batch --file projects/my-feature/batch.json

# AI runs (diff only, leaves pending):
python scripts/project_tree.py propose my-feature batch --file ... --no-prompt
```

If proposal pending and user wants changes, `reject` first then new `propose`.

## Conversation

- Pick node from `show` output; don't re-ask facts already in tree/constraints
- `work` nodes ready for specs → `/scope-contract`, save to `projects/<name>/specs/<id>.md`, then `propose set-status <id> spec_approved` (with spec path via `set-data` if needed)

## Adding new operations

If no CLI op fits, extend `scripts/project_tree/ops.py` + `cli.py` — do not edit yaml by hand.
