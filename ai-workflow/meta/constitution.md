# AI Workflow Constitution

Non-negotiable principles for **ai-workflow**. Clarify, analyze, and implement
**MUST** load this file (`workflow_get_constitution` / `constitution_path`) and
**MUST NOT** contradict **MUST** rules. Missing project-local `constitution.md`
falls back to this package file.

## MUST

### I. Tree is memory

The project tree (`nodes.yaml` + fragments) is session memory — not chat.
Pain, pattern, claims, and contract links live on nodes. Do not treat a
conversation as the source of truth.

### II. Weak default

New and unexplored nodes start **weak**. Exploration does not confer trust.
Do not silently promote status.

### III. Falsifiable VERIFY

Done means executable VERIFY (pytest, command, or ast_symbol) plus MUST /
MUST NOT that another engineer can fail without reading the implementation.
Ban vague claims ("robust", "handle gracefully", "properly").

### IV. Clarify before claims

When `needs_clarify` is true or a clarify session is `in_progress`, do not
stage contract claims until `workflow_clarify_complete` (`complete` or
`skipped`). Encode recorded decisions into GOAL / IN / OUT / claims — do not
re-ask.

### V. Analyze before implement

When spec-analyze tooling exists for the node, `/implement` waits until
analyze is **complete** or **skipped**. Analyze is read-only: it MUST NOT
edit claims, contracts, tree files, or this constitution. If analyze is not
installed yet, treat as skipped.

### VI. User-only strong

Only the user promotes a node to `strong` (propose → diff → apply). Agents
may propose `set-status` (including `spec_approved` / `verified_strong` after
VERIFY) but MUST NOT apply `strong` unless the user explicitly asked.

### VII. MCP / CLI persistence

Agents author; MCP and CLI persist. Mutate trees only via
`workflow_propose_tree_mutation` or `project_tree.py propose` — never by
hand-editing `nodes.yaml` or `fragments/*.yaml`. Persistence is propose →
diff → user y/n (or explicit apply).

## SHOULD

- Keep this file short; prefer amending a principle over adding essays.
- Load an excerpt (not the full file) into context when over ~4k characters.
- Prefer surgical node updates over regenerating trees from the filesystem.
- Preserve existing `strong` nodes across unrelated mutations.
- Host projects MAY add `constitution.md` in the project dir; package
  `meta/constitution.md` remains the fallback.

## Governance

This constitution supersedes conflicting skill or chat guidance. Amendments
require an explicit `/constitution` CREATE (or REVIEW → CREATE) pass: bump
**Version** (MAJOR = removed/redefined MUST; MINOR = new principle; PATCH =
wording), set **Last Amended** to today, and keep ratification date stable.
Compliance is reviewed in clarify, analyze, and implement — not invented
mid-change.

**Version**: 1.0.0 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-14
