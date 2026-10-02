"""Optional standalone-package bridge. Core remains usable without the package."""
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import threading
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest import mock
from gw_supervisor.cli import main
from gw_supervisor.config import DEFAULTS,resolve,trust_project
from gw_supervisor.knowledge import call
from gw_supervisor.util import write_json


@unittest.skipUnless(importlib.util.find_spec('gw_knowledge'),'Optional gw-knowledge package not installed')
class KnowledgeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name);self.home=self.root/'state';self.project=self.root/'project'
        self.project.mkdir();(self.project/'.git').mkdir()
        self.source=self.project/'source.md';self.source.write_text('needle evidence',encoding='utf-8')
    def cli(self,*args):
        out=io.StringIO()
        with redirect_stdout(out):main(['--home',str(self.home),'knowledge','--project',str(self.project),*args])
        return json.loads(out.getvalue())
    def test_default_core_does_not_enable_knowledge(self):
        self.assertFalse(DEFAULTS['knowledge']['enabled'])
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.cli('search','needle')
    def test_local_setup_and_cross_client_context(self):
        self.cli('init','--collection','shared-project')
        self.cli('ingest',str(self.source),'--id','doc')
        a=call(self.home,{'project':str(self.project),'client':'claude'},'context',{'query':'needle'})['result']
        b=call(self.home,{'project':str(self.project),'client':'codex'},'context',{'query':'needle'})['result']
        self.assertFalse(a['cache']['hit']);self.assertTrue(b['cache']['hit'])
        self.assertEqual(a['scope']['collection'],'shared-project')
    def test_project_isolation(self):
        self.cli('init');self.cli('ingest',str(self.source),'--id','doc')
        other=self.root/'other';other.mkdir()
        r=call(self.home,{'project':str(other)},'search',{'query':'needle'})
        self.assertEqual(r['result']['hits'],[])
    def test_project_cannot_redirect_backend(self):
        write_json(self.project/'.gw.json',{'knowledge':{'provider':'http','options':{'endpoint':'https://evil.test'}}})
        with self.assertRaises(ValueError):trust_project(self.home,self.project)
    def test_scope_cannot_be_supplied_by_api_request(self):
        self.cli('init')
        with self.assertRaises(ValueError):call(self.home,{'project':str(self.project)},'search',{'query':'a','scope':{'tenant':'other'}})
    def test_readonly_connection_blocks_ingest(self):
        self.cli('init','--read-only')
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.cli('ingest',str(self.source),'--id','doc')
    def test_preserves_existing_supervisor_goals(self):
        write_json(self.home/'config.json',{'version':1,'goals':{'retry_limit':{'threshold':5}}})
        self.cli('init')
        self.assertEqual(resolve(self.home,self.project,'generic')[0]['goals']['retry_limit']['threshold'],5)
    def test_locked_knowledge_configuration_not_overridden(self):
        write_json(self.home/'config.json',{'version':1,'locked':['knowledge'],'knowledge':DEFAULTS['knowledge']})
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):self.cli('init')
    def test_export_is_jsonl(self):
        self.cli('init');self.cli('ingest',str(self.source),'--id','doc');self.cli('ingest',str(self.source),'--id','doc2')
        out=io.StringIO()
        with redirect_stdout(out):main(['--home',str(self.home),'knowledge','--project',str(self.project),'export'])
        self.assertEqual(len(out.getvalue().splitlines()),2)
        self.assertEqual({json.loads(line)['document_id'] for line in out.getvalue().splitlines()},{'doc','doc2'})
    def test_no_automatic_event_or_policy_writes(self):
        self.cli('init');before=(self.home/'config.json').read_bytes()
        self.cli('ingest',str(self.source),'--id','doc');self.cli('context','needle')
        self.assertEqual(before,(self.home/'config.json').read_bytes())
        self.assertFalse((self.home/'state.sqlite3').exists())
    def test_http_gw_bridge(self):
        from gw_supervisor.server import make_server
        import urllib.request
        self.cli('init');self.cli('ingest',str(self.source),'--id','doc')
        server=make_server(self.home,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            data={'context':{'project':str(self.project)},'method':'context','request':{'query':'needle'}}
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v1/knowledge',json.dumps(data).encode(),{'Authorization':'Bearer '+(self.home/'api-token').read_text(),'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:result=json.load(response)
            self.assertEqual(result['result']['evidence'][0]['text'],'needle evidence')
        finally:
            server.shutdown();thread.join();server.server_close()

    def test_legacy_console_json_preserves_unicode(self):
        import subprocess,sys
        self.cli('init');self.source.write_text('needle → 🐱 naïve',encoding='utf-8')
        self.cli('ingest',str(self.source),'--id','unicode')
        env={**os.environ,'PYTHONIOENCODING':'cp1252'}
        for command in (['context','needle'],['export']):
            run=subprocess.run([sys.executable,'-m','gw_supervisor','--home',str(self.home),'knowledge','--project',str(self.project),*command],capture_output=True,env=env,check=True)
            result=json.loads(run.stdout.decode('ascii'))
            self.assertEqual(result['evidence'][0]['text'] if command[0]=='context' else result['text'],'needle → 🐱 naïve')
