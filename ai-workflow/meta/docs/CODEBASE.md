# Codebase map (meta)

Paths are relative to **`ai-workflow/`** (package root).

## Skills

| Capability | Skill | Path |
|------------|-------|------|
| Tree mutations | project-tree | `.cursor/skills/project-tree/SKILL.md` |
| Spec format + review | scope-contract | `.cursor/skills/scope-contract/SKILL.md` |
| Claims → spec | spec-discovery | `.cursor/skills/spec-discovery/SKILL.md` |

## CLIs

| Capability | Entry | Package |
|------------|-------|---------|
| Tree propose/compose/validate | `scripts/project_tree.py` | `scripts/project_tree/` |
| Claims triage/assemble | `scripts/spec_discovery.py` | `scripts/spec_discovery/` |
| Web UI server | `scripts/tree_server.py` | imports `project_tree.fragments` |

## Web UI

| Piece | Path |
|-------|------|
| HTML shell | `tools/tree-viewer/index.html` |
| Tree render | `tools/tree-viewer/app.js` |
| Styles | `tools/tree-viewer/styles.css` |

## Meta artifacts

| Artifact | Path |
|----------|------|
| Tree (root) | `meta/nodes.yaml` |
| Fragments | `meta/fragments/*.yaml` |
| Claims | `meta/claims/<node>.json` |
| Specs | `meta/specs/<node>.md` |

## Examples (shipped, not meta product)

| Example | Path |
|---------|------|
| Fragment layout | `examples/fragment-demo/` |

## Host sandboxes (not in package)

| Sandbox | Path (host repo) |
|---------|------------------|
| Practice | `projects/practice/` |
| Tik copy | `projects/tik/` + `sandbox/tik/` |
