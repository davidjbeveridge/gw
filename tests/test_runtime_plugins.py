"""Core/plugin contract tests, including a runtime with no reference implementations."""
from __future__ import annotations
import copy
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from gw_supervisor.api import (Advice, Assessment, Command, ConfigSection, Evaluator,
                               Plugin, PluginError, Tool, digest)
from gw_supervisor.registry import PluginManager, discover, selection
from gw_supervisor.engine import Supervisor


class MemoryRepository:
    def __init__(self): self.sessions, self.events, self.closed = {}, {}, False
    def session(self, event, config):
        sid = digest([event['project'], event['client'], event['session']])
        self.sessions.setdefault(sid, {'id': sid, 'task': event.get('task', 'fixture'),
            'project': event['project'], 'client': event['client'], 'config': copy.deepcopy(config)})
        return copy.deepcopy(self.sessions[sid])
    def cached_event(self, sid, event):
        return copy.deepcopy(self.events.get((sid, event['id'], event['type'])))
    def commit(self, session, event, result, updates):
        key = (session['id'], event['id'], event['type'])
        self.events.setdefault(key, copy.deepcopy(result))
        return copy.deepcopy(self.events[key])
    def close(self): self.closed = True


def memory_plugin(repo):
    return Plugin('fixture.state', '1', services={'state': lambda host: SimpleNamespace(open=lambda home: repo)})


def guard(id='fixture.guard', effect='deny', phase='local', callback=None):
    return Plugin(id, '1', evaluators=(Evaluator(id, phase, callback or (lambda ctx: Assessment((Advice(effect, id),)))),))


