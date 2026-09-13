# Install AI Workflow into any codebase

## What you copy

From this `ai-workflow/` folder into the **host repository**:

| Source | Destination |
|--------|-------------|
| `.cursor/skills/*` | `.cursor/skills/` (merge) |
| `scripts/` | `ai-workflow/scripts/` (keep package path) |
| `tools/` | `ai-workflow/tools/` |
| `requirements.txt` | `ai-workflow/requirements.txt` |

Do **not** copy `meta/` or `examples/` unless you want them — they ship with the package for reference.

## Steps

```bash
# 1. Add package to host repo (pick one)
git submodule add <url> ai-workflow
# or: cp -r ai-workflow /path/to/host/ai-workflow

# 2. Sync skills into Cursor
mkdir -p .cursor/skills
cp -r ai-workflow/.cursor/skills/* .cursor/skills/

# 3. Python deps
pip install -r ai-workflow/requirements.txt

# 4. Create your first initiative tree
mkdir -p projects/my-product/claims projects/my-product/specs
# Add projects/my-product/nodes.yaml (see meta/ or examples/fragment-demo/)
```

## Run CLIs (from host repo root)

```bash
python3 ai-workflow/scripts/project_tree.py show my-product
python3 ai-workflow/scripts/tree_server.py
python3 ai-workflow/scripts/spec_discovery.py review projects/my-product/claims/foo.json
```

## Cursor workspace

- **Option A:** Open `ai-workflow/` as workspace when developing the package itself.
- **Option B:** Open host repo root; skills load from `.cursor/skills/` after sync.

## AGENTS.md

Copy or merge [AGENTS.md](AGENTS.md) into your host `AGENTS.md` so agents discover the skills and scripts.
