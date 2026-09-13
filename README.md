# Agentic Workbench

Cursor skills and tooling for structured agentic coding — project trees, scope contracts, and a tree viewer.

## Skills

Install by using this repo in Cursor (skills load from `.cursor/skills/`).

- **`scope-contract`** — `/scope-contract` — falsifiable specs in ~30s review time
- **`project-tree`** — `/project-tree` — conversational planning via `nodes.yaml` + CLI

## Tools

### Project tree CLI

```bash
python3 scripts/project_tree.py show my-project
python3 scripts/project_tree.py propose my-project batch --file batch.json
# → diff + interactive y/n in terminal
```

### Tree viewer

```bash
python3 scripts/tree_server.py
# → http://127.0.0.1:8765
```

## Project trees

Create `projects/<name>/nodes.yaml` for an initiative. Mutations go through `scripts/project_tree.py` only — propose, review diff, approve in terminal.

## Requirements

```bash
pip install -r requirements.txt
```
