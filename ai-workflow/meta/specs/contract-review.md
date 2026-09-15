# Scope Contract: REVIEW mode — 30s approve/fix

- **Node:** `contract-review` (work)
- **Pattern:** `.cursor/skills/scope-contract/SKILL.md`

## GOAL

REVIEW mode — 30s approve/fix behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `.cursor/skills/scope-contract/SKILL.md`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_spec_analyze` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_spec_analyze` passes with fresh evidence recorded in the dogfood note.
