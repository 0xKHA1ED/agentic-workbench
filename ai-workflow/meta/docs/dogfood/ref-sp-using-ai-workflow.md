# Dogfood: using-ai-workflow meta-skill — route daily loop (ref-sp-using-ai-workflow)

- **Node:** `ref-sp-using-ai-workflow` (work) — fragment `fragments/reference-improvements.yaml`
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_path_router`
- **Evidence (2026-09-14 certification run):** `Ran 6 tests in 0.000s` — exit 0.

Selected `ref-sp-using-ai-workflow` from the Cockpit weak filter, opened the unified Node HUD
(`workflow_node_status` / `GET /api/node`), ran its VERIFY end-to-end, observed
the module pass (exit 0), then promoted it via
`project_tree.py propose meta set-status ref-sp-using-ai-workflow strong` → human apply.

Certified under the §2.5 checklist: contract present (C1), VERIFY executable &
falsifiable (C2), green with fresh evidence (C3), this dogfood note (C4),
read-only gates respected (C5), promotion applied (C6).
