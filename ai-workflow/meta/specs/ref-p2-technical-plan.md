# Scope Contract: technical-plan — optional plan.md (HOW) separate from contract

- **Node:** `ref-p2-technical-plan` (work)
- **Pattern:** `.cursor/skills/technical-plan/SKILL.md,scripts/plan_paths.py,scripts/plan_paths/**`

## GOAL

technical-plan — optional plan.md (HOW) separate from contract behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `.cursor/skills/technical-plan/SKILL.md,scripts/plan_paths.py,scripts/plan_paths/**`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_plan_paths` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_plan_paths` passes with fresh evidence recorded in the dogfood note.
