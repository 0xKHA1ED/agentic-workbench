# Phase 0 baseline — friction-zero → 100% strong

- **Branch:** `feat/friction-zero-100pct` (from `ed1ee6b`)
- **Date:** 2026-09-14

## Green baseline (captured this session)

```
python3 scripts/project_tree.py compose meta   → Fragments: 7 | Composed nodes: 77
PYTHONPATH=scripts python3 -m unittest discover -s tests   → Ran 293 tests … OK (skipped=1)
```

- Composed nodes: **77** (19 groups + 58 leaves).
- Strong at baseline: **9 leaves** (`tree-cli-usage`, `viewer-ui`, `ref-p1-spec-clarify`,
  `ref-p1-spec-analyze`, `ref-p1-constitution`, `ref-p2-requirements-checklist`,
  `ref-p2-task-breakdown`, `ref-p2-technical-plan`, `ref-p2-idea-assess`).
- Test suite: 293 pass, 1 skipped, 0 fail.

This file is the C3 evidence anchor for the certification program: every subsequent
promotion re-runs its node's VERIFY against this same green tree.
