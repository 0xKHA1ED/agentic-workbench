# Dogfood: Walk VERIFY checklist before done (implement-verify)

- **Node:** `implement-verify` (work) — fragment `fragments/implement.yaml`
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_verify_runner`
- **Evidence (2026-09-14 certification run):** `Ran 8 tests in 0.015s` — exit 0.

Selected `implement-verify` from the Cockpit weak filter, opened the unified Node HUD
(`workflow_node_status` / `GET /api/node`), ran its VERIFY end-to-end, observed
the module pass (exit 0), then promoted it via
`project_tree.py propose meta set-status implement-verify strong` → human apply.

Certified under the §2.5 checklist: contract present (C1), VERIFY executable &
falsifiable (C2), green with fresh evidence (C3), this dogfood note (C4),
read-only gates respected (C5), promotion applied (C6).
