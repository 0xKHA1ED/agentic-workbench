# AI Workflow

Installable agentic coding workflow for Cursor — orient, understand, spec, implement.

**Dogfood this package on itself:** project `meta` (tree at `meta/nodes.yaml`).

## Package layout

```
ai-workflow/
├── .cursor/skills/     # idea-assess, constitution, project-tree, scope-contract, spec-clarify, requirements-checklist, technical-plan, task-breakdown, spec-discovery
├── scripts/            # project_tree, spec_clarify, idea_assess, plan_paths, task_breakdown, spec_discovery, tree_server
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
| `idea-assess` | `/idea-assess` | Go/kill funnel before attaching tree nodes |
| `constitution` | `/constitution` | MUST/SHOULD principles; CREATE or REVIEW `constitution.md` |
| `project-tree` | `/project-tree` | Tree mutations via CLI (propose → diff → y/n) |
| `scope-contract` | `/scope-contract` | Falsifiable specs (GOAL/IN/OUT/VERIFY) |
| `spec-clarify` | `/spec-clarify` | Requirements clarification before claims |
| `technical-plan` | `/technical-plan` | Optional HOW plan.md (not the scope contract) |
| `task-breakdown` | `/task-breakdown` | Phased tasks.md from claims/spec; scoped implement |
| `spec-discovery` | `/spec-discovery` | Claims JSON → triage → assemble spec |
| `spec-analyze` | `/spec-analyze` | Read-only claims/contract gate before `/implement` |
| `requirements-checklist` | `/requirements-checklist` | Unit tests for requirements; user-only `[x]` before `/implement` |

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
