import json
import pathlib
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from gw_observe.store import LocalTraceRepository
from gw_observe.server import make_server
from gw_observe.otlp import send

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        with LocalTraceRepository(self.root) as repo:self.run=repo.start('Fixture',str(self.root),harness='fixture')
        self.server=make_server(self.root);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def stop(self):self.server.shutdown();self.thread.join();self.server.server_close()
    def get(self,path,headers=None):
        req=urllib.request.Request(self.url+path,headers=headers or {})
        return urllib.request.urlopen(req)
    def test_dashboard_assets_and_csp(self):
        with self.get('/') as response:
            self.assertIn('frame-ancestors',response.headers['Content-Security-Policy']);self.assertIn('Observability',response.read().decode())
    def test_api_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.get('/api/runs')
        self.assertEqual(e.exception.code,401)
    def test_authenticated_run_report(self):
        with self.get('/api/report/'+self.run['id'],{'Authorization':'Bearer '+self.server.token}) as r:
            data=json.load(r);self.assertIsNone(data['usage']['cost_usd'])
    def test_cross_origin_and_rebinding_rejected(self):
        for headers in ({'Authorization':'Bearer '+self.server.token,'Origin':'https://evil.example'}, {'Host':'evil.example'}):
            with self.assertRaises(urllib.error.HTTPError):self.get('/api/runs',headers)
    def test_arbitrary_source_path_not_served(self):
        with self.assertRaises(urllib.error.HTTPError):self.get('/api/source?path=/etc/passwd',{'Authorization':'Bearer '+self.server.token})
    def test_writes_not_exposed(self):
        req=urllib.request.Request(self.url+'/api/record',b'{}',{'Authorization':'Bearer '+self.server.token})
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,405)
    def test_real_otlp_receipt_and_partial_failure(self):
        from http.server import BaseHTTPRequestHandler,HTTPServer
        responses=[{}, {'partialSuccess':{'rejectedSpans':'1'}}];seen=[]
        class H(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));out=json.dumps(responses.pop(0)).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(out)));self.end_headers();self.wfile.write(out)
        server=HTTPServer(('127.0.0.1',0),H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            endpoint=f'http://127.0.0.1:{server.server_port}/v1/traces'
            self.assertTrue(send({'resourceSpans':[]},endpoint)['accepted'])
            with self.assertRaises(ValueError):send({'resourceSpans':[]},endpoint)
            self.assertEqual(len(seen),2)
        finally:server.shutdown();thread.join();server.server_close()
