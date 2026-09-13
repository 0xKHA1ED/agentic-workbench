---
name: project-tree
description: Maintain project trees via scripts/project_tree.py only. Use for any project with projects/<name>/nodes.yaml — show tree, propose mutations (diff), apply/reject after user approval. Never edit nodes.yaml directly.
disable-model-invocation: true
---

# Project Tree (programmatic)

**AI authors the tree. CLI persists it. User approves.**

The tree is a **work map** (concerns, pain, status) — not a filesystem mirror. At 500k LOC, keep it coarse (30–200 nodes). Leaves use `data.pattern` as drill-down pointers.

**AI must never edit `nodes.yaml` or `nodes.yaml.proposed` directly.** All mutations go through the CLI.

Announce: "Using project-tree skill."

Run from repo root:

```bash
python scripts/project_tree.py <command> <project> [args]
```

Install once: `pip install -r requirements.txt`

## Who does what

| Role | Responsibility |
|------|----------------|
| **AI** | Read docs/code; infer concerns; propose structure; batch ops; attach `data.pattern` / `data.pain` |
| **CLI** | Diff, persist, status, validate patterns — never decide semantics |
| **User** | Approve diffs; promote `weak` → `strong`; pick today's work |

**Never** rebuild the whole tree. **Never** auto-apply. **Never** set `strong` for the user.

### Bootstrap (new project)

1. Read README / ARCHITECTURE / user intent
2. Propose **2–3 levels**, ~20–40 nodes max — concerns, not every file
3. One `batch` diff → user y/n
4. Drill down **only** when user picks a weak branch

### Scripts are lint, not authors

```bash
python scripts/project_tree.py validate-patterns <project>
python scripts/project_tree.py validate-patterns <project> --strict
```

Use after moves/renames in codebase — fix `data.pattern` via `set-data`, not by regenning the tree.

## Commands

| Command | Purpose |
|---------|---------|
| `show <project>` | ASCII tree + pending warning |
| `validate-patterns <project>` | Check `data.pattern` paths resolve |
| `propose <project> <op> [args]` | Compute change, write `.proposed`, print **diff** |
| `pending <project>` | Re-show diff |
| `apply <project>` | **Only after user approves** |
| `reject <project>` | Discard pending proposal |

## Status model

**Default: everything is `weak`.** Only the user promotes nodes to `strong`.

| Status | Who sets it | Meaning |
|--------|-------------|---------|
| `weak` | default on new nodes | Not hardened — fair game for today's work |
| `strong` | **user only** | User trusts this area; skip unless revisiting |
| `spec_ready` | workflow | Claims/spec drafted |
| `spec_approved` | workflow | Scope contract approved |
| `done` | workflow | VERIFY passed after implementation |

Never set `strong` for the user. Pick work from `weak` nodes.

## Dynamic tree (nodes enter, die, move)

| Situation | Op | Example |
|-----------|-----|---------|
| New concern | `add-group` / `add-child` | batch with siblings |
| Area obsolete | `mark-stale` | `mark-stale old-api superseded by v2` |
| Area revived | `clear-stale` | after refactor completes |
| Wrong grouping | `reparent` | `reparent validation-layer formats` |
| Rename label | `rename` | `rename fmt-leap "The leap (distance)"` |
| Code moved | `set-data` | update `pattern` only — keep node id |
| User trusts area | `set-status` | `set-status validation-layer strong` |

**Prefer surgical patches over full re-seed.** Preserve `strong` nodes across changes.

### mark-stale vs delete

No delete op yet — `mark-stale` keeps history. Stale nodes stay visible in viewer (amber). User can `clear-stale` when area returns.

## Multi-aspect messages

**Memory = `nodes.yaml`, not chat.** After each approved apply, facts live in the tree.

When user mentions **multiple things in one message**:
1. Parse all intents (constraints + new nodes + status changes…)
2. Ask **only** if ambiguous — not one question per fact
3. Build **one batch** → **one diff** → **one approve**

```bash
python scripts/project_tree.py propose my-feature batch --json '{
  "summary": "Add auth module + API constraints",
  "ops": [
    {"op": "add-group", "args": ["root", "auth", "Authentication"]},
    {"op": "set-constraint", "args": ["must_use", "existing-jwt-middleware"]},
    {"op": "add-child", "args": ["auth", "login-endpoint", "POST /login", "work"]}
  ]
}'
```

Or `--file projects/<name>/batch.json`. **Do not** run five separate proposes for five facts.

## Propose operations

| Operation | Args | Example |
|-----------|------|---------|
| `batch` | `--json` or `--file` | Multi-op atomic proposal |
| `set-constraint` | key val [val...] | `set-constraint codebase sandbox/tik` |
| `add-group` | parent_id id title | `add-group root payments Payments` |
| `add-child` | parent id title [kind] [status] | `add-child payments retry Retry handler work` |
| `set-data` | node_id '{"k":"v"}'` | `set-data auth '{"pattern":"src/auth/**"}'` |
| `set-status` | node_id status | `set-status retry spec_ready` |
| `set-all-weak` | [preserve...] | all → weak except `strong` |
| `mark-stale` | node_id [notes] | `mark-stale old-approach superseded` |
| `clear-stale` | node_id | `clear-stale old-approach` |
| `rename` | node_id title | `rename fmt-leap The leap` |
| `reparent` | node_id new_parent_id | `reparent validation-layer formats` |

## Workflow (mandatory)

1. `show` or tree viewer — orient
2. Discuss — structure from user + codebase; names/requirements from user unless asked
3. **`propose ... --no-prompt`** — AI runs diff only
4. User runs propose in terminal (interactive y/n) or `apply`/`reject`
5. Never `apply`/`reject` for the user

```bash
# User (interactive y/n):
python scripts/project_tree.py propose my-feature batch --file projects/my-feature/batch.json

# AI (diff only):
python scripts/project_tree.py propose my-feature batch --file ... --no-prompt
```

If proposal pending and user wants changes: `reject` first, then new `propose`.

## Conversation

- Pick node from tree; don't re-ask facts in `data` / constraints
- `work` nodes → `/spec-discovery` → `projects/<name>/specs/<id>.md` → `set-status spec_approved`

## Adding new operations

Extend `scripts/project_tree/ops.py` + `cli.py` — do not edit yaml by hand.
