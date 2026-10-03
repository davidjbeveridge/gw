"""CI installs the example extension as a separate distribution before running."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

@unittest.skipUnless(importlib.util.find_spec('gw_example_plugin'),'Install examples/runtime-plugin for real discovery check')
class InstalledPluginTests(unittest.TestCase):
    def test_explicit_discovery_evaluation_and_agent_tool(self):
        from gw_supervisor.engine import Supervisor
        from gw_builtin.agent import AgentService
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); home=root/'state';home.mkdir()
            (home/'config.json').write_text(json.dumps({'runtime':{'enable':['gw.example.review']}}))
            with Supervisor(home) as s:
                result=s.evaluate({'project':tmp,'client':'generic','session':'a','type':'tool.before','tool':'Bash','input':{'command':'echo GW_EXTENSION_REVIEW'}})
                self.assertEqual(result['decision'],'approve')
            agent=AgentService(home,root)
            self.assertTrue(agent.gw_review_demo_status()['settings']['enabled'])
            self.assertIn('gw_review_demo_status',dir(agent))

    def test_agent_can_configure_new_owned_section_without_core_changes(self):
        from gw_builtin.agent import AgentService
        with tempfile.TemporaryDirectory() as tmp:
            home=pathlib.Path(tmp)/'state';home.mkdir()
            (home/'config.json').write_text(json.dumps({'runtime':{'enable':['gw.example.review']}}))
            agent=AgentService(home,tmp,manage=True)
            plan=agent.gw_configure_plan({'review_demo':{'enabled':False}})
            agent.gw_configure_apply(plan['id'])
            self.assertFalse(agent.gw_review_demo_status()['settings']['enabled'])

    def test_config_isolated_by_client_and_project(self):
        from gw_builtin.agent import AgentService
        from gw_supervisor.config import trust_project
        with tempfile.TemporaryDirectory() as tmp:
            home=pathlib.Path(tmp)/'state';home.mkdir()
            (home/'config.json').write_text(json.dumps({'runtime':{'enable':['gw.example.review']},'clients':{'codex':{'review_demo':{'enabled':False}}}}))
            self.assertFalse(AgentService(home,tmp,'codex').gw_review_demo_status()['settings']['enabled'])
            self.assertTrue(AgentService(home,tmp,'claude').gw_review_demo_status()['settings']['enabled'])
            (pathlib.Path(tmp)/'.gw.json').write_text(json.dumps({'review_demo':{'enabled':True}}))
            trust_project(home,pathlib.Path(tmp))
            self.assertTrue(AgentService(home,tmp,'codex').gw_review_demo_status()['settings']['enabled'])

    def test_plugin_graph_change_invalidates_bound_tool(self):
        from gw_builtin.agent import AgentService
        from gw_supervisor.api import PluginError
        with tempfile.TemporaryDirectory() as tmp:
            home=pathlib.Path(tmp)/'state';home.mkdir()
            (home/'config.json').write_text(json.dumps({'runtime':{'enable':['gw.example.review']}}))
            agent=AgentService(home,tmp);tool=agent.gw_review_demo_status
            (home/'config.json').write_text('{}')
            with self.assertRaises(PluginError): tool()
