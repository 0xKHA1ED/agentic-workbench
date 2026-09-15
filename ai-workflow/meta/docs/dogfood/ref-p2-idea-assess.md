# Dogfood: idea-assess — go/kill funnel before tree nodes (ref-p2-idea-assess)

- **Node:** `ref-p2-idea-assess` (work) — fragment `fragments/reference-improvements.yaml`
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_idea_assess`
- **Evidence (2026-09-14 certification run):** `Ran 10 tests in 0.009s` — exit 0.

Selected `ref-p2-idea-assess` from the Cockpit weak filter, opened the unified Node HUD
(`workflow_node_status` / `GET /api/node`), ran its VERIFY end-to-end, observed
the module pass (exit 0), then promoted it via
`project_tree.py propose meta set-status ref-p2-idea-assess strong` → human apply.

Certified under the §2.5 checklist: contract present (C1), VERIFY executable &
falsifiable (C2), green with fresh evidence (C3), this dogfood note (C4),
read-only gates respected (C5), promotion applied (C6).
