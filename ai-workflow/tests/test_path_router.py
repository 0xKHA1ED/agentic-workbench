"""Epic B — path-router meta-skill (using-ai-workflow) structural checks."""

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

SKILL = PACKAGE_ROOT / ".cursor" / "skills" / "using-ai-workflow" / "SKILL.md"
DAILY_LOOP = PACKAGE_ROOT / "meta" / "docs" / "DAILY-LOOP.md"


class TestPathRouterSkill(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SKILL.is_file(), f"missing router skill: {SKILL}")
        self.text = SKILL.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_declares_three_paths(self):
        for path in ("spike", "bounded", "full"):
            self.assertIn(path, self.lower, f"router skill must declare the '{path}' path")

    def test_enforces_approval_gate(self):
        self.assertIn("approval", self.lower)
        self.assertTrue(
            "hard-gate" in self.lower or "gate" in self.lower,
            "router skill must state the approval gate",
        )
        self.assertIn("never", self.lower, "approval gate must be described as non-negotiable")

    def test_one_way_ratchet(self):
        self.assertIn("ratchet", self.lower)

    def test_path_to_phase_policy_present(self):
        for phase in ("orient", "clarify", "implement"):
            self.assertIn(phase, self.lower)

    def test_frontmatter_valid(self):
        self.assertTrue(self.text.startswith("---"))
        block = self.text.split("---", 2)[1]
        self.assertIn("name:", block)
        self.assertIn("description:", block)

    def test_daily_loop_shows_path_table(self):
        self.assertTrue(DAILY_LOOP.is_file())
        loop = DAILY_LOOP.read_text(encoding="utf-8").lower()
        self.assertIn("spike", loop)
        self.assertIn("bounded", loop)
        self.assertIn("full", loop)


if __name__ == "__main__":
    unittest.main()
