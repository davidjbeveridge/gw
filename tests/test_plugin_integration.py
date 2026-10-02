import copy
import importlib.util
import io
import json
import pathlib
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock
from gw_supervisor.cli import main
from gw_supervisor.engine import Supervisor
from gw_supervisor.config import DEFAULTS,merge,validate
from gw_supervisor.util import write_json
from gw_supervisor.plugins import trace_repository
from gw_supervisor.proxy import process_request,process_response

@unittest.skipUnless(importlib.util.find_spec('gw_observe'), 'Optional observe package')
class ObservabilityIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.home=self.root/'state';self.project=self.root/'project';self.project.mkdir()
        self.config={'version':1,'plugins':{'observe':{'enabled':True}},'rules':{'canary':{'when':{'tool':'blocked'},'effect':'deny'}}}
        self.save()
    def save(self):write_json(self.home/'config.json',self.config)
    def event(self,typ='tool.before',id='one',**more):return {'type':typ,'id':id,'session':'native','client':'custom','project':str(self.project),'tool':'blocked','input':{'command':'secret original input'},**more}
    def report(self):
        with trace_repository(self.home,merge(DEFAULTS,self.config)) as repo:return repo.report(repo.runs()[0]['id'])
    def test_trace_does_not_call_classifier_when_off(self):
        with mock.patch('gw_supervisor.providers.Classifier.decide',side_effect=AssertionError('No model')),Supervisor(self.home) as s:
            r=s.evaluate(self.event());self.assertEqual(r['decision'],'deny');self.assertIn('audit',r)
            self.assertTrue(s.evaluate(self.event())['duplicate'])
        r=self.report();self.assertEqual(r['intercepts'],1);self.assertEqual(r['classifier_calls'],0)
        self.assertIsNone(r['usage']['cost_usd']);self.assertTrue(r['goal_evaluations'])
    def test_baseline_changes_nothing_and_no_inference(self):
        self.config.update(mode='baseline',proxy={'inject_task':True,'compact_tool_json':True,'max_output_tokens':1});self.save()
        with Supervisor(self.home,classifier=mock.Mock(side_effect=AssertionError())) as s:
            r=s.evaluate(self.event());self.assertEqual(r['decision'],'allow');self.assertTrue(all(g['status']=='baseline_not_evaluated' for g in r['audit']['goals']))
            payload={'model':'original','messages':[{'role':'user','content':'Do the task'}],'max_tokens':100}
            transformed=process_request(s,{'client':'custom','project':str(self.project),'session':'native','id':'request'},payload)
            self.assertEqual(transformed['payload'],payload)
        self.assertEqual(self.report()['classifier_calls'],0)
    def test_baseline_cannot_bypass_authority(self):
        c=merge(DEFAULTS,{'mode':'baseline','authority':{'endpoint':'https://authority.example/authorize'}})
        with self.assertRaises(ValueError):validate(c)
    def test_per_goal_classification_count(self):
        class Model:
            last_usage={'input_tokens':12,'output_tokens':2}
            def decide(self,state,goals):return {k:next(iter(g['choices'])) for k,g in goals.items()}
        with Supervisor(self.home,classifier=Model()) as s:
            s.store.set_task(str(self.project),'Do the task')
            r=s.evaluate(self.event(tool='Read'))
            self.assertEqual(len(r['audit']['classifier_calls']),1)
        r=self.report();self.assertEqual(r['classifier_calls'],1);self.assertEqual(r['supervisor_usage']['input_tokens'],12)
    def test_usage_and_original_response_preserved(self):
        with Supervisor(self.home) as s:
            context={'client':'custom','project':str(self.project),'session':'native','id':'request','cost_usd':.01}
            response={'model':'m','usage':{'input_tokens':10,'output_tokens':5,'output_tokens_details':{'reasoning_tokens':3}},'choices':[]}
            r=process_response(s,context,response);self.assertEqual(r['payload'],response)
            process_response(s,context,response)
        report=self.report();self.assertEqual(report['usage']['input_tokens'],10);self.assertEqual(report['usage']['cost_usd'],.01)
    def test_missing_source_keeps_compact_goals(self):
        with Supervisor(self.home) as s:s.evaluate(self.event())
        (self.home/'state.sqlite3').unlink()
        r=self.report();self.assertEqual(r['missing_source_records'],1);self.assertTrue(r['goal_evaluations'])
    def test_optional_logger_failure_not_policy_change(self):
        with mock.patch('gw_supervisor.plugins.trace_repository',side_effect=OSError('full disk')),Supervisor(self.home) as s:
            r=s.evaluate(self.event());self.assertEqual(r['decision'],'deny');self.assertEqual(r['observability_error'],'OSError')
    def test_explicit_run_binding_and_manual_comparison(self):
        def command(*a):
            out=io.StringIO()
            with redirect_stdout(out):main(['--home',str(self.home),'trace','--project',str(self.project),*a])
            return json.loads(out.getvalue())
        a=command('start','--harness','custom','--model','one','--bind')
        with Supervisor(self.home) as s:s.evaluate(self.event())
        command('finish',a['id'],'--outcome','partial')
        b=command('start','--harness','other','--model','two')
        result=command('compare',a['id'],b['id']);self.assertFalse(result['causal_claim']);self.assertEqual(result['reports'][0]['intercepts'],1)
    def test_knowledge_operations_traced_without_payload_copy(self):
        if not importlib.util.find_spec('gw_knowledge'):self.skipTest('Optional knowledge')
        from gw_supervisor.knowledge import open_service
        self.config['knowledge']={'enabled':True,'allow_writes':True};self.save()
        with open_service(self.home,self.project,'custom') as svc:
            scope=svc.scope.to_dict();svc.dispatch('put',{'scope':scope,'document':{'document_id':'d','title':'Title','text':'UNIQUE_KNOWLEDGE needle','source':'file:///fixture'}})
            svc.dispatch('context',{'scope':scope,'query':'needle'});svc.dispatch('context',{'scope':scope,'query':'needle'})
        with trace_repository(self.home,merge(DEFAULTS,self.config)) as repo:
            reports=[repo.report(r['id']) for r in repo.runs()]
            self.assertEqual(sum(r['context_cache'].get('hit',0) for r in reports),1)
            self.assertNotIn('UNIQUE_KNOWLEDGE',str([tuple(r) for r in repo.db.execute('SELECT attributes FROM observations')]))
    def test_project_cannot_enable_plugins(self):
        from gw_supervisor.config import trust_project
        write_json(self.project/'.gw.json',{'plugins':{'observe':{'enabled':True}}})
        with self.assertRaises(ValueError):trust_project(self.home,self.project)
