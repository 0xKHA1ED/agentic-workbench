# Scope Contract: INSTALL.md — add to any codebase

- **Node:** `platform-install` (work)
- **Pattern:** `INSTALL.md`

## GOAL

INSTALL.md — add to any codebase behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `INSTALL.md`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_install` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_install` passes with fresh evidence recorded in the dogfood note.
