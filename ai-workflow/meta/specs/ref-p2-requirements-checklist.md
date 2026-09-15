# Scope Contract: requirements-checklist — unit tests for requirements

- **Node:** `ref-p2-requirements-checklist` (work)
- **Pattern:** `.cursor/skills/requirements-checklist/SKILL.md,scripts/spec_checklist/**,meta/templates/requirements-checklist-template.md`

## GOAL

requirements-checklist — unit tests for requirements behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `.cursor/skills/requirements-checklist/SKILL.md,scripts/spec_checklist/**,meta/templates/requirements-checklist-template.md`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_spec_checklist` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_spec_checklist` passes with fresh evidence recorded in the dogfood note.
