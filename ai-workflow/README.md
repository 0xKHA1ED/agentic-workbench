# AI Workflow

Installable agentic coding workflow for Cursor — orient, understand, spec, implement.

**Dogfood this package on itself:** project `meta` (tree at `meta/nodes.yaml`).

## Package layout

```
ai-workflow/
├── .cursor/skills/     # project-tree, scope-contract, spec-discovery
├── scripts/            # project_tree CLI, spec_discovery CLI, tree_server
├── tools/tree-viewer/  # Web UI
├── meta/               # This package's own project tree (L1 + fragments)
├── examples/           # Reference project trees (e.g. fragment-demo)
├── requirements.txt
├── AGENTS.md
└── INSTALL.md          # Add to any codebase
```

## Quick start (development)

Open **`ai-workflow/`** as your Cursor workspace, or run from this directory:

```bash
cd ai-workflow
pip install -r requirements.txt

python3 scripts/project_tree.py show meta
python3 scripts/tree_server.py   # → http://127.0.0.1:8765/?project=meta
```

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `project-tree` | `/project-tree` | Tree mutations via CLI (propose → diff → y/n) |
| `scope-contract` | `/scope-contract` | Falsifiable specs (GOAL/IN/OUT/VERIFY) |
| `spec-discovery` | `/spec-discovery` | Claims JSON → triage → assemble spec |

## Project discovery

The CLI finds trees in:

| Location | CLI name | Purpose |
|----------|----------|---------|
| `meta/` | `meta` | Developing this package (alias: `ai-workflow`) |
| `examples/*/` | folder name | Shipped examples |
| `<host>/projects/*/` | folder name | Your initiatives in any host repo |

## Host repo layout (after install)

```
your-repo/
├── ai-workflow/          # this package (submodule, copy, or vendor)
├── .cursor/skills/       # synced from ai-workflow/.cursor/skills
└── projects/
    └── my-product/       # your initiative trees
        └── nodes.yaml
```

See [INSTALL.md](INSTALL.md).
