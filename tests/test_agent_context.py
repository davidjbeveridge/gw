"""Agent controls and real context pipeline, isolated from user settings."""
import copy
import importlib.util
import json
import os
import pathlib
import tempfile
import threading
import unittest
from unittest import mock
from gw_supervisor.agent import AgentService
from gw_supervisor.agent_bootstrap import bootstrap_agent_tools, _toml
from gw_supervisor.config import DEFAULTS, merge
from gw_supervisor.context import compile_context, inject_context
from gw_supervisor.engine import Supervisor
from gw_supervisor.proxy import process_request
from gw_supervisor.util import write_json

class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.home=self.root/'state';self.project=self.root/'project';self.project.mkdir()
        (self.project/'README.md').write_text('Login validation requires fixture tests.\n',encoding='utf-8')
        self.service=AgentService(self.home,self.project,'codex',manage=True)
    def config(self,overlay=None):
        return merge(DEFAULTS,overlay or {'context_compiler':{'enabled':True,'knowledge':False}})

class AgentTests(Fixture):
    def test_status_and_setup_no_inference(self):
        with mock.patch('gw_supervisor.providers.Classifier.decide',side_effect=AssertionError('No inference')):
            self.assertEqual(self.service.gw_status()['project'],str(self.project))
            self.assertIn('cascade',self.service.gw_setup_options()['strategies'])
    def test_plan_apply_keeps_unrelated_config_and_client(self):
        write_json(self.home/'config.json',{'version':1,'goals':{'retry_limit':{'threshold':5}}})
        plan=self.service.gw_configure_plan({'context_compiler':{'enabled':True}})
        before=json.loads((self.home/'config.json').read_text())
        self.assertNotIn('context_compiler',before)
        self.assertTrue(self.service.gw_configure_apply(plan['id'])['applied'])
        after=json.loads((self.home/'config.json').read_text())
        self.assertEqual(after['goals']['retry_limit']['threshold'],5)
        self.assertTrue(after['clients']['codex']['context_compiler']['enabled'])
        self.assertTrue(self.service.gw_configure_apply(plan['id'])['already_applied'])
    def test_stale_plan_and_locks(self):
        plan=self.service.gw_configure_plan({'mode':'observe'})
        write_json(self.home/'config.json',{'version':1,'mode':'baseline'})
        with self.assertRaises(ValueError):self.service.gw_configure_apply(plan['id'])
        write_json(self.home/'config.json',{'version':1,'mode':'enforce','locked':['mode']})
        with self.assertRaises(ValueError):self.service.gw_configure_plan({'mode':'baseline'})
    def test_readonly_and_no_arbitrary_authority_or_plugin(self):
        service=AgentService(self.home,self.project,'codex')
        for operation in (lambda:service.gw_configure_plan({'mode':'observe'}),lambda:service.gw_task_set('Task'),lambda:service.gw_dashboard_open()):
            with self.assertRaises(PermissionError):operation()
        for patch in ({'authority':{'endpoint':''}},{'locked':[]},{'plugins':{'learning':{'enabled':True}}},{'knowledge':{'provider':'malicious'}}):
            with self.assertRaises(ValueError):self.service.gw_configure_plan(patch)
    def test_secret_input_rejected(self):
        with self.assertRaises(ValueError):self.service.gw_configure_plan({'decision':{'api_key':'sk-'+'a'*30}})
    def test_cascade_config_with_references(self):
        backend={'provider':'openai','endpoint':'https://model.example/v1/chat/completions','model':'reasoner','key_env':'GW_REASONER_KEY'}
        plan=self.service.gw_configure_plan({'decision':{**backend,'strategy':'cascade','fallback':{'backend':backend}}})
        self.service.gw_configure_apply(plan['id'])
        self.assertEqual(self.service._config()['decision']['strategy'],'cascade')
    @unittest.skipUnless(importlib.util.find_spec('gw_observe'),'Optional observe package')
    def test_trace_boundaries_and_dashboard_no_credential_output(self):
        from gw_observe.store import LocalTraceRepository
        run=self.service.gw_trace_start('Fixture')
        self.assertEqual(self.service.gw_trace_query()['run']['id'],run['id'])
        other=self.root/'other';other.mkdir()
        with self.service._repo() as repo:r=repo.start('Other',str(other),harness='fixture')
        with self.assertRaises(ValueError):self.service.gw_trace_query(run_id=r['id'])
        result=self.service.gw_trace_finish(run['id'],'partial','Test evidence')
        self.assertEqual(result['outcome'],'partial')
        from gw_observe.server import make_server
        from gw_supervisor.dashboard import open_dashboard
        server=make_server(self.home/'observability');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with mock.patch('gw_supervisor.dashboard.webbrowser.open',return_value=True) as browser, mock.patch('gw_supervisor.dashboard.subprocess.Popen',side_effect=AssertionError('Already running')):
                result=open_dashboard(self.home,self.project,'codex',self.service._config(),port=server.server_port)
                self.assertNotIn(server.token,json.dumps(result));self.assertTrue(result['browser_opened'])
                self.assertIn('#token=',browser.call_args.args[0])
        finally:server.shutdown();thread.join();server.server_close()

