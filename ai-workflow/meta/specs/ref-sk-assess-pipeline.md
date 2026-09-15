# Scope Contract: Assess extension — intake→decide before spec-discovery

- **Node:** `ref-sk-assess-pipeline` (work)
- **Pattern:** `(behavioral — see VERIFY)`

## GOAL

Assess extension — intake→decide before spec-discovery behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `(behavioral — see VERIFY)`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_idea_assess` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_idea_assess` passes with fresh evidence recorded in the dogfood note.