class CompositionTests(unittest.TestCase):
    def test_explicit_selection(self):
        self.assertEqual(selection({'profile': 'minimal', 'enable': ['custom']}), ('custom',))
        self.assertNotIn('gw.context', selection({'disable': ['gw.context']}))
        for config in ({'profile': 'other'}, {'enable': ['a', 'a']}, {'enable': ['a'], 'disable': ['a']}, {'enable': ['../module.py']}):
            with self.assertRaises(PluginError): selection(config)
    def test_api_version_and_duplicate_identity(self):
        with self.assertRaises(PluginError): PluginManager([Plugin('new', '1', api_version=2)])
        with self.assertRaises(PluginError): PluginManager([Plugin('same', '1'), Plugin('same', '2')])
    def test_duplicate_services_config_commands_and_tools(self):
        features = [dict(services={'state': lambda h: None}),
            dict(config=(ConfigSection('sample', {}, lambda c: None),)),
            dict(commands=(Command('sample', lambda a: None),)),
            dict(tools=(Tool('sample', lambda h: lambda: {}),))]
        for fields in features:
            with self.subTest(fields=fields), self.assertRaises(PluginError):
                PluginManager([Plugin('a', '1', **fields), Plugin('b', '1', **fields)])
        with self.assertRaises(PluginError):
            PluginManager([Plugin('a','1',config=(ConfigSection('nested',{},lambda c:None),)),
                           Plugin('b','1',config=(ConfigSection('nested.child',{},lambda c:None),))])
    def test_missing_dependency_and_cycles(self):
        with self.assertRaises(PluginError): PluginManager([Plugin('a','1',requires=('missing',))])
        with self.assertRaises(PluginError):
            PluginManager([Plugin('a','1',requires=('b',),services={'a': lambda h:None}),
                           Plugin('b','1',requires=('a',),services={'b': lambda h:None})])
    def test_stable_order_independent_of_registration(self):
        plugins=[guard('a'),guard('b',phase='authority'),guard('c',phase='plan')]
        a=PluginManager(plugins); b=PluginManager(list(reversed(plugins)))
        self.assertEqual(a.describe(),b.describe())
        self.assertEqual([e.phase for _,e in a.evaluators],['local','plan','authority'])
    def test_invalid_phase_order_rejected(self):
        with self.assertRaises(PluginError):
            PluginManager([guard('authority',phase='authority'),Plugin('local','1',evaluators=(Evaluator('local','local',lambda c:Assessment(),after=('authority',)),))])
    def test_lazy_services_and_reverse_cleanup(self):
        calls=[]
        def factory(name):
            calls.append('open:'+name)
            return SimpleNamespace(close=lambda:calls.append('close:'+name))
        manager=PluginManager([Plugin('a','1',services={'a':lambda h:factory('a')}),
            Plugin('b','1',requires=('a',),services={'b':lambda h:factory('b')})])
        self.assertEqual(calls,[])
        manager.require('a');manager.require('b');manager.require('a');manager.close();manager.close()
        self.assertEqual(calls,['open:a','open:b','close:b','close:a'])
    def test_dynamic_construction_cycle_rejected(self):
        manager=PluginManager([Plugin('a','1',services={'a':lambda h:h.require('a')})])
        with self.assertRaises(PluginError):manager.require('a')


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.project=pathlib.Path(self.tmp.name);self.repo=MemoryRepository()
        self.event={'project':str(self.project),'client':'fixture','session':'one','id':'first','type':'tool.before','tool':'Read'}
    def run_plugins(self,plugins,mode='enforce',event=None):
        home=self.project/'state';home.mkdir(exist_ok=True)
        (home/'config.json').write_text(json.dumps({'version':1,'mode':mode}))
        with Supervisor(home,plugins=[memory_plugin(self.repo),*plugins]) as supervisor:
            return supervisor.evaluate(event or self.event)
    def test_local_allow_never_cancels_denial(self):
        r=self.run_plugins([guard('denial'),guard('allow','allow')]);self.assertEqual(r['decision'],'deny')
    def test_authority_allow_never_cancels_local_denial(self):
        r=self.run_plugins([guard(),guard('authority','allow','authority')]);self.assertEqual(r['decision'],'deny')
    def test_observe_softens_local_but_not_external_denial(self):
        r=self.run_plugins([guard(),guard('authority','deny','authority')],mode='observe')
        self.assertEqual(r['decision'],'deny');self.assertEqual(r['would_decision'],'deny')
    def test_baseline_does_not_invoke_evaluators(self):
        def never(ctx):raise AssertionError('must not run')
        r=self.run_plugins([guard(callback=never)],mode='baseline');self.assertEqual(r['decision'],'allow');self.assertEqual(r['runtime_steps'],[])
    def test_baseline_requires_explicit_authority_acknowledgment(self):
        with self.assertRaises(PluginError):
            self.run_plugins([guard('authority', phase='authority')], mode='baseline')
    def test_oversized_contribution_denied_before_persistence(self):
        r=self.run_plugins([guard(callback=lambda c:Assessment(state={'huge':'x'*300000}))])
        self.assertEqual(r['decision'],'deny');self.assertIn('plugin_errors',r)
    def test_audit_conflict_does_not_apply_partial_metadata(self):
        a=guard('a',callback=lambda c:Assessment(audit={'value':1}))
        b=guard('b',callback=lambda c:Assessment(details={'pretend':'success'},audit={'value':2}))
        r=self.run_plugins([a,b]);self.assertEqual(r['decision'],'deny');self.assertNotIn('pretend',r)
    def test_post_action_cannot_claim_to_undo_execution(self):
        r=self.run_plugins([guard()],event={**self.event,'type':'tool.after'});self.assertEqual(r['decision'],'advise')
    def test_invalid_plugin_result_and_exception_fail_closed(self):
        for i,callback in enumerate((lambda ctx:{'decision':'allow'},lambda ctx:1/0)):
            r=self.run_plugins([guard(callback=callback)],event={**self.event,'id':str(i)})
            self.assertEqual(r['decision'],'deny');self.assertIn('plugin_errors',r)
    def test_mutating_context_does_not_change_other_plugin_or_input(self):
        def attempt(ctx):
            ctx.result['decision']='allow';ctx.event['input']={'injected':True};ctx.config['mode']='baseline'
            return Assessment()
        r=self.run_plugins([guard('a'),guard('b',callback=attempt)])
        self.assertEqual(r['decision'],'deny');self.assertNotIn('input',self.event)
    def test_reserved_metadata_cannot_override_runtime_verdict(self):
        r=self.run_plugins([guard(callback=lambda c:Assessment(details={'decision':'allow'}))]);self.assertEqual(r['decision'],'deny')
    def test_observer_cannot_modify_canonical_verdict(self):
        def observer(ctx,result):result['decision']='allow';return {'decision':'allow'}
        r=self.run_plugins([guard(),Plugin('observer','1',observe=observer)])
        self.assertEqual(r['decision'],'deny');self.assertEqual(r['observability_error'],'PluginError')
    def test_duplicate_delivery_does_not_reexecute_evaluator(self):
        calls=[]
        def cb(ctx):calls.append(True);return Assessment()
        plugins=[memory_plugin(self.repo),guard(callback=cb)]
        with Supervisor(self.project/'state',plugins=plugins) as s:
            s.evaluate(self.event);r=s.evaluate(self.event)
        self.assertTrue(r['duplicate']);self.assertEqual(len(calls),1)
    def test_plugin_version_change_requires_fresh_session(self):
        self.run_plugins([guard()])
        with self.assertRaises(PluginError):self.run_plugins([replace(guard(),version='2')])
    def test_core_does_not_import_any_reference_or_optional_feature(self):
        root=str(pathlib.Path(__file__).resolve().parents[1])
        code=r'''
import importlib.abc, sys, tempfile
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'gw_builtin','gw_context','gw_knowledge','gw_observe','gw_learning','gw_sync','sqlite3'}:
            raise AssertionError('Unexpected implementation import: '+fullname)
sys.meta_path.insert(0,Block())
from gw_supervisor.api import Plugin, Advice, Assessment, Evaluator
from gw_supervisor.registry import PluginManager
from gw_supervisor.engine import Supervisor
from test_runtime_plugins import MemoryRepository, memory_plugin
with tempfile.TemporaryDirectory() as tmp:
    with Supervisor(tmp,plugins=[memory_plugin(MemoryRepository()),Plugin('fixture','1',evaluators=(Evaluator('fixture','local',lambda ctx:Assessment((Advice('deny','fixture'),))),))]) as s:
        result=s.evaluate({'project':tmp,'client':'fixture','session':'a','type':'tool.before','tool':'Read','id':'c'})
        assert result['decision']=='deny'
print('core-only-ok')
'''
        env={**os.environ,'PYTHONPATH':os.pathsep.join([root,str(pathlib.Path(root)/'tests')])}
        p=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('core-only-ok',p.stdout)


