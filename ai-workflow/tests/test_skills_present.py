"""Epic H — every process-pack SKILL.md is present with valid frontmatter."""

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PACKAGE_ROOT / ".cursor" / "skills"

# The process-skill pack this program ships/certifies (Epics B + H) plus the
# meta-skills that must exist for the router and implement loop.
REQUIRED_SKILLS = [
    "using-ai-workflow",
    "brainstorming",
    "test-driven-development",
    "writing-plans",
    "executing-plans",
    "subagent-driven-development",
    "verification-before-completion",
    "systematic-debugging",
    "using-git-worktrees",
    "requesting-code-review",
    "receiving-code-review",
    "finishing-a-development-branch",
    "converge",
]


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


class TestRequiredSkillsPresent(unittest.TestCase):
    def test_required_skills_exist_with_frontmatter(self):
        for name in REQUIRED_SKILLS:
            skill = SKILLS_DIR / name / "SKILL.md"
            self.assertTrue(skill.is_file(), f"missing skill: {name}")
            fm = _frontmatter(skill.read_text(encoding="utf-8"))
            self.assertEqual(fm.get("name"), name, f"{name}: frontmatter name mismatch")
            self.assertTrue(fm.get("description"), f"{name}: missing description")

    def test_every_skill_dir_has_valid_frontmatter(self):
        for skill in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            fm = _frontmatter(skill.read_text(encoding="utf-8"))
            self.assertTrue(fm.get("name"), f"{skill}: missing frontmatter name")
            self.assertTrue(fm.get("description"), f"{skill}: missing description")


if __name__ == "__main__":
    unittest.main()
