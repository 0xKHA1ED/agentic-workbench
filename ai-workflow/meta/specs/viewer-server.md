# Scope Contract: tree_server compose API

- **Node:** `viewer-server` (work)
- **Pattern:** `scripts/tree_server.py`

## GOAL

tree_server compose API behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `scripts/tree_server.py`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_tree_server` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_tree_server` passes with fresh evidence recorded in the dogfood note.
