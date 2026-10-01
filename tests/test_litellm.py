"""Optional real-SDK contract tests; no upstream calls or model keys."""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock
from gw_supervisor.engine import Supervisor
from gw_supervisor.util import write_json

AVAILABLE = importlib.util.find_spec('litellm') is not None
if AVAILABLE:
    from gw_supervisor.litellm import GWCallback


@unittest.skipUnless(AVAILABLE, 'Optional LiteLLM dependency not installed')
class LiteLLMTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'state'
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / '.git').mkdir()
        patch = mock.patch.dict(os.environ, {'GW_HOME': str(self.home), 'GW_PROJECT': str(self.project), 'GW_SESSION': 'test-proxy'})
        patch.start()
        self.addCleanup(patch.stop)
        self.callback = GWCallback()

    async def test_request_transform_real_callback_class(self):
        write_json(self.home / 'config.json', {'proxy': {'compact_tool_json': True, 'max_output_tokens': 123}})
        data = {'model': 'example', 'messages': [{'role': 'tool', 'tool_call_id': 'call', 'content': '{ "value": 1 }'}]}
        result = await self.callback.async_pre_call_hook(None, None, data, 'completion')
        self.assertEqual(result['messages'][0]['content'], '{"value":1}')
        self.assertEqual(result['messages'][0]['tool_call_id'], 'call')
        self.assertEqual(result['max_tokens'], 123)
        self.assertTrue(result['metadata']['gw']['request_id'])

    async def test_denial_stops_model_request(self):
        write_json(self.home / 'config.json', {'rules': {'deny_model': {'on': ['model.request'], 'when': {'model': 'blocked'}, 'effect': 'deny'}}})
        with self.assertRaises(PermissionError):
            await self.callback.async_pre_call_hook(None, None, {'model': 'blocked', 'messages': []}, 'completion')

    async def test_response_preserved_and_usage_audited_once(self):
        data = await self.callback.async_pre_call_hook(None, None, {'model': 'example', 'messages': []}, 'completion')
        response = {'model': 'example', 'choices': [{'message': {'refusal': 'unchanged'}}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 3}}
        self.assertIs(await self.callback.async_post_call_success_hook(data, None, response), response)
        kwargs = {'litellm_params': {'metadata': data['metadata']}}
        await self.callback.async_log_success_event(kwargs, response, None, None)
        await self.callback.async_log_success_event(kwargs, response, None, None)
        with Supervisor(self.home) as supervisor:
            usage = supervisor.store.report()['usage']
        self.assertEqual(usage['input_tokens'], 20)
        self.assertEqual(usage['calls'], 1)

    async def test_missing_context_refuses(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                await self.callback.async_pre_call_hook(None, None, {'model': 'example', 'messages': []}, 'completion')

    async def test_media_request_alias_selection(self):
        from test_models import model
        write_json(self.home / 'config.json', {'inference': {'models': {'image': model('image.generate', outputs=['image'])}}, 'proxy': {'inject_task': True, 'max_output_tokens': 12}})
        data = {'model': 'old', 'prompt': 'a mountain', 'n': 2, 'size': '1024x1024', 'custom_provider_option': True}
        result = await self.callback.async_pre_call_hook(None, None, data, 'image_generation')
        self.assertEqual(result['model'], 'example-route')
        self.assertTrue(result['custom_provider_option'])
        self.assertNotIn('max_tokens', result)
        self.assertNotIn('messages', result)

    async def test_embedding_request_alias_selection(self):
        from test_models import model
        write_json(self.home / 'config.json', {'inference': {'models': {'embed': model('embedding', outputs=['embeddings'])}}})
        result = await self.callback.async_pre_call_hook(None, None, {'model': 'old', 'input': ['one', 'two'], 'dimensions': 128}, 'embeddings')
        self.assertEqual(result['model'], 'example-route')
        self.assertEqual(result['input'], ['one', 'two'])
        self.assertEqual(result['dimensions'], 128)

    async def test_unsupported_operations_are_not_silently_unsupervised(self):
        with self.assertRaises(ValueError):
            await self.callback.async_pre_call_hook(None, None, {'model': 'old'}, 'unknown_new_api')

    async def test_responses_protocol(self):
        write_json(self.home / 'config.json', {'proxy': {'compact_tool_json': True, 'max_output_tokens': 75}})
        data = {'model': 'example', 'input': [{'type': 'function_call_output', 'call_id': 'c', 'output': '{ "n": 1 }'}]}
        result = await self.callback.async_pre_call_hook(None, None, data, 'responses')
        self.assertEqual(result['input'][0]['output'], '{"n":1}')
        self.assertEqual(result['max_output_tokens'], 75)


if __name__ == '__main__':
    unittest.main()
