---
name: project-tree
description: Maintain project trees via MCP tools or scripts/project_tree.py. Projects live in meta/, examples/*, or host projects/<name>/ — show tree, propose mutations (diff), apply/reject after user approval. Never edit nodes.yaml directly.
disable-model-invocation: true
---

# Project Tree (programmatic)

**AI authors the tree. CLI/MCP persists it. User approves.**

The tree is a **work map** (concerns, pain, status) — not a filesystem mirror. At 500k LOC, use **thin root + fragment files per product**.

**AI must never edit `nodes.yaml`, `fragments/*.yaml`, or `*.proposed` directly.** All mutations go through MCP tools (`workflow_propose_tree_mutation`) or the CLI (`scripts/project_tree.py`).

Announce: "Using project-tree skill."

## Who does what

| Role | Responsibility |
|------|----------------|
| **AI** | Fetch node context (`workflow_get_node`); orient tree (`workflow_orient`); propose mutations directly via MCP (`workflow_propose_tree_mutation`); batch ops; attach `data.pattern` / `data.pain` |
| **CLI / MCP** | Diff, persist, compose fragments, validate patterns — never decide semantics |
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

## MCP Tools (Native Agent Invocation)

In Cursor sessions with the `ai-workflow` MCP server configured, **agents invoke MCP tools directly**. Do NOT demand or output manual terminal commands for tree mutations or node inspection.

### Fetch Node Context: `workflow_get_node`

Inspect complete node context before proposing changes (status, pain, pattern, linked claims, contract, verification, parent, children):

```json
{
  "project": "<project>",
  "node_id": "<node_id>"
}
```

Returns deep node state without parsing YAML files directly.

### Orientation: `workflow_orient`

Get a high-level overview of weak nodes, decayed nodes, and pending proposals:

```json
{
  "project": "<project>",
  "filter": "weak" // "weak" | "decayed" | "all"
}
```

### Propose Mutation: `workflow_propose_tree_mutation`

Stage an atomic tree mutation directly via MCP (non-blocking, diff generated automatically):

```json
{
  "project": "<project>",
  "target_node_id": "<node_id>",
  "operation": "add_child" | "set_data" | "set_status" | "mark_stale" | "clear_stale" | "reparent" | "attach_subtree",
  "payload": { ... },
  "fragment": "fragments/<file>.yaml" // optional, targets specific fragment
}
```

#### MCP Mutation Examples:
- **Add child work node**:
  ```json
  {
    "project": "my-platform",
    "target_node_id": "certs",
    "operation": "add_child",
    "payload": {
      "id": "validation",
      "title": "Validation layer",
      "kind": "work",
      "status": "weak",
      "data": { "pattern": "services/inspection-certs/validate/**" }
    },
    "fragment": "fragments/certs.yaml"
  }
  ```
- **Attach subtree fragment**:
  ```json
  {
    "project": "my-platform",
    "target_node_id": "root",
    "operation": "attach_subtree",
    "payload": {
      "id": "certs",
      "title": "Inspection certificates",
      "fragment_path": "fragments/certs.yaml",
      "kind": "group"
    }
  }
  ```
- **Attach pain / pattern to existing node**:
  ```json
  {
    "project": "my-platform",
    "target_node_id": "validation",
    "operation": "set_data",
    "payload": {
      "pain": "Marbles tunneling through dynamic colliders at high speed",
      "pattern": "services/inspection-certs/validate/**"
    },
    "fragment": "fragments/certs.yaml"
  }
  ```

---

## Commands (CLI Fallback / Human Review)

| Command | Purpose |
|---------|---------|
| `show <project>` | Composed tree (fragments expanded) |
| `show <project> --raw` | Root `nodes.yaml` only |
| `show <project> --fragment fragments/foo.yaml` | One fragment |
| `compose <project>` | Fragment count + composed node count |
| `list-fragments <project>` | Linked subtrees + files on disk |
| `validate-patterns <project>` | Check patterns on root |
| `validate-patterns <project> --recursive` | Root + all linked fragments |
| `propose <project> <op> ...` | CLI mutate root `nodes.yaml` |
| `propose <project> --fragment fragments/foo.yaml <op> ...` | CLI mutate one fragment |
| `apply` / `reject` / `pending` | User resolves staged proposals |

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

## Workflow (mandatory)

1. **Inspect context**:
   - Call `workflow_orient` or `workflow_get_node` via MCP to inspect node details, pain points, patterns, and verify status.
   - Or run `show <project>` in CLI. Note any `⚠ Pending` lines.
2. **Discuss structure**:
   - Align on names and hierarchy with the user.
3. **Propose mutation via MCP**:
   - Agent calls `workflow_propose_tree_mutation` directly via MCP tools.
   - **Never demand manual terminal commands from the user to stage mutations.** Call MCP directly.
   - (CLI fallback: `python scripts/project_tree.py propose ... --no-prompt`).
4. **User reviews in terminal or Cockpit**:
   - `pending <project> [--fragment …]` — reprint diff
   - `apply` or `reject` with the **same** `--fragment` flag as propose
5. `validate-patterns --recursive` after codebase moves

**One pending per project:** root and fragment proposals share a single gate — resolve any pending before the next `propose`.

**Batch:** `propose <project> batch --file batch.json --no-prompt` — atomic multi-op diff (same apply/reject gate).

## Reference

See `examples/fragment-demo/` for a working thin-root + fragments example.

## Adding new operations

Extend `scripts/project_tree/ops.py` + `cli.py` + `workflow_mcp.py` — do not edit yaml by hand.
