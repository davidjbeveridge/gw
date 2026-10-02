"""Fastino GLiDE's documented System One contract; no hosted model calls."""
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
from gw_supervisor.cli import main
from gw_supervisor.agent import AgentService
from gw_supervisor.config import DEFAULTS, merge
from gw_supervisor.decision_setup import PRESETS
from gw_supervisor.decision_transport import credential, validate_decision
from gw_supervisor.providers import Classifier
from gw_supervisor.util import post_json


class FastinoPresetTests(unittest.TestCase):
    def test_preset_is_managed_and_available_to_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=AgentService(pathlib.Path(tmp)/'state',tmp,'codex')
            preset=service.gw_setup_options()['decision']['presets']['glide']
            self.assertEqual(preset['model'],'fastino/GLiDE')
            self.assertEqual(preset['endpoint'],'https://api.fastino.ai/v1/systemone')
            self.assertEqual(preset['strategy'],'managed')
            self.assertEqual(preset['auth'],'api_key')
            validate_decision(merge(DEFAULTS['decision'],PRESETS['glide']))

    def test_setup_key_override_keeps_documented_header_mode(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            main(['--home',tmp,'setup','--preset','glide','--key-env','MY_FASTINO_KEY','--yes'])
            c=json.loads((pathlib.Path(tmp)/'config.json').read_text())['decision']
            self.assertEqual(c['auth'],'api_key')
            self.assertEqual(c['strategy'],'managed')
            self.assertEqual(c['key_env'],'MY_FASTINO_KEY')
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):credential(PRESETS['glide'])

    def test_classifier_preserves_choices_and_usage_with_api_key(self):
        goals={'g':{'question':'Select based on evidence','choices':{'yes':'Supported','unknown':'Insufficient evidence'}}}
        response={'answers':{'g':{'type':'choice','choice':'yes','confidence':0.9,'probabilities':{'yes':0.95,'unknown':0.05}}},
                  'usage':{'input_tokens':42,'output_tokens':7}}
        config=merge(DEFAULTS['decision'],PRESETS['glide'])
        with mock.patch.dict(os.environ,{'FASTINO_API_KEY':'fixture-only-key'}),mock.patch('gw_supervisor.providers.post_json',return_value=response) as request:
            model=Classifier(config)
            self.assertEqual(model.decide({'evidence':'fixture'},goals),{'g':'yes'})
            self.assertEqual(request.call_args.kwargs,{'key_header':'X-API-Key'})
            self.assertEqual(json.loads(request.call_args.args[1]['state']),{'evidence':'fixture'})
            self.assertEqual(model.last_usage,response['usage'])
            self.assertEqual(request.call_count,1)

    def test_http_header_contract_and_no_arbitrary_header(self):
        response=mock.MagicMock()
        response.__enter__.return_value.read.return_value=b'{}'
        opener=mock.Mock();opener.open.return_value=response
        with mock.patch('urllib.request.build_opener',return_value=opener):
            post_json('https://api.fastino.ai/v1/systemone',{},'fixture-only-key',key_header='X-API-Key')
            request=opener.open.call_args.args[0]
            headers={k.lower():v for k,v in request.header_items()}
            self.assertEqual(headers['x-api-key'],'fixture-only-key')
            self.assertNotIn('authorization',headers)
            post_json('https://example.test/v1/decision',{},'fixture-only-key')
            request=opener.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'),'Bearer fixture-only-key')
        with self.assertRaises(ValueError):post_json('https://example.test',{},key_header='X-Unreviewed')
