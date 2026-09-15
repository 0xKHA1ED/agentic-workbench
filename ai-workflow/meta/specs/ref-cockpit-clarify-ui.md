# Scope Contract: Clarify + checklist triage in tree viewer (J/K/Y/N)

- **Node:** `ref-cockpit-clarify-ui` (work)
- **Pattern:** `(behavioral — see VERIFY)`

## GOAL

Clarify + checklist triage in tree viewer (J/K/Y/N) behaves as specified and stays regression-proof: its VERIFY command
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
