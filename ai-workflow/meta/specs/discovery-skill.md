# Scope Contract: spec-discovery skill

- **Node:** `discovery-skill` (work)
- **Pattern:** `.cursor/skills/spec-discovery/SKILL.md`

## GOAL

spec-discovery skill behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `.cursor/skills/spec-discovery/SKILL.md`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_spec_discovery_execution` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_spec_discovery_execution` passes with fresh evidence recorded in the dogfood note.
