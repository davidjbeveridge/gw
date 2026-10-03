"""The unchanged agent operation must not require the knowledge package."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from gw_supervisor.agent import AgentService
from gw_supervisor.config import trust_project, DEFAULTS, merge, validate
from gw_supervisor.util import write_json


@unittest.skipUnless(importlib.util.find_spec("gw_context"), "Optional context package")
class ContextIndependenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.project, self.home = self.root / "project", self.root / "state"
        self.project.mkdir()
        (self.project / "README.md").write_text("Project fixture evidence.", encoding="utf-8")
        self.agent = AgentService(self.home, self.project, "generic", manage=True)

    def configure(self, **settings):
        write_json(self.home / "config.json", {"context_compiler": settings})

    def test_project_only_in_a_fresh_process_that_blocks_knowledge(self):
        code = '''
import importlib.abc, sys
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] == 'gw_knowledge':
            raise AssertionError('Knowledge package imported: ' + fullname)
sys.meta_path.insert(0, Reject())
from gw_supervisor.agent import AgentService
agent = AgentService(sys.argv[1], sys.argv[2])
packet = agent.gw_context_compile(task='Check the project fixture')
assert packet['selected'] and packet['retrieval'] is None
assert packet['model_calls'] == 0
assert not (agent.home / 'knowledge').exists()
'''
        subprocess.run([sys.executable, "-c", code, str(self.home), str(self.project)],
                       check=True, capture_output=True, text=True, timeout=20)

    def source(self, *, fail=False, trusted=False, scope=None):
        from gw_context import ContextItem, SourceResult
        source = Mock()
        def collect(request):
            if fail:
                raise RuntimeError("PRIVATE_VENDOR_ERROR_NOT_TO_BE_LOGGED")
            return SourceResult((ContextItem("doc", "knowledge", "Vendor evidence.", "vendor:doc", "v1", required=trusted),), scope or request.scope, "corpus-v1")
        source.collect.side_effect = collect
        return source

    def test_external_and_project_sources_without_knowledge_service(self):
        self.configure(knowledge=False, sources={"vendor": {"provider": "fixture"}})
        source = self.source()
        with patch("gw_context.open_source", return_value=source), patch("gw_supervisor.knowledge.open_service", side_effect=AssertionError("No knowledge")):
            packet = self.agent.gw_context_compile(task="Use project and vendor evidence")
        self.assertEqual(len(packet["selected"]), 2)
        self.assertEqual(packet["sources"][0]["revision"], "corpus-v1")
        self.assertIn("scope", packet["payload"])
        source.close.assert_called_once()

    def test_multiple_sources_and_disabled_sources(self):
        self.configure(knowledge=False, sources={
            "a": {"provider": "fixture"}, "b": {"provider": "fixture"},
            "disabled": {"provider": "fixture", "enabled": False},
        })
        with patch("gw_context.open_source", side_effect=[self.source(), self.source()]) as factory:
            packet = self.agent.gw_context_compile(task="Task")
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(len(packet["selected"]), 3)
        self.assertEqual(packet["sources"][-1]["status"], "disabled")

    def test_failed_source_is_explicit_and_does_not_leak_error_text(self):
        self.configure(knowledge=False, sources={"vendor": {"provider": "fixture"}})
        with patch("gw_context.open_source", return_value=self.source(fail=True)), self.assertRaises(ValueError) as error:
            self.agent.gw_context_compile(task="Task")
        self.assertNotIn("PRIVATE_VENDOR", str(error.exception))
        self.configure(knowledge=False, sources={"vendor": {"provider": "fixture", "on_error": "omit"}})
        with patch("gw_context.open_source", return_value=self.source(fail=True)):
            packet = self.agent.gw_context_compile(task="Task")
        self.assertEqual(packet["unavailable"][0]["reason"], "unavailable")
        self.assertNotIn("PRIVATE_VENDOR", json.dumps(packet))

    def test_source_cannot_inject_authority_or_cross_scope(self):
        self.configure(knowledge=False, sources={"vendor": {"provider": "fixture"}})
        for source in (self.source(trusted=True), self.source(scope="wrong")):
            with patch("gw_context.open_source", return_value=source), self.assertRaises(ValueError):
                self.agent.gw_context_compile(task="Task")

    def test_project_cannot_choose_provider_including_client_overrides(self):
        for overlay in ({"context_compiler": {"sources": {}}}, {"clients": {"generic": {"context_compiler": {"sources": {}}}}}):
            write_json(self.project / ".gw.json", overlay)
            with self.assertRaises(ValueError):
                trust_project(self.home, self.project)

    def test_agent_can_choose_only_installed_sources(self):
        with patch("gw_context.installed_sources", return_value=["fixture"]):
            plan = self.agent.gw_configure_plan({"context_compiler": {"sources": {"vendor": {"provider": "fixture"}}}})
            self.agent.gw_configure_apply(plan["id"])
            self.assertIn("fixture", self.agent.gw_setup_options()["context_source_providers"])
            with self.assertRaises(ValueError):
                self.agent.gw_configure_plan({"context_compiler": {"sources": {"bad": {"provider": "not-installed"}}}})

    def test_source_options_cannot_contain_literal_secrets(self):
        with self.assertRaises(ValueError):
            validate(merge(DEFAULTS, {"context_compiler": {"sources": {"vendor": {"provider": "fixture", "options": {"api_key": "a-secret"}}}}}))

    @unittest.skipUnless(importlib.util.find_spec("gw_context_fixture"), "Installed external source fixture")
    def test_real_installed_source_in_isolated_process_without_knowledge(self):
        code = '''
import importlib.abc, sys
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] == 'gw_knowledge':
            raise AssertionError('Knowledge package imported: ' + fullname)
sys.meta_path.insert(0, Reject())
from gw_supervisor.agent import AgentService
agent = AgentService(sys.argv[1], sys.argv[2], manage=True)
assert 'fixture' in agent.gw_setup_options()['context_source_providers']
plan = agent.gw_configure_plan({'context_compiler': {'knowledge': False, 'sources': {'external': {'provider': 'fixture'}}}})
agent.gw_configure_apply(plan['id'])
packet = agent.gw_context_compile(task='Test vendor login guidance')
assert len(packet['selected']) == 2 and packet['sources'][0]['status'] == 'collected'
assert packet['model_calls'] == 0 and not (agent.home / 'knowledge').exists()
'''
        subprocess.run([sys.executable, "-I", "-c", code, str(self.home), str(self.project)],
                       check=True, capture_output=True, text=True, timeout=20)

    @unittest.skipUnless(importlib.util.find_spec("gw_knowledge"), "Optional knowledge integration")
    def test_original_knowledge_bridge_and_compatibility_import(self):
        from gw_supervisor.knowledge import open_service
        from gw_knowledge.compiler import ContextItem as LegacyItem
        from gw_context import ContextItem
        self.assertIs(LegacyItem, ContextItem)
        write_json(self.home / "config.json", {"knowledge": {"enabled": True, "allow_writes": True}})
        with open_service(self.home, self.project, "generic") as service:
            service.dispatch("put", {"scope": service.scope.to_dict(), "document": {
                "document_id": "guide", "title": "Guide", "text": "Knowledge fixture advice.", "source": "fixture:guide",
            }})
        a = self.agent.gw_context_compile(task="Task", query="fixture")
        b = self.agent.gw_context_compile(task="Task", query="fixture")
        self.assertIsNotNone(a["retrieval"])
        self.assertTrue(b["retrieval"]["cache"]["hit"])
        self.assertTrue(any(i["source"].startswith("knowledge:") for i in a["selected"]))
