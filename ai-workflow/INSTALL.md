# Install AI Workflow into any codebase

## One command (recommended)

From the host repo root, after the package is present at `ai-workflow/`:

```bash
python3 ai-workflow/scripts/install.py init . --project my-product
```

`awf init` is **inspectable and idempotent**: it prints a diff of every planned
write and asks before touching `.cursor/` (no blind `curl | bash`). It:

1. writes `.cursor/mcp.json` from the in-repo template,
2. syncs `.cursor/skills/` from the package with a checksum manifest
   (`.skills-manifest.json`), so re-running only rewrites changed skills, and
3. scaffolds `projects/<name>/nodes.yaml`.

Preview without writing anything:

```bash
python3 ai-workflow/scripts/install.py init . --project my-product --plan
```

Re-running after no source changes reports "already up to date" and writes
nothing.

## What you copy (manual alternative)

From this `ai-workflow/` folder into the **host repository**:

| Source | Destination |
|--------|-------------|
| `.cursor/skills/*` | `.cursor/skills/` (merge) |
| `scripts/` | `ai-workflow/scripts/` (keep package path) |
| `tools/` | `ai-workflow/tools/` |
| `requirements.txt` | `ai-workflow/requirements.txt` |

Do **not** copy `meta/` or `examples/` unless you want them — they ship with the package for reference.

## Steps (manual)

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
