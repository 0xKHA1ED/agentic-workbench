# Scope Contract: Web UI render + weak/strong badges

- **Node:** `viewer-ui` (work)
- **Pattern:** `tools/tree-viewer/app.js,tools/tree-viewer/styles.css,tools/tree-viewer/index.html`

## GOAL

Web UI render + weak/strong badges behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `tools/tree-viewer/app.js,tools/tree-viewer/styles.css,tools/tree-viewer/index.html`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_cockpit_e2e` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_cockpit_e2e` passes with fresh evidence recorded in the dogfood note.
