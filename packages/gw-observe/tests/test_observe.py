"""Deterministic local traces and wire contracts. No model/service accounts."""
import dataclasses
import json
import os
import pathlib
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest import mock
from gw_observe.contract import *
from gw_observe.store import LocalTraceRepository
from gw_observe.importers import import_transcript
from gw_observe.otlp import export,send

class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.repo=LocalTraceRepository(self.root/'obs');self.addCleanup(self.repo.close)
        self.run=self.repo.start('Fixture',str(self.root),harness='custom',model='fixture',mode='baseline')
    def event(self,id='one',kind='model.usage',attrs=None,session='session',run=None):
        at=self.run['started_ns']+100
        return {'protocol':PROTOCOL,'id':id,'run_id':run or self.run['id'],'session_id':session,'kind':kind,'start_ns':at,'end_ns':at+10,'attributes':attrs or {},'source':{}}

class TraceTests(Fixture):
    def test_metadata_idempotence(self):
        self.assertTrue(self.repo.record(self.event()));self.assertFalse(self.repo.record(self.event()))
        self.assertEqual(self.repo.report(self.run['id'])['events'],1)
    def test_unknown_cost_and_tokens_are_null(self):
        self.repo.record(self.event());r=self.repo.report(self.run['id'])
        self.assertIsNone(r['usage']['cost_usd']);self.assertIsNone(r['usage']['input_tokens']);self.assertIsNone(r['elapsed_seconds'])
    def test_finish_is_explicit_immutable(self):
        result=self.repo.finish(self.run['id'],'succeeded','operator checked tests')
        self.assertEqual(result['outcome'],'succeeded');self.assertEqual(result['evidence']['asserted_by'],'operator')
        with self.assertRaises(ValueError):self.repo.finish(self.run['id'])
    def test_cross_run_id_rejected(self):
        other=self.repo.start('Other',str(self.root),harness='custom')
        self.repo.record(self.event())
        with self.assertRaises(ValueError):self.repo.record(self.event(run=other['id']))
    def test_session_binding_pinned(self):
        self.assertEqual(self.repo.bind_session('s',str(self.root),'custom',run_id=self.run['id']),self.run['id'])
        other=self.repo.start('Other',str(self.root),harness='custom')
        with self.assertRaises(ValueError):self.repo.bind_session('s',str(self.root),'custom',run_id=other['id'])
    def test_metadata_comparison_exposes_variables(self):
        other=self.repo.start('Other',str(self.root),harness='other',model='another')
        result=self.repo.compare([self.run['id'],other['id']])
        self.assertFalse(result['causal_claim']);self.assertIn('model',result['differences'][0]['changed_variables'])
    def test_overlapping_capture_lanes_not_summed(self):
        self.repo.record(self.event(attrs={'usage':{'input_tokens':100,'output_tokens':20},'usage_source':'proxy','model':'a'}))
        self.repo.record(self.event('copy',attrs={'usage':{'input_tokens':100,'output_tokens':20},'usage_source':'claude-jsonl','model':'a'}))
        result=self.repo.report(self.run['id']);self.assertEqual(result['usage']['input_tokens'],100)
        self.assertEqual(len(result['usage_ambiguities']),1)
    def test_subsets_not_double_counted(self):
        raw={'input_tokens':100,'output_tokens':40,'input_tokens_details':{'cached_tokens':75},'output_tokens_details':{'reasoning_tokens':30}}
        u=normalize_usage(raw);self.assertEqual(u['input_tokens'],100);self.assertEqual(u['output_tokens'],40)
        self.assertEqual(u['cache_read_input_tokens'],75)
    def test_anthropic_normalized_once(self):
        self.assertEqual(normalize_usage({'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':30},'anthropic')['input_tokens'],60)
    def test_invalid_counters_not_invented(self):
        self.assertEqual(normalize_usage({'input_tokens':True,'output_tokens':-2,'cost_usd':float('nan')}),{})
    def test_tool_entity_dedup(self):
        self.repo.record(self.event('a','agent.tool',{'tool_class':'cli','tool_call_id':'call'}))
        self.repo.record(self.event('b','gw.intercept',{'tool_class':'cli','tool_call_id':'call','event_type':'tool.before','decision':'deny'}))
        self.repo.record(self.event('c','agent.tool_result',{'tool_call_id':'call','success':False}))
        r=self.repo.report(self.run['id']);self.assertEqual(r['tools'],{'cli':1});self.assertEqual(r['denied_then_observed_executing'],1)
    def test_goal_metadata_survives_source_removal(self):
        e=self.event(kind='gw.intercept',attrs={'decision':'deny','goal_index':[{'id':'alignment','status':'evaluated','effect':'deny'}]})
        e['source']={'source_id':'missing'};self.repo.record(e)
        r=self.repo.report(self.run['id']);self.assertEqual(r['goal_evaluations']['alignment']['deny'],1);self.assertEqual(r['missing_source_records'],1)
    def test_time_and_metadata_validation(self):
        e=self.event();e['end_ns']=0
        with self.assertRaises(ValueError):self.repo.record(e)
        e=self.event();e['protocol']='wrong'
        with self.assertRaises(ValueError):self.repo.record(e)
    def test_source_only_registered_paths(self):
        self.assertEqual(self.repo.source({'path':'/etc/passwd'})['status'],'unregistered')
    def test_prompt_capture_optin(self):
        p=self.root/'prompt';p.write_text('unique prompt content')
        r=self.repo.start('prompt',str(self.root),harness='custom',prompt_file=p)
        self.assertNotIn('snapshot',r['manifest']['prompt'])
        self.assertNotIn('unique prompt content',(self.root/'obs/traces.sqlite3').read_bytes().decode(errors='ignore'))
    def test_otlp_json_shape(self):
        self.repo.record(self.event(attrs={'model':'fixture','usage':{'input_tokens':10,'output_tokens':5},'usage_source':'declared'}))
        result=export(self.repo,[self.run['id']]);spans=result['resourceSpans'][0]['scopeSpans'][0]['spans']
        self.assertEqual(len(spans),2)
        for span in spans:
            self.assertEqual(len(span['traceId']),32);int(span['traceId'],16)
            self.assertEqual(len(span['spanId']),16);self.assertIsInstance(span['kind'],int);self.assertIsInstance(span['startTimeUnixNano'],str)
        self.assertIn('gen_ai.usage.input_tokens',str(result));self.assertNotIn('prompt',str(result))
    def test_otlp_unsafe_endpoint(self):
        for endpoint in ('http://remote.test/v1/traces','https://token@host/v1/traces','https://host?key=x'):
            with self.assertRaises(ValueError):send({},endpoint)

