# Dogfood (rollup): Platform (platform)

- **Node:** `platform` (group) — fragment `root/nodes.yaml`
- **Rollup rule (§2.5):** promotable iff every descendant leaf is strong.
- **VERIFY:** `PYTHONPATH=scripts python3 -m unittest tests.test_meta_strong`
- **Evidence:** `tests.test_meta_strong` asserts the whole composed meta tree is
  strong (0 non-strong nodes), which entails every descendant of `platform`.

Rollup — all children certified. Promoted bottom-up after its descendants.
