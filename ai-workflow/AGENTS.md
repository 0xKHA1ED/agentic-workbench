# AI Workflow

Installable agentic coding workflow — project trees, scope contracts, spec discovery, tree viewer.

## Layout

```
.cursor/skills/       # idea-assess, constitution, project-tree, scope-contract, spec-clarify, spec-analyze, requirements-checklist, technical-plan, task-breakdown, spec-discovery
scripts/              # project_tree, spec_clarify, spec_analyze, spec_checklist, idea_assess, plan_paths, task_breakdown, spec_discovery, tree_server
tools/tree-viewer/    # Web UI
meta/                 # Dogfood project tree (CLI name: meta) + constitution.md
examples/             # Reference trees (e.g. fragment-demo)
```

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `idea-assess` | `/idea-assess` | Go/kill funnel before attaching tree nodes |
| `constitution` | `/constitution` | MUST/SHOULD principles; CREATE or REVIEW `constitution.md` |
| `scope-contract` | `/scope-contract` | Skimmable specs (GOAL/IN/OUT/VERIFY) — WHEN/WHY |
| `spec-clarify` | `/spec-clarify` | Requirements Q&A before claims staging |
| `technical-plan` | `/technical-plan` | Optional HOW `plan.md` separate from the contract |
| `task-breakdown` | `/task-breakdown` | Phased `tasks.md` from claims/spec; scoped `/implement` |
| `project-tree` | `/project-tree` | Mutate trees via CLI only (propose → diff → y/n) |
| `spec-discovery` | `/spec-discovery` | Claims JSON → terminal triage → assemble spec |
| `spec-analyze` | `/spec-analyze` | Read-only claims/contract gate before `/implement` |
| `requirements-checklist` | `/requirements-checklist` | Unit tests for requirements; user-only `[x]` gate before `/implement` |

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

# Spec clarify (before claims when needs_clarify)
python3 scripts/spec_clarify.py paths meta <node_id> --json
python3 scripts/spec_clarify.py complete meta <node_id> --status complete --deferred observability

# Spec analyze (after assemble, before /implement)
python3 scripts/spec_analyze.py paths meta <node_id> --json
python3 scripts/spec_analyze.py run meta <node_id>
python3 scripts/spec_analyze.py complete meta <node_id>
python3 scripts/spec_analyze.py skip meta <node_id>

# Requirements checklist (user-only [x]; read-only implement gate)
python3 scripts/spec_checklist.py generate meta <node_id> --json
python3 scripts/spec_checklist.py status meta <node_id> --json
python3 scripts/spec_checklist.py validate meta/checklists/<node_id>/requirements.md --require-unchecked

# Idea assess (go/kill before tree nodes)
python3 scripts/idea_assess.py init meta <slug> --idea "…" --json
python3 scripts/idea_assess.py paths meta <slug> --json

# Technical plan (optional HOW; link via tree data.plan)
python3 scripts/plan_paths.py paths meta <node_id> --json
python3 scripts/plan_paths.py init meta <node_id> --json

# Task breakdown (phased tasks.md + scoped implement)
python3 scripts/task_breakdown.py paths meta <node_id> --json
python3 scripts/task_breakdown.py generate meta <node_id> --json
python3 scripts/task_breakdown.py scope meta <node_id> --phase 2 --json

# Tree web UI
python3 scripts/tree_server.py
```

**Host repo initiatives** live at `<host>/projects/<name>/nodes.yaml` and are discovered automatically.

Never edit `nodes.yaml` or `fragments/*.yaml` directly in agent sessions — use the CLI.

**Meta project:** `meta/` — this package applied to itself ([meta/README.md](meta/README.md)).
