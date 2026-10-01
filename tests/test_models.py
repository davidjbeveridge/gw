"""Capability routing and planning, without provider calls or subscription access."""
import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from gw_supervisor.catalog import import_openrouter, OPENROUTER_CATALOG
from gw_supervisor.config import DEFAULTS, merge, resolve, trust_project, validate
from gw_supervisor.engine import Supervisor
from gw_supervisor.models import decision_config, requirements, select, validate_registry
from gw_supervisor.proxy import process_request, request_requirements
from gw_supervisor.util import write_json


def model(operation='chat', inputs=None, outputs=None, kind='proxy', billing='metered', **kwargs):
    return {'provider': 'example', 'model': 'arbitrary-model-id', 'operations': [operation],
            'input_modalities': inputs or ['text'], 'output_modalities': outputs or ['text'],
            'capabilities': [], 'execution': {'kind': kind, 'target': 'example-route'},
            'availability': 'available', 'billing': {'kind': billing}, **kwargs}


def req(operation='chat', inputs=None, outputs=None, **kwargs):
    return {'operation': operation, 'input_modalities': inputs or ['text'],
            'output_modalities': outputs or ['text'], **kwargs}


class SelectionTests(unittest.TestCase):
    def pick(self, models, request=None, policy=None, classifier=None):
        return select({'models': models, 'policy': policy or {}}, request or req(), classifier)

    def test_arbitrary_ids_not_tiers(self):
        result = self.pick({'custom/favourite@v7': model()})
        self.assertEqual(result['plan']['model_id'], 'custom/favourite@v7')

    def test_different_families_in_one_registry(self):
        models = {'coder': model(), 'judge': model('decision', outputs=['decisions'], kind='adapter'),
                  'image': model('image.generate', outputs=['image']),
                  'video': model('video.generate', outputs=['video']),
                  'embed': model('embedding', outputs=['embeddings'])}
        for mid, candidate in models.items():
            result = self.pick(models, req(candidate['operations'][0], outputs=candidate['output_modalities']))
            self.assertEqual(result['plan']['model_id'], mid)

    def test_vision_does_not_imply_image_generation(self):
        result = self.pick({'vision': model(inputs=['text', 'image'])}, req('image.generate', outputs=['image']))
        self.assertEqual(result['status'], 'unavailable')

    def test_modality_filter_precedes_preferences(self):
        result = self.pick({'cheap': model(), 'vision': model(inputs=['text', 'image'])}, req(inputs=['text', 'image']), {'prefer': ['cheap']})
        self.assertEqual(result['plan']['model_id'], 'vision')
        self.assertEqual(result['rejected']['cheap'], 'input_modalities_mismatch')

    def test_output_filter(self):
        result = self.pick({'wrong': model(outputs=['audio'])})
        self.assertEqual(result['rejected']['wrong'], 'output_modalities_mismatch')

    def test_custom_capabilities_and_operations_are_open(self):
        m = model('pose.estimate', inputs=['skeleton'], outputs=['tensor'], kind='adapter', capabilities=['custom:accelerated'])
        self.assertEqual(self.pick({'pose': m}, req('pose.estimate', inputs=['skeleton'], outputs=['tensor'], capabilities=['custom:accelerated']))['status'], 'selected')

    def test_missing_capability(self):
        result = self.pick({'no-tools': model()}, req(capabilities=['tools']))
        self.assertEqual(result['rejected']['no-tools'], 'capabilities_mismatch')

    def test_subscription_and_api_separate(self):
        models = {'plan': model('code', kind='harness', billing='subscription'), 'api': model('code')}
        result = self.pick(models, req('code'), {'billing_preference': ['subscription', 'metered']})
        self.assertEqual(result['plan']['execution']['kind'], 'harness')
        self.assertEqual(result['plan']['billing'], {'kind': 'subscription'})
        self.assertTrue(result['selection_only'])

    def test_proxy_cannot_select_harness_even_when_preferred(self):
        result = self.pick({'sub': model(kind='harness'), 'api': model()}, req(execution_kinds=['proxy']), {'prefer': ['sub']})
        self.assertEqual(result['plan']['model_id'], 'api')

    def test_unknown_exhausted_disabled_expired(self):
        models = {'unknown': model(availability='unknown'), 'exhausted': model(availability='exhausted'),
                  'disabled': model(enabled=False), 'zero': model(quota_remaining=0),
                  'expired': model(available_until='2000-01-01T00:00:00Z')}
        r = self.pick(models)
        self.assertEqual(r['status'], 'unavailable')
        self.assertEqual(len(r['rejected']), 5)

    def test_absent_availability_is_not_assumed(self):
        m = model(); del m['availability']
        self.assertEqual(self.pick({'x': m})['status'], 'unavailable')

    def test_unknown_quota_not_fabricated_as_free(self):
        r = self.pick({'subscription': model(billing='subscription')})
        self.assertNotIn('prices', r['plan']['billing'])

    def test_context_window_unknown_and_small_excluded(self):
        r = self.pick({'unknown': model(), 'small': model(context_window=100), 'large': model(context_window=10000)}, req(context_tokens=200))
        self.assertEqual(r['plan']['model_id'], 'large')

    def test_explicit_price_units_preserved_not_compared(self):
        m = model(billing='metered'); m['billing']['prices'] = {'USD/image': .2, 'USD/million_input_tokens': 2}
        self.assertEqual(self.pick({'x': m})['plan']['billing']['prices'], m['billing']['prices'])

    def test_allow_deny_and_exclude(self):
        r = self.pick({x: model() for x in 'abcd'}, req(exclude=['b']), {'allow': ['a', 'b', 'c'], 'deny': ['a']})
        self.assertEqual(r['plan']['model_id'], 'c')

    def test_empty_allowlist_is_no_models(self):
        self.assertEqual(self.pick({'a': model()}, policy={'allow': []})['status'], 'unavailable')

    def test_stable_order(self):
        self.assertEqual(self.pick({'z': model(), 'a': model()})['plan']['model_id'], 'a')

    def test_classifier_only_sees_eligible_candidates(self):
        classifier = mock.Mock()
        classifier.decide.return_value = {'model_selection': 'candidate_1'}
        r = self.pick({'a': model(), 'b': model(), 'secret': model('decision', outputs=['decisions'])}, policy={'strategy': 'classifier'}, classifier=classifier)
        self.assertEqual(r['plan']['model_id'], 'b')
        self.assertNotIn('secret', json.dumps(classifier.decide.call_args.args[1]))

    def test_classifier_abstention_no_paid_fallback(self):
        c = mock.Mock(); c.decide.return_value = {'model_selection': 'abstain'}
        self.assertEqual(self.pick({'a': model(), 'b': model()}, policy={'strategy': 'classifier'}, classifier=c)['status'], 'abstained')

    def test_classifier_invalid_choice_and_error(self):
        c = mock.Mock(); c.decide.return_value = {'model_selection': 'invented'}
        for fail in (False, True):
            if fail:
                c.decide.side_effect = RuntimeError('secret must not be echoed')
            r = self.pick({'a': model(), 'b': model()}, policy={'strategy': 'classifier'}, classifier=c)
            self.assertEqual(r['status'], 'classifier_unavailable')
            self.assertNotIn('secret', json.dumps(r))

    def test_single_candidate_does_not_spend_classifier_call(self):
        c = mock.Mock()
        self.assertEqual(self.pick({'a': model()}, policy={'strategy': 'classifier'}, classifier=c)['status'], 'selected')
        c.decide.assert_not_called()

    def test_registry_rejects_ambiguous_or_executable_config(self):
        for patch in ({'execution': {'kind': 'shell', 'target': 'bash'}}, {'api_key': 'secret'}, {'priority': float('nan')}, {'quota_remaining': -1}, {'enabled': 'yes'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_registry({'models': {'x': model(**patch)}})

    def test_opaque_state_cannot_cross_models(self):
        bound = model(); bound['execution']['target'] = 'original'
        r = self.pick({'original': bound, 'other': model()}, req(execution_target='original'), {'prefer': ['other']})
        self.assertEqual(r['plan']['model_id'], 'original')
        self.assertEqual(r['rejected']['other'], 'opaque_state_bound_to_other_target')

    def test_invalid_requirements(self):
        for request in ({}, req(capabilities='tools'), req(context_tokens=True), req(execution_kinds=['shell'])):
            with self.assertRaises(ValueError):
                requirements(request)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'home'
        self.project = self.root / 'project'; self.project.mkdir(); (self.project / '.git').mkdir()
        self.ctx = {'client': 'generic', 'project': str(self.project), 'session': 'test'}

    def config(self, models, **overrides):
        value = {'inference': {'models': models, 'policy': {}}, **overrides}
        write_json(self.home / 'config.json', value)
        return value

    def test_existing_v01_session_survives_upgrade(self):
        self.config({})
        with Supervisor(self.home) as s:
            event = {**self.ctx, 'type': 'session.start', 'task': 'legacy task'}
            first = s.evaluate(event)
            row = s.store.db.execute('SELECT config FROM sessions WHERE id=?', (first['session_id'],)).fetchone()
            legacy = json.loads(row[0]); legacy.pop('inference')
            with s.store.db:
                s.store.db.execute('UPDATE sessions SET config=? WHERE id=?', (json.dumps(legacy), first['session_id']))
            result = process_request(s, self.ctx, {'model': 'existing', 'messages': []})
            self.assertEqual(result['decision'], 'allow')
            self.assertEqual(result['payload']['model'], 'existing')

    def test_image_request_rewrites_alias_not_payload_contract(self):
        self.config({'image': model('image.generate', outputs=['image'])}, proxy={'inject_task': True, 'max_output_tokens': 12})
        payload = {'model': 'incoming', 'prompt': 'a mountain', 'size': '1024x1024', 'n': 2}
        with Supervisor(self.home) as s:
            r = process_request(s, self.ctx, payload, 'image')
        self.assertEqual(r['payload'], {**payload, 'model': 'example-route'})
        self.assertEqual(payload['model'], 'incoming')

    def test_legacy_tier_routing_cannot_rewrite_media(self):
        self.config({}, proxy={'models': {'cheap': {'alias': 'text-only', 'capabilities': ['text']}}}, goals={'tier': {'on': ['model.request'], 'evaluator': 'choice', 'question': 'Pick', 'choices': {'cheap': 'cheap'}, 'route': {'cheap': 'cheap'}}})
        c = mock.Mock(); c.decide.return_value = {'tier': 'cheap'}
        with Supervisor(self.home, classifier=c) as s:
            result = process_request(s, self.ctx, {'model': 'image-original', 'prompt': 'test'}, 'image')
        self.assertEqual(result['payload']['model'], 'image-original')

    def test_video_decision_embedding_protocols(self):
        for wire, op, outputs in [('video', 'video.generate', ['video']), ('decision', 'decision', ['decisions']), ('embedding', 'embedding', ['embeddings'])]:
            self.config({wire: model(op, outputs=outputs)})
            with Supervisor(self.home) as s:
                r = process_request(s, {**self.ctx, 'session': wire}, {'model': 'old', 'prompt': 'test'}, wire)
            self.assertEqual(r['payload']['model'], 'example-route')
            self.assertEqual(r['inference']['plan']['operation'], op)

    def test_chat_does_not_rewrite_to_video_or_harness(self):
        self.config({'video': model('video.generate', outputs=['video']), 'subscription': model(kind='harness')})
        with Supervisor(self.home) as s:
            r = process_request(s, self.ctx, {'model': 'old', 'messages': []})
        self.assertEqual(r['decision'], 'approve')
        self.assertEqual(r['payload']['model'], 'old')

    def test_general_selection_returns_harness_plan(self):
        self.config({'codex-plan': model('code', kind='harness', billing='subscription')})
        with Supervisor(self.home) as s:
            r = s.evaluate({**self.ctx, 'type': 'inference.select', 'requirements': req('code')})
        self.assertEqual(r['inference']['plan']['execution']['kind'], 'harness')
        self.assertNotIn('model', r)

    def test_authority_sees_selected_plan_and_can_deny(self):
        self.config({'judge': model('decision', outputs=['decisions'], kind='adapter')})
        a = mock.Mock(); a.authorize.return_value = {'decision': 'deny'}
        with Supervisor(self.home, authority=a) as s:
            r = s.evaluate({**self.ctx, 'type': 'inference.select', 'requirements': req('decision', outputs=['decisions'])})
        self.assertEqual(r['decision'], 'deny')
        self.assertEqual(a.authorize.call_args.args[0]['inference_plan']['model_id'], 'judge')

    def test_registry_model_ref_for_supervisor_classifier(self):
        m = model('decision', outputs=['decisions'], kind='adapter', model='my-pinned-jev')
        m['execution']['target'] = 'jev'
        c = merge(DEFAULTS, {'inference': {'models': {'judge': m}}, 'decision': {'provider': 'jev', 'model_ref': 'judge'}})
        self.assertEqual(decision_config(c)['model'], 'my-pinned-jev')
        c['inference']['models']['judge']['availability'] = 'exhausted'
        with self.assertRaises(ValueError):
            decision_config(c)

    def test_project_inheritance_and_lock(self):
        self.config({'a': model(), 'b': model()}, locked=['inference.models'])
        write_json(self.project / '.gw.json', {'inference': {'policy': {'prefer': ['b']}}})
        trust_project(self.home, self.project)
        c, _ = resolve(self.home, self.project, 'generic')
        self.assertEqual(select(c['inference'], req())['plan']['model_id'], 'b')
        write_json(self.project / '.gw.json', {'inference': {'models': {'a': {'enabled': False}}}})
        with self.assertRaises(ValueError):
            trust_project(self.home, self.project)

    def test_selection_cli(self):
        self.config({'image': model('image.generate', outputs=['image'])})
        r = subprocess.run([sys.executable, '-m', 'gw_supervisor', '--home', str(self.home), 'models', 'select', '--project', str(self.project), '--operation', 'image.generate', '--input', 'text', '--output', 'image'], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout)['inference']['plan']['model_id'], 'image')

    def test_proxy_requirements_cannot_be_weakened(self):
        with self.assertRaises(ValueError):
            request_requirements({'tools': [{}]}, 'chat', {'execution_kinds': ['harness']})
        r = request_requirements({'tools': [{}]}, 'chat', {'capabilities': ['code'], 'context_tokens': 200})
        self.assertEqual(r['capabilities'], ['code', 'tools'])

    def test_request_requirements_distinguish_vision_from_image_output(self):
        r = request_requirements({'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'x'}}]}]}, 'chat')
        self.assertEqual(r['input_modalities'], ['image', 'text'])
        self.assertEqual(r['output_modalities'], ['text'])

    def test_signed_reasoning_and_server_tools_require_capabilities(self):
        r = request_requirements({'messages': [{'content': [{'type': 'thinking', 'signature': 'x'}]}], 'tools': [{'type': 'web_search'}], 'previous_response_id': 'r'}, 'responses')
        self.assertTrue({'signed_reasoning', 'previous_response_id', 'tool:web_search', 'tools'} <= set(r['capabilities']))


class CatalogTests(unittest.TestCase):
    def row(self, mid, outputs):
        return {'id': mid, 'name': mid, 'architecture': {'input_modalities': ['text'], 'output_modalities': outputs}, 'supported_parameters': ['tools'], 'context_length': 1000, 'pricing': {'prompt': '0.0001'}}

    def test_catalog_includes_nontext_but_does_not_enable(self):
        self.assertIn('output_modalities=all', OPENROUTER_CATALOG)
        snapshot = {'data': [self.row('coder', ['text']), self.row('judge', ['decisions']), self.row('image', ['image']), self.row('other', ['text'])]}
        result = import_openrouter(snapshot, ['coder', 'judge', 'image'])
        models = result['inference']['models']
        self.assertEqual(len(models), 3)
        self.assertTrue(all(not m['enabled'] and m['availability'] == 'unknown' for m in models.values()))
        self.assertEqual(models['openrouter:judge']['operations'], ['decision'])
        self.assertEqual(models['openrouter:image']['operations'], ['configure.operation'])
        self.assertEqual(models['openrouter:coder']['metadata']['pricing_as_published'], {'prompt': '0.0001'})

    def test_missing_or_duplicate_ids_fail_not_guess(self):
        for snapshot in ({'data': []}, {'data': [self.row('x', ['text'])] * 2}):
            with self.assertRaises(ValueError):
                import_openrouter(snapshot, ['x'])

    def test_bad_schema_does_not_invent_modalities(self):
        with self.assertRaises(ValueError):
            import_openrouter({'data': [{'id': 'x'}]}, ['x'])


if __name__ == '__main__':
    unittest.main()
