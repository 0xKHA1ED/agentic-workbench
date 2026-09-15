# Scope Contract: Fragment compose + list-fragments

- **Node:** `platform-compose` (work)
- **Pattern:** `scripts/project_tree/fragments.py`

## GOAL

Fragment compose + list-fragments behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `scripts/project_tree/fragments.py`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_cli_e2e` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_cli_e2e` passes with fresh evidence recorded in the dogfood note.
