# Scope Contract: Workflow overlays — insert lint/verify after implement

- **Node:** `ref-sk-workflow-overlays` (work)
- **Pattern:** `(behavioral — see VERIFY)`

## GOAL

Workflow overlays — insert lint/verify after implement behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `(behavioral — see VERIFY)`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_workflow_run` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_workflow_run` passes with fresh evidence recorded in the dogfood note.