class BootstrapTests(Fixture):
    def test_all_formats_preserve_unrelated_and_are_idempotent(self):
        user=self.root/'user';user.mkdir()
        write_json(user/'.claude.json',{'unrelated':{'keep':1}})
        agents=['claude','codex','gemini','cursor','copilot','opencode']
        with mock.patch.dict(os.environ,{'XDG_CONFIG_HOME':str(user/'.config'),'COPILOT_HOME':str(user/'.copilot')}):
            first=bootstrap_agent_tools(self.home,agents,user_home=user)
            second=bootstrap_agent_tools(self.home,agents,user_home=user)
            self.assertTrue(any(r['changed'] for r in first));self.assertFalse(any(r['changed'] for r in second))
            self.assertEqual(json.loads((user/'.claude.json').read_text())['unrelated'],{'keep':1})
            self.assertIn('[mcp_servers.gw]',(user/'.codex/config.toml').read_text())
            self.assertNotIn('trust',json.loads((user/'.gemini/settings.json').read_text())['mcpServers']['gw'])
            self.assertTrue((user/'.agents/skills/gw/SKILL.md').exists())
            bootstrap_agent_tools(self.home,agents,user_home=user,install=False)
            self.assertNotIn('gw',json.loads((user/'.claude.json').read_text())['mcpServers'])
    def test_unrelated_gw_server_refused(self):
        user=self.root/'user';user.mkdir();write_json(user/'.claude.json',{'mcpServers':{'gw':{'command':'unrelated'}}})
        with self.assertRaises(ValueError):bootstrap_agent_tools(self.home,['claude'],user_home=user)
    def test_project_scope_and_no_writes_on_dry_run(self):
        result=bootstrap_agent_tools(self.home,['codex'],project=self.project,dry_run=True)
        self.assertTrue(result);self.assertFalse((self.project/'.codex').exists())
        bootstrap_agent_tools(self.home,['codex'],project=self.project)
        config=_toml((self.project/'.codex/config.toml').read_text(encoding='utf-8'))
        argv=config['mcp_servers']['gw']['args']
        self.assertEqual(argv[argv.index('--project')+1],str(self.project))
        self.assertIn('--manage',argv)
    def test_toml_preserves_existing_user_settings(self):
        path=self.project/'.codex/config.toml';path.parent.mkdir();path.write_text('model = "keep"\n[features]\nkeep = true\n')
        bootstrap_agent_tools(self.home,['codex'],self.project)
        self.assertTrue(path.read_text().startswith('model = "keep"'))
    def test_unrelated_codex_registry_refused(self):
        path=self.project/'.codex/config.toml';path.parent.mkdir();path.write_text('[mcp_servers.gw]\ncommand="other"\n')
        with self.assertRaises(ValueError):bootstrap_agent_tools(self.home,['codex'],self.project)

