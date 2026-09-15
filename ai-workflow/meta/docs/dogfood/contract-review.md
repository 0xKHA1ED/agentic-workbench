# Dogfood: REVIEW mode — 30s approve/fix (contract-review)

- **Node:** `contract-review` (work) — fragment `fragments/spec-contract.yaml`
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_spec_analyze`
- **Evidence (2026-09-14 certification run):** `Ran 11 tests in 0.053s` — exit 0.

Selected `contract-review` from the Cockpit weak filter, opened the unified Node HUD
(`workflow_node_status` / `GET /api/node`), ran its VERIFY end-to-end, observed
the module pass (exit 0), then promoted it via
`project_tree.py propose meta set-status contract-review strong` → human apply.

Certified under the §2.5 checklist: contract present (C1), VERIFY executable &
falsifiable (C2), green with fresh evidence (C3), this dogfood note (C4),
read-only gates respected (C5), promotion applied (C6).
