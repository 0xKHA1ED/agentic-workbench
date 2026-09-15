# Dogfood (rollup): Tree viewer (orient-viewer)

- **Node:** `orient-viewer` (group) — fragment `fragments/orient.yaml`
- **Rollup rule (§2.5):** promotable iff every descendant leaf is strong.
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_meta_strong`
- **Evidence:** `tests.test_meta_strong` asserts the whole composed meta tree is
  strong (0 non-strong nodes), which entails every descendant of `orient-viewer`.

Rollup — all children certified. Promoted bottom-up after its descendants.
