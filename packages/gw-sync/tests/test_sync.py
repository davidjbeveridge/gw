import copy
import json
import os
import pathlib
import tempfile
import unittest
from gw_sync.store import *

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.src=self.root/'src';self.src.mkdir();(self.src/'SKILL.md').write_text('Use explicit evidence.')
        self.store=LocalBundleStore(self.root/'store');self.addCleanup(self.store.close);self.dest=self.root/'dest'
    def pack(self,expected=None):return pack(self.store,self.src,['*.md'],channel='team',expected=expected)
    def test_pack_plan_apply(self):
        pushed=self.pack();p=plan(self.store,'team',self.dest);self.assertEqual(p['conflicts'],0)
        result=apply(self.store,p);self.assertEqual((self.dest/'SKILL.md').read_text(),'Use explicit evidence.')
        self.assertIn('not_performed',result['agent_activation'])
    def test_content_dedup_and_channel_cas(self):
        a=self.pack();self.assertEqual(self.pack()['reference'],a['reference'])
        (self.src/'SKILL.md').write_text('New guidance')
        with self.assertRaises(ValueError):self.pack()
        b=self.pack(a['reference']);self.assertNotEqual(a['reference'],b['reference'])
        self.assertEqual(len(list((self.root/'store/blobs').glob('*/*'))),2)
    def test_destination_conflict_is_not_overwritten(self):
        self.pack();self.dest.mkdir();(self.dest/'SKILL.md').write_text('Local edits')
        p=plan(self.store,'team',self.dest);self.assertEqual(p['conflicts'],1)
        with self.assertRaises(ValueError):apply(self.store,p)
        self.assertEqual((self.dest/'SKILL.md').read_text(),'Local edits')
    def test_stale_plan_rejected(self):
        self.pack();p=plan(self.store,'team',self.dest);self.dest.mkdir();(self.dest/'SKILL.md').write_text('Changed after review')
        with self.assertRaises(ValueError):apply(self.store,p)
    def test_unmodified_previous_version_updates(self):
        old=self.pack();apply(self.store,plan(self.store,'team',self.dest))
        (self.src/'SKILL.md').write_text('New');self.pack(old['reference']);p=plan(self.store,'team',self.dest)
        self.assertEqual(p['changes'][0]['status'],'update');apply(self.store,p);self.assertEqual((self.dest/'SKILL.md').read_text(),'New')
    def test_plan_tamper_rejected(self):
        self.pack();p=plan(self.store,'team',self.dest);p['destination']=str(self.root/'other')
        with self.assertRaises(ValueError):apply(self.store,p)
    def test_paths_reject_escape(self):
        for path in ('../file','/etc/passwd','C:/x','a\\b','a/../b','a/./b',''):
            with self.subTest(path=path),self.assertRaises(ValueError):safe_path(path)
    def test_secrets_not_synchronized(self):
        for name,data in [('.env',b'X=1'),('sessions.jsonl',b'{}'),('config.json',b'{"api_key":"literal-secret"}')]:
            with self.subTest(name=name),self.assertRaises(ValueError):scan(name,data)
        scan('config.json',b'{"api_key":"os.environ/API_KEY"}')
    def test_corrupt_blob_rejected(self):
        ref=self.pack();m=self.store.resolve(ref['reference'])['manifest'];h=m['files'][0]['hash'];(self.root/'store/blobs'/h[:2]/h).write_text('corrupted')
        with self.assertRaises(ValueError):plan(self.store,'team',self.dest)
    def test_symlink_refused(self):
        if os.name=='nt':self.skipTest('Symlink privileges not assumed on Windows')
        (self.src/'link.md').symlink_to(self.src/'SKILL.md')
        with self.assertRaises(ValueError):self.pack()
    def test_case_collision_refused(self):
        m={'protocol':PROTOCOL,'files':[{'path':p,'hash':'a'*64,'size':1,'executable':False} for p in ['A.md','a.md']]}
        with self.assertRaises(ValueError):self.store.validate(m)
    def test_provider_need_not_own_local_application_state(self):
        class Remote:
            def __init__(self):self.blobs={};self.bundle=None
            def put_blob(self,data):h=sha(data);self.blobs[h]=data;return h
            def get_blob(self,h):return self.blobs[h]
            def publish(self,m,*,channel,expected):self.bundle={'reference':hash_json(m),'manifest':m};return {'reference':hash_json(m),'channel':channel}
            def resolve(self,r):return self.bundle
        remote=Remote()
        with SyncWorkspace(remote,self.root/'workspace') as workspace:
            pack(workspace,self.src,['*.md'],channel='a');apply(workspace,plan(workspace,'a',self.dest))
            self.assertTrue((self.dest/'SKILL.md').exists());self.assertTrue(workspace.history())
    def test_noncooperative_provider_hash_checked(self):
        class Bad:
            def resolve(self,r):return {'reference':'a'*64,'manifest':{'protocol':PROTOCOL,'files':[]}}
        with SyncWorkspace(Bad(),self.root/'workspace') as workspace:
            with self.assertRaises(ValueError):workspace.resolve('whatever')
    def test_cooperative_lock(self):
        self.pack();p=plan(self.store,'team',self.dest)
        with destination_lock(self.dest):
            with self.assertRaises(FileExistsError):apply(self.store,p)

class HttpSyncTests(unittest.TestCase):
    def test_actual_remote_provider_and_cas(self):
        from gw_sync.http import make_server,HttpBundleProvider
        import threading
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp).resolve();server=make_server(root/'server','fixture-sync-token-at-least-20-chars',writable=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with mock.patch.dict(os.environ,{'GW_SYNC_TOKEN':'fixture-sync-token-at-least-20-chars'}):
                    source=root/'src';source.mkdir();(source/'SKILL.md').write_text('Portable guidance')
                    provider=HttpBundleProvider(f'http://127.0.0.1:{server.server_port}/v1/bundles')
                    with SyncWorkspace(provider,root/'client-state') as client:
                        pushed=pack(client,source,['*.md'],channel='team')
                        result=apply(client,plan(client,'team',root/'destination'))
                        self.assertTrue(result['applied']);self.assertEqual((root/'destination/SKILL.md').read_text(),'Portable guidance')
                        (source/'SKILL.md').write_text('Changed')
                        with self.assertRaises(ValueError):pack(client,source,['*.md'],channel='team')
                        self.assertNotEqual(pack(client,source,['*.md'],channel='team',expected=pushed['reference'])['reference'],pushed['reference'])
            finally:server.shutdown();thread.join();server.server_close()
