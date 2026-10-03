"""Public host boundaries must not depend on path spelling or unrelated plugins."""
import importlib.util
import pathlib
import tempfile
import unittest

from gw_supervisor.config import resolve, trust_project
from gw_supervisor.util import write_json


class ProjectIdentityTests(unittest.TestCase):
    def test_trust_and_resolve_share_canonical_project_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            project = root / "project"
            child = project / "child"
            child.mkdir(parents=True)
            home = root / "state"
            write_json(project / ".gw.json", {"goals": {"retry_limit": {"threshold": 2}}})
            alias = child / ".."
            snapshot = trust_project(home, alias)
            self.assertEqual(snapshot["project"], str(project.resolve()))
            for supplied in (project.resolve(), alias, child):
                with self.subTest(project=supplied):
                    config, status = resolve(home, supplied, "codex")
                    self.assertEqual(status, "trusted_snapshot")
                    self.assertEqual(config["goals"]["retry_limit"]["threshold"], 2)
            self.assertEqual(len(list((home / "projects").glob("*.json"))), 1)


@unittest.skipUnless(importlib.util.find_spec("gw_observe"), "Optional observation package")
class ObservationIndependenceTests(unittest.TestCase):
    def test_trace_prompt_does_not_require_context_plugin(self):
        from gw_builtin.agent import AgentService
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            home = root / "state"
            write_json(home / "config.json", {"runtime": {"disable": ["gw.context"]}})
            (root / "task.txt").write_text("Fix the parser without unrelated refactors.", encoding="utf-8")
            agent = AgentService(home, root, "codex", manage=True)
            self.assertNotIn("gw_context_compile", dir(agent))
            run = agent.gw_trace_start("Prompt without compiler", prompt_file="task.txt")
            self.assertTrue(run["manifest"]["prompt"]["hash"])
            self.assertEqual(agent.gw_trace_query()["run"]["id"], run["id"])
            agent.gw_trace_finish(run["id"], "unknown", "Fixture only")

    def test_trace_prompt_path_cannot_escape_bound_project(self):
        from gw_builtin.agent_tools.observe import _file
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            host = SimpleNamespace(project=pathlib.Path(tmp).resolve())
            for value in ("../outside.txt", "/outside.txt", "C:/outside.txt", "..\\outside.txt"):
                with self.subTest(path=value), self.assertRaises(ValueError):
                    _file(host, value)


if __name__ == "__main__":
    unittest.main()
