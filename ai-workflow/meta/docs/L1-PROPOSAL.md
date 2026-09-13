# L1 proposal

**Approved** — implemented in `meta/nodes.yaml` + `meta/fragments/*.yaml`.

Replace the brainstorm tree (`nodes.v0-brainstorm.yaml`) with **thin L1 + fragments**.

## Proposed L1 nodes

| id | title | What it covers |
|----|-------|----------------|
| `orient` | Orient | What to work on today — tree, viewer, weak/strong, fragments, compose |
| `understand` | Understand | Investigation ritual, pain on nodes, decomposition |
| `spec-discovery` | Spec discovery | Claims JSON, triage CLI, assemble → scope contract |
| `spec-contract` | Spec contract | `/scope-contract` format, 30s REVIEW mode |
| `implement` | Implement | Agent runs against approved spec (workflow glue — mostly gap) |
| `platform` | Platform | Shared infra — project_tree CLI, ops, patterns, tree_server |

**Optional 7th** (could merge into orient or platform):

| id | title | Notes |
|----|-------|-------|
| `examples` | Examples & sandboxes | fragment-demo, practice/tik sandboxes |

## What moves out of L1

| Old group | Fate |
|-----------|------|
| `pain-*` | Research notes — archive or fold into L2 weak nodes inside each L1 fragment |
| `desired` | Target state — becomes VERIFY items per L1, not separate tree branch |
| `daily-loop` | Becomes `docs/DAILY-LOOP.md` + ordering of L1 nodes, not duplicate nodes |
| `tooling` | Split across L1 children (each capability owns its skill + script) |

## Fragment plan (after L1 approved)

```
ai-workflow/meta/
  nodes.yaml                 # 6–7 L1 stubs with data.subtree
  fragments/
    orient.yaml
    understand.yaml
    spec-discovery.yaml
    spec-contract.yaml
    implement.yaml
    platform.yaml
```

## Status

- [x] L1 approved by user
- [x] Migrate nodes.yaml to thin root
- [x] Create fragments with L2 subsystems
- [x] All nodes `weak` by default
- [ ] User promotes shipped areas to `strong` as ready
