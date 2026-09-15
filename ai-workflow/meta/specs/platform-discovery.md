# Scope Contract: Project discovery (meta, examples, host)

- **Node:** `platform-discovery` (work)
- **Pattern:** `scripts/project_tree/model.py`

## GOAL

Project discovery (meta, examples, host) behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `scripts/project_tree/model.py`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_model` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_model` passes with fresh evidence recorded in the dogfood note.