class ImportTests(Fixture):
    def write(self,records):
        p=self.root/'session.jsonl';p.write_text(''.join(json.dumps(x)+'\n' for x in records));return p
    def test_claude_turn_usage_source_and_no_payload_copy(self):
        p=self.write([{'type':'assistant','sessionId':'native','uuid':'uuid','message':{'id':'m1','model':'claude-fixture','usage':{'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':20},'content':[{'type':'tool_use','id':'call','name':'Bash','input':{'command':'UNIQUE_PRIVATE_ARGUMENT'}}]}}])
        a=import_transcript(self.repo,self.run['id'],p,'claude-jsonl');b=import_transcript(self.repo,self.run['id'],p,'claude-jsonl')
        self.assertGreater(a['inserted'],0);self.assertEqual(b['inserted'],0);self.assertEqual(b['revised'],0)
        result=self.repo.report(self.run['id']);self.assertEqual(result['usage']['input_tokens'],30);self.assertEqual(result['observed_model_turns'],1)
        self.assertNotIn('UNIQUE_PRIVATE_ARGUMENT',str(list(self.repo.db.execute('SELECT attributes FROM observations'))))
        event=self.repo.timeline(self.run['id'])['events'][0];self.assertEqual(self.repo.event(event['id'])['detail']['status'],'available')
        p.write_text('deleted original');self.assertEqual(self.repo.event(event['id'])['detail']['status'],'changed')
    def test_cumulative_codex_counts_once(self):
        def count(i,o):return {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':i,'output_tokens':o}}}}
        p=self.write([{'type':'session_meta','payload':{'id':'native'}},count(100,20),count(100,20),count(150,30)])
        result=import_transcript(self.repo,self.run['id'],p,'codex-jsonl')
        self.assertEqual(result['duplicate_counters'],1);r=self.repo.report(self.run['id']);self.assertEqual(r['usage']['input_tokens'],150);self.assertIsNone(r['observed_model_turns'])
    def test_revision_import_idempotent(self):
        def msg(n):return {'type':'assistant','sessionId':'n','message':{'id':'m','usage':{'input_tokens':10,'output_tokens':n},'content':[]}}
        p=self.write([msg(1)]);import_transcript(self.repo,self.run['id'],p,'claude-jsonl')
        p=self.write([msg(2)]);self.assertGreater(import_transcript(self.repo,self.run['id'],p,'claude-jsonl')['revised'],0)
        self.assertEqual(import_transcript(self.repo,self.run['id'],p,'claude-jsonl')['revised'],0)
        self.assertEqual(self.repo.report(self.run['id'])['usage']['output_tokens'],2)
    def test_import_cannot_reassign_run(self):
        p=self.write([{'type':'assistant','sessionId':'n','message':{'id':'m','usage':{'input_tokens':10},'content':[]}}])
        import_transcript(self.repo,self.run['id'],p,'claude-jsonl');other=self.repo.start('Other',str(self.root),harness='custom')
        with self.assertRaises(ValueError):import_transcript(self.repo,other['id'],p,'claude-jsonl')
    def test_counter_reset_reported(self):
        p=self.write([{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':n}}}} for n in (100,10,20)])
        result=import_transcript(self.repo,self.run['id'],p,'codex-jsonl');self.assertEqual(result['counter_resets'],1)
