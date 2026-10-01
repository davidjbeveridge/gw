"""Wire compatibility and setup flow tests; no paid calls or model downloads."""
import contextlib
import copy
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock
from gw_supervisor.cli import main, parser
from gw_supervisor.config import DEFAULTS, merge, resolve, trust_project
from gw_supervisor.decision_setup import PRESETS, SMOKE_GOALS, SMOKE_STATE, candidate, manifest, probe
from gw_supervisor.decision_transport import credential, validate_decision
from gw_supervisor.providers import Classifier
from gw_supervisor.util import read_json, write_json

GOALS = {'topic': {'question': 'What topic?', 'choices': {'code': 'Writing software', 'forms': 'Entering form data'}}}


def cfg(preset='kev', **kw):
    return {**DEFAULTS['decision'], **PRESETS[preset], **kw}


def chat(content='{"decisions":{"topic":"code"}}', finish='stop', **kw):
    return {'choices': [{'finish_reason': finish, 'message': {'content': content, **kw}}]}


class TransportTests(unittest.TestCase):
    def test_systemone_keyless_local_request(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'topic': {'choice': 'code'}}}) as post:
            self.assertEqual(Classifier(cfg()).decide({'password': 'hidden'}, GOALS), {'topic': 'code'})
            url, body, token, timeout = post.call_args.args
            self.assertEqual(url, 'http://127.0.0.1:8009/v1/systemone')
            self.assertEqual(token, '')
            self.assertNotIn('hidden', body['state'])
            self.assertEqual(body['questions']['topic']['criteria'], GOALS['topic']['choices'])

    def test_openrouter_uses_systemone_and_correct_key(self):
        with mock.patch.dict(os.environ, {'OPENROUTER_API_KEY': 'router-token', 'TYPESAFE_API_KEY': 'wrong-token'}), mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'topic': {'choice': 'forms'}}}) as post:
            Classifier(cfg('openrouter')).decide({}, GOALS)
            self.assertEqual(post.call_args.args[0], 'https://openrouter.ai/api/v1/systemone')
            self.assertEqual(post.call_args.args[2], 'router-token')

    def test_missing_key_no_request(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch('gw_supervisor.providers.post_json') as post:
            with self.assertRaisesRegex(RuntimeError, 'key_missing'):
                Classifier(cfg('typesafe')).decide({}, GOALS)
            post.assert_not_called()

    def test_none_auth_does_not_read_or_leak_inherited_credentials(self):
        with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'secret'}):
            self.assertEqual(credential(cfg(key_env='TYPESAFE_API_KEY', key_file='/does/not/exist')), '')

    def test_custom_contract_unchanged(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value={'decisions': {'topic': 'code'}}) as post:
            Classifier(cfg(provider='http')).decide({}, GOALS)
            self.assertEqual(post.call_args.args[1]['version'], 1)
            self.assertEqual(post.call_args.args[1]['goals'], GOALS)

    def test_openai_schema_and_success(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value=chat()) as post:
            result = Classifier(cfg(provider='openai')).decide({}, GOALS)
            self.assertEqual(result, {'topic': 'code'})
            b = post.call_args.args[1]
            self.assertFalse(b['stream'])
            self.assertTrue(b['response_format']['json_schema']['strict'])
            self.assertEqual(b['response_format']['json_schema']['schema']['properties']['decisions']['properties']['topic']['enum'], ['code', 'forms'])
            self.assertNotIn('tools', b)

    def test_explicit_json_object_mode_and_token_parameter(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value=chat()) as post:
            Classifier(cfg(provider='openai', response_format='json_object', token_parameter='max_completion_tokens')).decide({}, GOALS)
            b = post.call_args.args[1]
            self.assertEqual(b['response_format'], {'type': 'json_object'})
            self.assertIn('max_completion_tokens', b)
            self.assertNotIn('max_tokens', b)

    def test_chat_invalid_incomplete_refusal_and_tools_are_errors(self):
        for response in (chat(finish='length'), chat(refusal='No'), chat(tool_calls=[{'id':'a'}]),
                         chat('```json\n{"decisions":{"topic":"code"}}\n```'),
                         chat('{"decisions":{"topic":"code","topic":"forms"}}'),
                         chat('{"decisions":{"topic":"invented"}}'), chat('{"decisions":{}}'),
                         chat('{"decisions":{"topic":"code","extra":"code"}}')):
            with self.subTest(response=response), mock.patch('gw_supervisor.providers.post_json', return_value=response):
                with self.assertRaises(ValueError):
                    Classifier(cfg(provider='openai')).decide({}, GOALS)

    def test_reported_truncation_is_not_accepted(self):
        for usage in ({'truncated': True}, {'state_tokens_dropped': 20}, {'truncated_questions': ['topic']}):
            with mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'topic': {'choice': 'code'}}, 'usage': usage}):
                with self.assertRaisesRegex(ValueError, 'truncated'):
                    Classifier(cfg()).decide({}, GOALS)

    def test_top_level_kev_truncation_is_rejected(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'topic': {'choice': 'code'}}, 'truncated': True}):
            with self.assertRaisesRegex(ValueError, 'truncated'):
                Classifier(cfg()).decide({}, GOALS)

    def test_wrong_systemone_type_rejected(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'topic': {'type': 'noul', 'choice': 'code'}}}):
            with self.assertRaises(ValueError):
                Classifier(cfg()).decide({}, GOALS)

    def test_request_budget_includes_questions(self):
        with mock.patch('gw_supervisor.providers.post_json') as post:
            with self.assertRaisesRegex(RuntimeError, 'request_too_large'):
                Classifier(cfg(max_request_chars=10)).decide({}, GOALS)
            post.assert_not_called()

    def test_option_limit_is_enforced(self):
        with self.assertRaisesRegex(RuntimeError, 'too_many_options'):
            Classifier(cfg(max_options=1)).decide({}, GOALS)

    def test_endpoint_and_credential_config_validation(self):
        for kwargs in ({'endpoint':'https://host/v1?key=secret'}, {'key_env':'literal key'}, {'key_file':'relative'},
                       {'timeout_seconds': 6}, {'max_output_tokens': 5.5}, {'auth':'surprise'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                validate_decision(cfg(**kwargs))

    def test_existing_private_key_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)/'key'; path.write_text('from-file\n'); path.chmod(0o600)
            c = cfg(auth='bearer', key_file=str(path), key_env='GW_TEST_SECRET')
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(credential(c), 'from-file')
            with mock.patch.dict(os.environ, {'GW_TEST_SECRET':'from-env'}):
                self.assertEqual(credential(c), 'from-env')
            if os.name != 'nt':
                path.chmod(0o644)
                with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
                    credential(c)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)/'home'; self.home.mkdir()
        self.path = self.home/'config.json'

    def call(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(['--home',str(self.home),*args])
        return json.loads(out.getvalue())

    def test_manifest_noninteractive_without_writes(self):
        self.assertEqual(self.call('setup','--describe')['presets']['openrouter']['provider'], 'systemone')
        self.assertEqual(list(self.home.iterdir()), [])

    def test_dry_run_no_config_or_request(self):
        with mock.patch('gw_supervisor.providers.post_json') as post:
            r = self.call('setup','--preset','kev','--dry-run')
            self.assertFalse(r['applied']); self.assertFalse(self.path.exists()); post.assert_not_called()

    def test_apply_preserves_goals_and_registry_and_backs_up(self):
        old = {'version':1, 'goals':{'research_first':{'enabled':False}}, 'inference': {'models':{}}, 'clients':{'codex': {'mode':'observe'}}}
        write_json(self.path,old)
        r = self.call('setup','--preset','openrouter','--yes')
        new = read_json(self.path)
        self.assertEqual(new['goals'],old['goals']); self.assertEqual(new['clients'],old['clients'])
        self.assertEqual(read_json(pathlib.Path(r['backup'])),old)
        self.assertEqual(new['decision']['key_env'], 'OPENROUTER_API_KEY')

    def test_setup_removes_stale_model_ref(self):
        write_json(self.path, {'decision': {'model_ref':'old'}})
        self.call('setup','--preset','kev','--yes')
        self.assertIsNone(read_json(self.path)['decision']['model_ref'])

    def test_failed_check_does_not_change_configuration(self):
        old = {'version':1}; write_json(self.path,old)
        with mock.patch('gw_supervisor.providers.post_json', side_effect=RuntimeError('sensitive-provider-message')):
            with self.assertRaises(SystemExit) as ctx:
                self.call('setup','--preset','kev','--check','--yes')
        self.assertEqual(ctx.exception.code,2); self.assertEqual(read_json(self.path),old)

    def test_probe_synthetic_and_correct_labels(self):
        with mock.patch('gw_supervisor.providers.post_json', return_value={'answers':{k:{'choice':v} for k,v in {'selection':'beta','policy':'deny'}.items()}}) as post:
            r = self.call('setup','--preset','kev','--check','--yes')
            self.assertTrue(r['check']['ok']); self.assertFalse(r['check']['accuracy_benchmark'])
            self.assertEqual(json.loads(post.call_args.args[1]['state']),SMOKE_STATE)

    def test_probe_does_not_echo_raw_provider_errors(self):
        with mock.patch('gw_supervisor.providers.post_json',side_effect=RuntimeError('SECRET_RAW_PROVIDER_MESSAGE')):
            result = probe(cfg())
        self.assertNotIn('SECRET_RAW_PROVIDER_MESSAGE',json.dumps(result))
        self.assertFalse(result['ok'])

    def test_missing_key_diagnostic(self):
        with mock.patch.dict(os.environ, {},clear=True):
            self.assertEqual(probe(cfg('openrouter'))['error'],'decision_key_missing')

    def test_client_specific_setup_and_locked_global(self):
        self.call('setup','--preset','kev','--client','codex','--yes')
        new=read_json(self.path); self.assertNotIn('decision',new)
        self.assertEqual(new['clients']['codex']['decision']['model'],'kev-latest')
        write_json(self.path,{'locked':['decision'], 'clients':{}})
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.call('setup','--preset','kev','--client','codex','--yes')

    def test_cua_requires_explicit_bridge_not_fabricated_endpoint(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.call('setup','--preset','cua','--yes')
        self.assertFalse(self.path.exists())
        r=self.call('setup','--preset','cua','--endpoint','http://127.0.0.1:9000/classify','--model','my-evaluated-bridge','--no-auth','--yes')
        self.assertIn('not generic',r['note'])

    def test_remote_local_preset_requires_explicit_auth(self):
        args=parser().parse_args(['setup','--preset','kev','--endpoint','https://myhost/v1/systemone','--yes'])
        c=candidate(args, {})['decision']
        self.assertEqual(c['auth'],'bearer');self.assertEqual(c['key_env'],'GW_DECISION_API_KEY')

    def test_status_makes_no_network_request(self):
        self.call('setup','--preset','kev','--yes')
        with mock.patch('gw_supervisor.providers.post_json') as post:
            r=self.call('decision','status','--project',str(self.home))
            self.assertFalse(r['decision']['live_verified']);post.assert_not_called()

    def test_old_enable_jev_resets_protocol_and_auth(self):
        self.call('setup','--preset','kev','--yes')
        self.call('enable-jev')
        c=read_json(self.path)['decision']
        self.assertEqual(c['endpoint'],PRESETS['typesafe']['endpoint'])
        self.assertEqual(c['auth'],'bearer')

    def test_noninteractive_requires_intent(self):
        with mock.patch('sys.stdin.isatty',return_value=False), contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            self.call('setup','--preset','kev')
        self.assertFalse(self.path.exists())

    def test_cli_subprocess_guide(self):
        run=subprocess.run([sys.executable,'-m','gw_supervisor','--home',str(self.home),'setup','--describe'],capture_output=True,text=True,check=True)
        self.assertIn('openrouter',json.loads(run.stdout)['presets'])


class LocalHTTPTest(unittest.TestCase):
    def test_real_http_systemone_and_chat_roundtrip(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append((self.path,body,self.headers.get('Authorization')))
                result={'answers':{'topic':{'type':'choice','choice':'code'}}} if self.path.endswith('systemone') else chat()
                data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            for protocol,path in [('systemone','/v1/systemone'),('openai','/v1/chat/completions')]:
                result=Classifier(cfg(provider=protocol,endpoint=f'http://127.0.0.1:{server.server_port}{path}')).decide({},GOALS)
                self.assertEqual(result,{'topic':'code'})
            self.assertTrue(all(row[2] is None for row in seen))
        finally:
            server.shutdown();worker.join();server.server_close()
