"""Epic H — converge appends unmet contract acceptance items to tasks (append-only)."""

import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import converge

CONTRACT = """# Scope Contract: Widget

## GOAL
Do the widget.

## ACCEPTANCE
- [ ] Widget renders on load
- [ ] Widget survives reload
- [ ] Widget logs an error on bad input
"""

TASKS = """# Tasks: widget

- [x] Widget renders on load
"""


class TestFindGaps(unittest.TestCase):
    def test_acceptance_items_extracted(self):
        items = converge.contract_acceptance_items(CONTRACT)
        self.assertIn("Widget renders on load", items)
        self.assertIn("Widget survives reload", items)
        self.assertEqual(len(items), 3)

    def test_gaps_exclude_items_present_in_tasks(self):
        gaps = converge.find_gaps(CONTRACT, TASKS)
        self.assertNotIn("Widget renders on load", gaps)
        self.assertIn("Widget survives reload", gaps)
        self.assertIn("Widget logs an error on bad input", gaps)

    def test_no_tasks_means_all_acceptance_are_gaps(self):
        gaps = converge.find_gaps(CONTRACT, "")
        self.assertEqual(len(gaps), 3)

    def test_none_placeholder_ignored(self):
        contract = "## ACCEPTANCE\n- [ ] (none)\n"
        self.assertEqual(converge.contract_acceptance_items(contract), [])


class TestConvergeAppends(unittest.TestCase):
    def test_converge_appends_gaps_to_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "contract.md"
            tasks_path = Path(tmp) / "tasks.md"
            contract_path.write_text(CONTRACT, encoding="utf-8")
            tasks_path.write_text(TASKS, encoding="utf-8")

            result = converge.converge(contract_path, tasks_path)
            self.assertEqual(result["appended"], 2)

            tasks_after = tasks_path.read_text(encoding="utf-8")
            self.assertIn(converge.CONVERGE_HEADING, tasks_after)
            self.assertIn("- [ ] Widget survives reload", tasks_after)
            self.assertIn("- [ ] Widget logs an error on bad input", tasks_after)
            # Append-only: the already-checked item is untouched.
            self.assertIn("- [x] Widget renders on load", tasks_after)

    def test_converge_without_tasks_reports_gaps_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "contract.md"
            contract_path.write_text(CONTRACT, encoding="utf-8")
            result = converge.converge(contract_path, None)
            self.assertEqual(result["appended"], 0)
            self.assertEqual(len(result["gaps"]), 3)

    def test_converge_rerun_after_fix_reports_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "contract.md"
            tasks_path = Path(tmp) / "tasks.md"
            contract_path.write_text(CONTRACT, encoding="utf-8")
            # Tasks now mention every acceptance item.
            tasks_path.write_text(
                "# Tasks\n- [x] Widget renders on load\n"
                "- [x] Widget survives reload\n"
                "- [x] Widget logs an error on bad input\n",
                encoding="utf-8",
            )
            result = converge.converge(contract_path, tasks_path)
            self.assertEqual(result["appended"], 0)
            self.assertEqual(result["gaps"], [])


if __name__ == "__main__":
    unittest.main()
