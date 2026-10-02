import copy
import json
import pathlib
import sys
import tempfile
import unittest
from gw_learning.engine import LearningCoordinator,DEFAULTS,canonical

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.events=[]
        self.c=LearningCoordinator(self.root/'learn',observer=lambda *x:self.events.append(x));self.addCleanup(self.c.close)
        self.context={'as_of':10000,'repetitions':[{'action_hash':'hash','tool':'Bash','successes':3,'reference':'source:one'}],
                      'goal_patterns':[{'id':'alignment','interventions':3,'evidence':['source:two']}]}
    def test_defaults_do_not_execute(self):
        r=self.c.run(self.context);self.assertEqual(len(r['proposals']),2)
        self.assertTrue(all(p['status']=='proposed' for p in self.c.list()))
    def test_repeat_idempotence(self):
        self.c.run(self.context);r=self.c.run(self.context)
        self.assertTrue(all(not p['new'] for p in r['proposals']));self.assertEqual(len(self.c.list()),2)
    def test_off_and_strategy_scope(self):
        self.c.configure({'mode':'off'});self.assertEqual(self.c.run(self.context)['status'],'disabled')
        self.c.configure({'strategies':['expansion']});self.assertEqual(self.c.run(self.context)['proposals'],[])
    def test_reviewed_publication_is_not_activation(self):
        pid=self.c.run(self.context)['proposals'][0]['id']
        with self.assertRaises(ValueError):self.c.promote(pid,self.root/'out')
        self.c.review(pid,True);r=self.c.promote(pid,self.root/'out')
        self.assertEqual(self.c.get(pid)['status'],'published');self.assertTrue((self.root/'out').exists())
        self.assertTrue(self.events)
    def test_rejection_not_rerun(self):
        pid=self.c.run(self.context)['proposals'][0]['id'];self.c.review(pid,False)
        with self.assertRaises(ValueError):self.c.review(pid,True)
    def test_research_only_explicit_topics(self):
        self.c.configure({'plugins':{'research':{'enabled':True}},'strategies':['expansion']})
        self.assertEqual(self.c.run(self.context)['proposals'],[])
    def research(self,code='import json,sys; x=json.load(sys.stdin); print(json.dumps({"report":"Fixture research result","sources":[],"usage":{"input_tokens":0}}))',mode='propose',timeout=2):
        worker=self.root/'worker.py';worker.write_text(code)
        return self.c.configure({'mode':mode,'strategies':['expansion'],'plugins':{'research':{'enabled':True,'topics':[{'id':'topic','query':'Only this explicit topic'}],'interval_seconds':3600}},'executor':{'argv':[sys.executable,str(worker)],'timeout_seconds':timeout}})
    def test_real_local_worker_requires_approval(self):
        self.research();pid=self.c.run(self.context)['proposals'][0]['id']
        with self.assertRaises(ValueError):self.c.execute(pid)
        self.c.review(pid,True);result=self.c.execute(pid)
        self.assertEqual(result['status'],'succeeded');self.assertIn('Fixture',result['result']['report'])
        with self.assertRaises(ValueError):self.c.execute(pid)
    def test_auto_only_authorized_research(self):
        self.research(mode='auto');self.c.run(self.context)
        self.assertEqual(self.c.list()[0]['status'],'succeeded')
    def test_worker_timeout(self):
        self.research('import time;time.sleep(30)',timeout=1);pid=self.c.run(self.context)['proposals'][0]['id'];self.c.review(pid,True)
        self.assertEqual(self.c.execute(pid)['status'],'failed')
    def test_worker_output_budget(self):
        self.research('print("x"*2000000)');pid=self.c.run(self.context)['proposals'][0]['id'];self.c.review(pid,True)
        self.assertEqual(self.c.execute(pid)['status'],'failed')
    def test_config_change_invalidates_worker_approval(self):
        config=self.research();pid=self.c.run(self.context)['proposals'][0]['id'];self.c.review(pid,True)
        config['lookback_days']=30;self.c.configure(config)
        with self.assertRaises(ValueError):self.c.execute(pid)
    def test_publication_does_not_overwrite(self):
        pid=self.c.run(self.context)['proposals'][0]['id'];self.c.review(pid,True)
        self.c.promote(pid,self.root/'out')
        with self.assertRaises(ValueError):self.c.promote(pid,self.root/'out')
    def test_bad_modes_and_cadence(self):
        with self.assertRaises(ValueError):self.c.configure({'promotion':'auto'})
        self.c.configure({'strategies':['expansion'],'plugins':{'research':{'enabled':True,'topics':[{'id':'a','query':'q'}],'interval_seconds':1}}})
        self.assertEqual(self.c.run(self.context)['status'],'partial')
    def test_observer_failure_not_state_failure(self):
        self.c.observer=lambda *a:(_ for _ in ()).throw(RuntimeError('offline'))
        self.assertEqual(len(self.c.run(self.context)['proposals']),2)

    def test_guidance_worker_is_explicitly_allowed(self):
        config=self.research();config['strategies']=['thematic'];config['executor']['allowed_kinds']=['guidance']
        self.c.configure(config);items=self.c.run(self.context)['proposals']
        for item in items:
            self.c.review(item['id'],True)
            if item['kind']=='guidance':self.assertEqual(self.c.execute(item['id'])['status'],'succeeded')
            else:
                with self.assertRaises(ValueError):self.c.execute(item['id'])

    def test_config_change_can_create_a_fresh_reviewable_proposal(self):
        old=self.c.run(self.context)['proposals'][0]['id']
        self.c.configure({'lookback_days':30})
        new=self.c.run(self.context)['proposals']
        self.assertTrue(all(x['id']!=old for x in new))
        self.assertTrue(all(x['new'] for x in new))
