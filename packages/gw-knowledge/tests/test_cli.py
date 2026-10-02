import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from gw_knowledge import DocumentInput, LocalKnowledgeProvider, Scope


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.file=self.root/'source.md';self.file.write_text('needle source evidence',encoding='utf-8')
    def cli(self,*args,store=None):
        return subprocess.run([sys.executable,'-m','gw_knowledge','--store',str(store or self.root/'store'),'--collection','demo',*args],capture_output=True,text=True,timeout=15)
    def test_ingest_search_context_and_export_restore(self):
        self.assertEqual(self.cli('ingest',str(self.file),'--id','doc').returncode,0)
        result=json.loads(self.cli('search','needle').stdout);self.assertEqual(result['hits'][0]['document_id'],'doc')
        self.assertFalse(json.loads(self.cli('context','needle').stdout)['cache']['hit'])
        self.assertTrue(json.loads(self.cli('context','needle').stdout)['cache']['hit'])
        exported=self.cli('export');self.assertEqual(exported.returncode,0,exported.stderr)
        backup=self.root/'sources.jsonl';backup.write_text(exported.stdout,encoding='utf-8')
        restored=self.cli('restore',str(backup),store=self.root/'other');self.assertEqual(restored.returncode,0,restored.stderr)
        self.assertEqual(json.loads(self.cli('search','needle',store=self.root/'other').stdout)['hits'][0]['text'],'needle source evidence')
    def test_update_requires_revision(self):
        before=json.loads(self.cli('ingest',str(self.file),'--id','doc').stdout)
        self.file.write_text('needle updated',encoding='utf-8')
        self.assertEqual(self.cli('ingest',str(self.file),'--id','doc').returncode,2)
        self.assertEqual(self.cli('ingest',str(self.file),'--id','doc','--expected-revision',before['revision']).returncode,0)
    def test_semantic_mode_is_not_faked(self):
        r=self.cli('search','needle','--mode','semantic');self.assertEqual(r.returncode,2);self.assertIn('unsupported',r.stderr)
    def test_cache_clear_retains_source(self):
        self.cli('ingest',str(self.file),'--id','doc');self.cli('context','needle')
        self.assertFalse(json.loads(self.cli('cache-clear').stdout)['sources_deleted'])
        self.assertTrue(json.loads(self.cli('search','needle').stdout)['hits'])
    def test_json_metadata_filters(self):
        self.cli('ingest',str(self.file),'--id','doc','--metadata','{"type":"docs"}')
        self.assertTrue(json.loads(self.cli('search','--mode','structured','--filters','{"type":"docs"}').stdout)['hits'])
    def test_version_independent(self):
        r=subprocess.run([sys.executable,'-m','gw_knowledge','--version'],capture_output=True,text=True,check=True)
        self.assertEqual(r.stdout.strip(),'0.2.0')
    def test_sources_are_not_automatically_rescanned(self):
        self.cli('ingest',str(self.file),'--id','doc')
        self.file.write_text('changed outside storage',encoding='utf-8')
        self.assertEqual(json.loads(self.cli('read','doc').stdout)['text'],'needle source evidence')
    def test_ingestion_preserves_crlf(self):
        self.file.write_bytes(b'needle\r\nnext\r\n')
        self.cli('ingest',str(self.file),'--id','doc')
        self.assertEqual(json.loads(self.cli('read','doc').stdout)['text'],'needle\r\nnext\r\n')

    def test_legacy_console_preserves_unicode_json(self):
        self.file.write_text('needle → 🐱 naïve',encoding='utf-8')
        self.cli('ingest',str(self.file),'--id','unicode')
        env={**os.environ,'PYTHONIOENCODING':'cp1252'}
        run=subprocess.run([sys.executable,'-m','gw_knowledge','--store',str(self.root/'store'),'--collection','demo','context','needle'],capture_output=True,env=env,check=True)
        self.assertEqual(json.loads(run.stdout.decode('ascii'))['evidence'][0]['text'],'needle → 🐱 naïve')
