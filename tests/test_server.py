import json
import pathlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from gw_supervisor.server import make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'state'
        self.project = self.root / 'project'
        self.project.mkdir()
        self.server = make_server(self.home, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.token = (self.home / 'api-token').read_text()
    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
    def request(self, path, body=None, authenticated=True, headers=None):
        h = {'Content-Type': 'application/json'}
        if authenticated:
            h['Authorization'] = 'Bearer ' + self.token
        h.update(headers or {})
        req = urllib.request.Request(self.url + path, json.dumps(body).encode() if body is not None else None, h)
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)
    def event(self):
        return {'type': 'tool.before', 'client': 'custom', 'session': 's', 'project': str(self.project), 'tool': 'read', 'input': {}}
    def test_health_does_not_expose_state(self):
        self.assertEqual(set(self.request('/healthz', authenticated=False)), {'service', 'version'})
    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/events', self.event(), authenticated=False)
        self.assertEqual(e.exception.code, 401)
    def test_browser_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/events', self.event(), headers={'Origin': 'https://attacker.example'})
        self.assertEqual(e.exception.code, 401)
    def test_event_and_report(self):
        self.assertEqual(self.request('/v1/events', self.event())['decision'], 'allow')
        self.assertEqual(self.request('/v1/status')['events'], 1)
    def test_model_request_and_response(self):
        ctx = {'client': 'custom', 'session': 's', 'project': str(self.project), 'id': 'request1'}
        p = {'model': 'x', 'messages': [{'role': 'user', 'content': 'hello'}]}
        self.assertEqual(self.request('/v1/model/request', {'context': ctx, 'payload': p})['payload'], p)
        response = {'model': 'x', 'usage': {'prompt_tokens': 8, 'completion_tokens': 2}}
        self.assertEqual(self.request('/v1/model/response', {'context': ctx, 'payload': response})['payload'], response)
        self.assertEqual(self.request('/v1/status')['usage']['input_tokens'], 8)
    def test_malformed_event_denied(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/events', {'type': 'wrong'})
        self.assertEqual(e.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
