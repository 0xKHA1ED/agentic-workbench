# Dogfood (rollup): P2 — Spec depth (ref-p2-spec)

- **Node:** `ref-p2-spec` (group) — fragment `fragments/reference-improvements.yaml`
- **Rollup rule (§2.5):** promotable iff every descendant leaf is strong.
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_meta_strong`
- **Evidence:** `tests.test_meta_strong` asserts the whole composed meta tree is
  strong (0 non-strong nodes), which entails every descendant of `ref-p2-spec`.

Rollup — all children certified. Promoted bottom-up after its descendants.