@unittest.skipUnless(importlib.util.find_spec('gw_knowledge'),'Optional knowledge package')
class ContextIntegrationTests(Fixture):
    def test_one_shot_requires_no_global_config(self):
        result=self.service.gw_context_compile(task='Fix login validation',query='fixture')
        self.assertEqual(result['model_calls'],0);self.assertTrue(result['selected'])
        self.assertFalse((self.home/'config.json').exists())
    def test_missing_active_skill_and_escape_fail(self):
        for files in (['missing.md'],['../README.md']):
            with self.assertRaises(ValueError):self.service.gw_context_compile(task='Task',active_skills=files)
    def test_secret_source_and_symlink_rejected(self):
        (self.project/'README.md').write_text('password=literal-secret-value')
        with self.assertRaises(ValueError):self.service.gw_context_compile(task='Task')
        if os.name!='nt':
            (self.project/'README.md').unlink();(self.project/'README.md').symlink_to(self.root/'outside.md');(self.root/'outside.md').write_text('outside')
            with self.assertRaises(ValueError):self.service.gw_context_compile(task='Task')
    def test_required_preserved_or_budget_error(self):
        from gw_knowledge.compiler import ContextBudgetExceeded
        (self.project/'SKILL.md').write_text('Important instructions '*100)
        write_json(self.home/'config.json',{'context_compiler':{'max_chars':700}})
        with self.assertRaises(ContextBudgetExceeded):self.service.gw_context_compile(task='Task',active_skills=['SKILL.md'])
    def test_proxy_schema_and_prompt_preserved(self):
        write_json(self.home/'config.json',{'context_compiler':{'enabled':True,'knowledge':False,'delivery':'proxy'}})
        with Supervisor(self.home) as supervisor:
            supervisor.store.set_task(str(self.project),'Fix login validation')
            payload={'model':'fixture','messages':[{'role':'system','content':'Keep this instruction'},{'role':'user','content':'Fix login'}],
                     'tools':[{'type':'function','function':{'name':'example','parameters':{'type':'object'}}}]}
            result=process_request(supervisor,{'client':'codex','project':str(self.project),'session':'fixture','id':'call'},payload)
            self.assertEqual(result['payload']['tools'],payload['tools']);self.assertEqual(result['payload']['messages'][:2],payload['messages'])
            self.assertEqual(len(payload['messages']),2)
            self.assertEqual(result['context_compiler']['status'],'inserted')
            self.assertIn('project:README.md',result['payload']['messages'][-1]['content'])
    def test_injection_idempotence_and_nontext_rejection(self):
        packet=self.service.gw_context_compile(task='Task')
        original={'messages':[{'role':'user','content':'Task'}]}
        once,added=inject_context(original,'chat',packet);twice,added2=inject_context(once,'chat',packet)
        self.assertTrue(added);self.assertFalse(added2);self.assertEqual(once,twice)
    def test_baseline_payload_unchanged(self):
        write_json(self.home/'config.json',{'mode':'baseline','context_compiler':{'enabled':True,'delivery':'proxy','supervisor':True}})
        with self.assertRaises(ValueError):self.service.gw_context_compile(task='Task')
        with Supervisor(self.home) as supervisor:
            data={'model':'fixture','messages':[{'role':'user','content':'Task'}]}
            self.assertEqual(process_request(supervisor,{'client':'codex','session':'s','id':'c','project':str(self.project)},data)['payload'],data)
    def test_supervisor_receives_recent_evidence(self):
        write_json(self.home/'config.json',{'context_compiler':{'enabled':True,'supervisor':True,'knowledge':False}})
        class Judge:
            state=None
            def decide(self,state,goals):
                self.state=state
                return {k:next(iter(g['choices'])) for k,g in goals.items()}
        judge=Judge()
        with Supervisor(self.home,classifier=judge) as supervisor:
            supervisor.store.set_task(str(self.project),'Fix login validation')
            r=supervisor.evaluate({'client':'codex','session':'s','id':'c','type':'tool.before','project':str(self.project),'tool':'Read','input':{'file_path':'README.md'}})
        self.assertIn('compiled_evidence',judge.state);self.assertIn('compiled_context_id',r)
    def test_opaque_provider_state_not_injected(self):
        write_json(self.home/'config.json',{'context_compiler':{'enabled':True,'delivery':'proxy','knowledge':False}})
        with Supervisor(self.home) as supervisor:
            supervisor.store.set_task(str(self.project),'Task')
            data={'model':'fixture','input':'Task','previous_response_id':'opaque'}
            r=process_request(supervisor,{'client':'codex','session':'s','id':'c','project':str(self.project)},data,'responses')
            self.assertEqual(r['payload'],data);self.assertEqual(r['context_compiler']['status'],'skipped_incompatible_or_opaque_state')
