# Dogfood (rollup): Reference-inspired improvements (Spec Kit + Superpowers) (ref-imp-overview)

- **Node:** `ref-imp-overview` (group) — fragment `fragments/reference-improvements.yaml`
- **Rollup rule (§2.5):** promotable iff every descendant leaf is strong.
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_meta_strong`
- **Evidence:** `tests.test_meta_strong` asserts the whole composed meta tree is
  strong (0 non-strong nodes), which entails every descendant of `ref-imp-overview`.

Rollup — all children certified. Promoted bottom-up after its descendants.
