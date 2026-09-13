# Meta (dogfood)

Project tree for **improving AI Workflow itself**. CLI name: `meta` (alias: `ai-workflow`).

## Commands

```bash
cd ai-workflow
python3 scripts/project_tree.py show meta
python3 scripts/tree_server.py   # → http://127.0.0.1:8765/?project=meta
```

## Docs

- [docs/CODEBASE.md](docs/CODEBASE.md) — which package paths map to which capability
- [docs/DAILY-LOOP.md](docs/DAILY-LOOP.md) — orient → understand → spec → implement
- [docs/L1-PROPOSAL.md](docs/L1-PROPOSAL.md) — proposed L1 nodes (discussion)

## Artifacts

| Path | Purpose |
|------|---------|
| `nodes.yaml` | Root tree (migrating to thin L1 + fragments) |
| `fragments/` | Per-capability subtrees (after L1 approved) |
| `claims/` | spec-discovery JSON |
| `specs/` | Assembled scope contracts |
