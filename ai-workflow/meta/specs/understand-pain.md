# Scope Contract: Capture pain on node data.pain

- **Node:** `understand-pain` (work)
- **Pattern:** `.cursor/skills/project-tree/SKILL.md`

## GOAL

Capture pain on node data.pain behaves as specified and stays regression-proof: its VERIFY command
passes from a clean checkout and fails if the behavior regresses.

## IN

- The behavior implemented under `.cursor/skills/project-tree/SKILL.md`.
- The VERIFY command below exiting 0.

## OUT

- Behavior owned by sibling nodes / other fragments.
- Anything the VERIFY command does not exercise.

## VERIFY

- [ ] check_type: command | `PYTHONPATH=scripts python3 -m unittest tests.test_ops` exits 0 (falsifiable: fails if the behavior is absent).

## ACCEPTANCE

- [ ] `tests.test_ops` passes with fresh evidence recorded in the dogfood note.
