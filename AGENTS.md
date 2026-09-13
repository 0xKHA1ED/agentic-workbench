# Agentic Workbench

Skills, scripts, and tooling for agentic coding workflows — project trees, scope contracts, tree viewer.

## Layout

```
.cursor/skills/       # Cursor skills (scope-contract, project-tree, spec-discovery)
scripts/              # project_tree CLI, spec_discovery CLI, tree_server
tools/tree-viewer/    # Web UI for projects/*/nodes.yaml
projects/             # Per-initiative trees (nodes.yaml) — not committed by default unless you add them
```

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `scope-contract` | `/scope-contract` | Skimmable specs (GOAL/IN/OUT/VERIFY) |
| `project-tree` | `/project-tree` | Mutate `nodes.yaml` via CLI only (propose → diff → y/n) |
| `spec-discovery` | `/spec-discovery` | AI proposes claims JSON → terminal y/n triage → assemble spec |

## Scripts

```bash
pip install -r requirements.txt

# Tree CLI
python3 scripts/project_tree.py show <project>
python3 scripts/project_tree.py validate-patterns <project>
python3 scripts/project_tree.py propose <project> batch --file batch.json

# Spec discovery
python3 scripts/spec_discovery.py validate projects/<name>/claims/<node>.json
python3 scripts/spec_discovery.py review projects/<name>/claims/<node>.json
python3 scripts/spec_discovery.py assemble projects/<name>/claims/<node>.json

# Tree web UI
python3 scripts/tree_server.py
```

Project trees live at `projects/<name>/nodes.yaml`. Use the CLI to mutate; never edit yaml directly in agent sessions.
