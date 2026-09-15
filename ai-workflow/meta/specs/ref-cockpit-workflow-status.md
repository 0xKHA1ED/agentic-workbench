# Scope Contract: Workflow run status + resume from paused gate

- **Node:** `ref-cockpit-workflow-status` (work)
- **Pattern:** `(behavioral — see VERIFY)`

## GOAL

Workflow run status + resume from paused gate behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `(behavioral — see VERIFY)`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_cockpit_e2e` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_cockpit_e2e` passes with fresh evidence recorded in the dogfood note.
