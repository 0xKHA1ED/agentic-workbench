# AI Workflow

Installable agentic coding workflow — project trees, scope contracts, spec discovery, tree viewer.

## Layout

```
.cursor/skills/       # project-tree, scope-contract, spec-discovery
scripts/              # project_tree CLI, spec_discovery CLI, tree_server
tools/tree-viewer/    # Web UI
meta/                 # Dogfood project tree (CLI name: meta)
examples/             # Reference trees (e.g. fragment-demo)
```

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `scope-contract` | `/scope-contract` | Skimmable specs (GOAL/IN/OUT/VERIFY) |
| `project-tree` | `/project-tree` | Mutate trees via CLI only (propose → diff → y/n) |
| `spec-discovery` | `/spec-discovery` | Claims JSON → terminal triage → assemble spec |

## Scripts

Run from **`ai-workflow/`** directory (or prefix paths from host repo):

```bash
pip install -r requirements.txt

# Tree CLI
python3 scripts/project_tree.py show meta
python3 scripts/project_tree.py compose meta
python3 scripts/project_tree.py list-fragments meta
python3 scripts/project_tree.py validate-patterns meta --recursive
python3 scripts/project_tree.py propose meta batch --file batch.json

# Spec discovery
python3 scripts/spec_discovery.py validate meta/claims/<node>.json
python3 scripts/spec_discovery.py review meta/claims/<node>.json
python3 scripts/spec_discovery.py assemble meta/claims/<node>.json

# Tree web UI
python3 scripts/tree_server.py
```

**Host repo initiatives** live at `<host>/projects/<name>/nodes.yaml` and are discovered automatically.

Never edit `nodes.yaml` or `fragments/*.yaml` directly in agent sessions — use the CLI.

**Meta project:** `meta/` — this package applied to itself ([meta/README.md](meta/README.md)).
