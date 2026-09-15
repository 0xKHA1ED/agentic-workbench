# Scope Contract: subagent-driven-development — per-task implementer + review

- **Node:** `ref-sp-subagent-dev` (work)
- **Pattern:** `(behavioral — see VERIFY)`

## GOAL

subagent-driven-development — per-task implementer + review behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `(behavioral — see VERIFY)`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_skills_present` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_skills_present` passes with fresh evidence recorded in the dogfood note.
