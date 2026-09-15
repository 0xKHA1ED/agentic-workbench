"""Epic D — one-command install kit (awf init): files, idempotency, inspectability."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PACKAGE_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import install as awf_install


class TestInstallKit(unittest.TestCase):
    def _install(self, target, **kw):
        return awf_install.install(target, out=io.StringIO(), **kw)

    def test_install_creates_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = self._install(target, project_name="demo", assume_yes=True)
            self.assertTrue((target / ".cursor" / "mcp.json").is_file())
            self.assertTrue((target / ".cursor" / "skills" / "using-ai-workflow" / "SKILL.md").is_file())
            self.assertTrue((target / "projects" / "demo" / "nodes.yaml").is_file())
            self.assertTrue((target / ".cursor" / "skills" / awf_install.MANIFEST_NAME).is_file())
            self.assertTrue(result["changed"])
            self.assertGreater(len(result["written"]), 0)

    def test_mcp_json_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._install(target, assume_yes=True)
            import json

            mcp = json.loads((target / ".cursor" / "mcp.json").read_text())
            self.assertIn("ai-workflow", mcp["mcpServers"])
            self.assertEqual(mcp["mcpServers"]["ai-workflow"]["args"], ["scripts/workflow_mcp.py"])

    def test_scaffold_is_valid_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._install(target, project_name="demo", assume_yes=True)
            import yaml

            doc = yaml.safe_load((target / "projects" / "demo" / "nodes.yaml").read_text())
            self.assertEqual(doc["project"], "demo")
            self.assertEqual(doc["nodes"][0]["id"], "root")
            self.assertEqual(doc["nodes"][0]["status"], "weak")

    def test_idempotent_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._install(target, project_name="demo", assume_yes=True)
            second = self._install(target, project_name="demo", assume_yes=True)
            self.assertFalse(second["changed"])
            self.assertEqual(second["written"], [])

    def test_plan_is_inspectable_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            plan = awf_install.plan_install(target, project_name="demo")
            self.assertTrue(plan["changed"])
            self.assertFalse((target / ".cursor").exists(), "plan must not write anything")
            kinds = {a["kind"] for a in plan["actions"]}
            self.assertIn("create", kinds)

    def test_confirm_false_aborts_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = awf_install.install(
                target,
                project_name="demo",
                assume_yes=False,
                confirm=lambda _prompt: False,
                out=io.StringIO(),
            )
            self.assertTrue(result.get("aborted"))
            self.assertEqual(result["written"], [])
            self.assertFalse((target / ".cursor").exists())

    def test_skill_manifest_matches_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._install(target, assume_yes=True)
            import json

            written = json.loads((target / ".cursor" / "skills" / awf_install.MANIFEST_NAME).read_text())
            source = awf_install.compute_skill_manifest()
            self.assertEqual(written, source)


if __name__ == "__main__":
    unittest.main()