class ReferenceReplacementTests(unittest.TestCase):
    def test_replace_context_without_editing_agent_or_runtime(self):
        from gw_builtin.agent import AgentService
        from gw_supervisor.registry import STANDARD
        manager=discover(tuple(x for x in STANDARD if x!='gw.context'))
        supplied={'proof':'third-party compiler','model_calls':0}
        def external_tool(host):
            def gw_context_compile(task:str='') -> dict:return {**supplied,'task':task}
            return gw_context_compile
        plugins=[*manager.plugins.values(),Plugin('external.context','1',tools=(Tool('gw_context_compile',external_tool),))]
        custom=PluginManager(plugins)
        with tempfile.TemporaryDirectory() as tmp:
            service=AgentService(pathlib.Path(tmp)/'state',tmp)
            with patch.object(service,'_manager',return_value=custom),patch('gw_supervisor.registry.manager_for',return_value=custom):
                result=service.gw_context_compile(task='fixture')
            self.assertEqual(result,{**supplied,'task':'fixture'})
    def test_project_cannot_select_code(self):
        from gw_supervisor.config import trust_project
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp);(p/'.gw.json').write_text('{"runtime":{"enable":["unexpected"]}}')
            with self.assertRaises(ValueError):trust_project(p/'state',p)
    def test_native_hook_still_denies_when_runtime_configuration_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp);(p/'config.json').write_text('broken JSON')
            event={'cwd':tmp,'session_id':'fixture','tool_use_id':'call','tool_name':'Bash','tool_input':{'command':'echo fixture'}}
            process=subprocess.run([sys.executable,'-m','gw_supervisor','--home',tmp,'hook','claude','pre'],input=json.dumps(event),text=True,capture_output=True,timeout=15)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(json.loads(process.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
    def test_new_plugin_is_not_autoenabled_on_install(self):
        self.assertNotIn('gw.example.review',selection({}))


if __name__=='__main__':unittest.main()
