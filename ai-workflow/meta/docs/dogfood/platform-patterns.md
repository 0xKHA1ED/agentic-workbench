# Dogfood: validate-patterns --recursive (platform-patterns)

- **Node:** `platform-patterns` (work) — fragment `fragments/platform.yaml`
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_cli_e2e`
- **Evidence (2026-09-14 certification run):** `Ran 9 tests in 0.417s` — exit 0.

Selected `platform-patterns` from the Cockpit weak filter, opened the unified Node HUD
(`workflow_node_status` / `GET /api/node`), ran its VERIFY end-to-end, observed
the module pass (exit 0), then promoted it via
`project_tree.py propose meta set-status platform-patterns strong` → human apply.

Certified under the §2.5 checklist: contract present (C1), VERIFY executable &
falsifiable (C2), green with fresh evidence (C3), this dogfood note (C4),
read-only gates respected (C5), promotion applied (C6).
