---
name: project-tree
description: Maintain project trees via scripts/project_tree.py only. Projects live in meta/, examples/*, or host projects/<name>/ — show tree, propose mutations (diff), apply/reject after user approval. Never edit nodes.yaml directly.
disable-model-invocation: true
---

# Project Tree (programmatic)

**AI authors the tree. CLI persists it. User approves.**

The tree is a **work map** (concerns, pain, status) — not a filesystem mirror. At 500k LOC, use **thin root + fragment files per product**.

**AI must never edit `nodes.yaml`, `fragments/*.yaml`, or `*.proposed` directly.** All mutations go through the CLI.

Announce: "Using project-tree skill."

Run from **`ai-workflow/`** package root (or `ai-workflow/scripts/` from host repo):

```bash
python scripts/project_tree.py <command> <project> [args]
```

Install once: `pip install -r requirements.txt`

## Who does what

| Role | Responsibility |
|------|----------------|
| **AI** | Read docs/code; infer concerns; propose structure; batch ops; attach `data.pattern` / `data.pain` |
| **CLI** | Diff, persist, compose fragments, validate patterns — never decide semantics |
| **User** | Approve diffs; promote `weak` → `strong`; pick today's work |

**Never** rebuild the whole tree. **Never** auto-apply. **Never** set `strong` for the user.

## Large codebase layout (fragments)

```
<host>/projects/<initiative>/   # user initiatives in any host repo
  nodes.yaml
  fragments/

ai-workflow/meta/               # dogfood (CLI name: meta)
ai-workflow/examples/*          # shipped examples
```

**Root stub** links a fragment:

```yaml
- id: inspection-certificates
  title: Inspection certificates
  kind: group
  status: weak
  data:
    subtree: fragments/inspection-certificates.yaml
```

**Fragment file** (`fragments/inspection-certificates.yaml`):

```yaml
constraints:
  codebase: [services/inspection-certs]
nodes:
  - id: validation-layer
    title: Validation layer
    kind: work
    status: weak
    data:
      pattern: services/inspection-certs/validate/**
```

| Level | Where | Size |
|-------|-------|------|
| L0–L1 | `nodes.yaml` | ~10–20 stubs |
| L2–L3 | `fragments/<product>.yaml` | ~5–15 per product |
| L4+ | grow in fragment on drill-down | on demand |

**Viewer and `show` compose fragments automatically.** Mutations target root or a specific fragment.

### Bootstrap (new initiative)

1. Propose thin `nodes.yaml` with product/platform stubs + `attach-subtree` or `set-data subtree`
2. One fragment file per product (L2 subsystems)
3. All nodes `weak` by default
4. Drill down only when user picks a branch

## Commands

| Command | Purpose |
|---------|---------|
| `show <project>` | Composed tree (fragments expanded) |
| `show <project> --raw` | Root `nodes.yaml` only |
| `show <project> --fragment fragments/foo.yaml` | One fragment |
| `compose <project>` | Fragment count + composed node count |
| `list-fragments <project>` | Linked subtrees + files on disk |
| `validate-patterns <project>` | Check patterns on root |
| `validate-patterns <project> --recursive` | Root + all linked fragments |
| `propose <project> <op> ...` | Mutate root `nodes.yaml` |
| `propose <project> --fragment fragments/foo.yaml <op> ...` | Mutate one fragment |
| `apply` / `reject` / `pending` | Same `--fragment` flag when needed |

## Status model

**Default: everything is `weak`.** Only the user promotes nodes to `strong`.

| Status | Who sets it | Meaning |
|--------|-------------|---------|
| `weak` | default on new nodes | Not hardened — fair game for today's work |
| `strong` | **user only** | User trusts this area; skip unless revisiting |
| `spec_ready` | workflow | Claims/spec drafted |
| `spec_approved` | workflow | Scope contract approved |
| `done` | workflow | VERIFY passed after implementation |

## Dynamic tree

| Situation | Op | Target |
|-----------|-----|--------|
| New product | `attach-subtree` | root `nodes.yaml` |
| New subsystem | `add-child` | product fragment |
| Area obsolete | `mark-stale` | root or fragment |
| Area revived | `clear-stale` | root or fragment |
| Wrong grouping | `reparent` | within same file |
| Code moved | `set-data` | update `pattern` only |
| User trusts area | `set-status` | `strong` |

**Prefer surgical patches.** Preserve `strong` across changes. Never regen from filesystem.

## Propose operations

| Operation | Args | Example |
|-----------|------|---------|
| `batch` | `--json` or `--file` | Multi-op atomic proposal |
| `attach-subtree` | parent id title fragment_path | `attach-subtree root certs Certificates fragments/certs.yaml` |
| `add-group` / `add-child` | … | same as before |
| `set-data` | node_id json | `set-data x '{"pattern":"src/**"}'` |
| `set-status` | node_id status | `set-status x strong` |
| `set-all-weak` | [preserve...] | bulk reset |
| `mark-stale` / `clear-stale` | node_id [notes] | |
| `rename` / `reparent` | … | |

```bash
# Root: add product stub
python scripts/project_tree.py propose my-platform attach-subtree root certs "Inspection certificates" fragments/certs.yaml --no-prompt

# Fragment: add subsystem
python scripts/project_tree.py propose my-platform --fragment fragments/certs.yaml add-child certs validation "Validation layer" work --no-prompt
```

## Workflow (mandatory)

1. `show` or tree viewer (composed view) — note any `⚠ Pending` lines
2. Discuss structure — names from user unless asked
3. **`propose ... --no-prompt`** — AI stages diff only (never edit yaml by hand)
4. User reviews in terminal:
   - `pending <project> [--fragment …]` — reprint diff
   - `apply` or `reject` with the **same** `--fragment` flag as propose
5. `validate-patterns --recursive` after codebase moves

**Agent sessions:** always `--no-prompt`. Cursor chat is non-interactive — user finishes apply/reject in terminal.

**One pending per project:** root and fragment proposals share a single gate — resolve any pending before the next `propose`.

**Batch:** `propose <project> batch --file batch.json --no-prompt` — atomic multi-op diff (same apply/reject gate).

## Reference

See `examples/fragment-demo/` for a working thin-root + fragments example.

## Adding new operations

Extend `scripts/project_tree/ops.py` + `cli.py` — do not edit yaml by hand.
