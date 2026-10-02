"""No external inference: deterministic fixtures exercise the real cascade."""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest import mock
from gw_supervisor.config import DEFAULTS, merge, validate
from gw_supervisor.decisions import DecisionCascade
from gw_supervisor.decision_transport import parse_answers, request_body
from gw_supervisor.engine import Supervisor
from gw_supervisor.util import write_json

BACKEND = {'provider': 'openai', 'endpoint': 'http://127.0.0.1:9981/chat/completions', 'model': 'slow', 'auth': 'none', 'timeout_seconds': 3}
GOALS = {g: {'question': 'Does the evidence establish the answer?', 'choices': {'yes': 'Yes', 'uncertain': 'Insufficient'}, 'on': ['tool.before'], 'evaluator': 'choice'} for g in ('a', 'b')}


def config():
    return {**BACKEND, 'model': 'fast', 'strategy': 'cascade', 'fallback': {'backend': BACKEND, 'on_labels': {'*': ['uncertain']}, 'on_error': False}}


class CascadeTests(unittest.TestCase):
    def decider(self, responses, c=None):
        self.calls = []
        def factory(backend):
            outer = self
            class Fake:
                last_usage = {'input_tokens': 10, 'output_tokens': 2}
                def decide(self, state, goals):
                    outer.calls.append((backend['model'], copy.deepcopy(state), copy.deepcopy(goals)))
                    response = responses[len(outer.calls)-1]
                    if isinstance(response, Exception):
                        raise response
                    return response
            return Fake()
        return DecisionCascade(c or config(), factory)

    def test_clear_labels_use_one_call(self):
        d = self.decider([{'a': 'yes', 'b': 'yes'}])
        self.assertEqual(d.decide({'evidence': 1}, GOALS), {'a': 'yes', 'b': 'yes'})
        self.assertEqual(len(self.calls), 1)

    def test_only_uncertain_subset_escalates(self):
        d = self.decider([{'a': 'yes', 'b': 'uncertain'}, {'b': 'yes'}])
        self.assertEqual(d.decide({'evidence': 1}, GOALS), {'a': 'yes', 'b': 'yes'})
        self.assertEqual(set(self.calls[1][2]), {'b'})
        self.assertEqual(self.calls[0][1], self.calls[1][1])
        self.assertEqual([x['stage'] for x in d.last_calls], ['primary', 'fallback'])
        self.assertEqual(sum(x['usage']['input_tokens'] for x in d.last_calls), 20)

    def test_uncertain_fallback_is_not_recursive(self):
        d = self.decider([{'a': 'uncertain', 'b': 'yes'}, {'a': 'uncertain'}])
        self.assertEqual(d.decide({}, GOALS)['a'], 'uncertain')
        self.assertEqual(len(self.calls), 2)

    def test_error_fallback_explicit(self):
        d = self.decider([TimeoutError()])
        with self.assertRaises(TimeoutError): d.decide({}, GOALS)
        self.assertEqual(len(self.calls), 1)
        c = config(); c['fallback']['on_error'] = True
        d = self.decider([TimeoutError(), {'a': 'yes', 'b': 'yes'}], c)
        d.decide({}, GOALS)
        self.assertEqual(d.last_calls[1]['trigger'], 'primary_error')

    def test_refusal_never_retries(self):
        c = config(); c['fallback']['on_error'] = True
        d = self.decider([ValueError('decision_provider_refused')], c)
        with self.assertRaises(ValueError): d.decide({}, GOALS)
        self.assertEqual(len(self.calls), 1)
        for answer in ({'finish_reason': 'stop', 'message': {'refusal': 'No'}}, {'finish_reason': 'content_filter', 'message': {'content': ''}}):
            with self.assertRaisesRegex(ValueError, 'decision_provider_refused'):
                parse_answers(BACKEND, {'choices': [answer]}, GOALS)

    def test_fallback_malformed_is_not_an_allow(self):
        d = self.decider([{'a': 'yes', 'b': 'uncertain'}, {'b': 'invented'}])
        with self.assertRaises(ValueError): d.decide({}, GOALS)
        self.assertEqual(d.last_calls[-1]['status'], 'error')

    def test_goal_specific_trigger(self):
        c = config(); c['fallback']['on_labels'] = {'a': ['uncertain']}
        d = self.decider([{'a': 'yes', 'b': 'uncertain'}], c)
        d.decide({}, GOALS); self.assertEqual(len(self.calls), 1)

    def test_managed_endpoint_one_call(self):
        d = self.decider([{'a': 'yes', 'b': 'uncertain'}], {**BACKEND, 'strategy': 'managed'})
        d.decide({}, GOALS); self.assertEqual(len(self.calls), 1)
        self.assertEqual(d.last_calls[0]['strategy'], 'managed')

    def test_nested_or_structure_overrides_rejected(self):
        for c in ({**BACKEND, 'strategy': 'magic'}, {**BACKEND, 'request_options': {'messages': []}}, {**BACKEND, 'request_options': {'model': 'different'}},
                  {**config(), 'fallback': {'backend': {**BACKEND, 'strategy': 'cascade'}}}):
            with self.subTest(c=c), self.assertRaises(ValueError): DecisionCascade(c)

    def test_reasoning_options_and_output_bound(self):
        c = {**BACKEND, 'strategy': 'managed', 'request_options': {'reasoning': {'effort': 'low'}}, 'max_output_tokens': 2048}
        d = DecisionCascade(c)
        body = request_body(c, {}, GOALS)
        self.assertEqual(body['reasoning'], {'effort': 'low'})
        self.assertEqual(body['max_tokens'], 2048)
        self.assertFalse(body['stream'])
        self.assertEqual(body['response_format']['type'], 'json_schema')

    def test_local_denial_survives_both_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write_json(root/'config.json', {'decision': config(), 'plugins': {'observe': {'enabled': True}},
                'goals': {k: {'enabled': False} for k in DEFAULTS['goals']},
                'rules': {'no': {'when': {'tool': 'Bash'}, 'effect': 'deny'}}})
            # Inject a cascade using fixture providers; no network or actual tool.
            d = self.decider([{'a': 'uncertain', 'b': 'yes'}, {'a': 'yes'}])
            existing = json.loads((root/'config.json').read_text()); existing['goals'].update(GOALS); write_json(root/'config.json', existing)
            with Supervisor(root, classifier=d) as supervisor:
                supervisor.store.set_task(str(root), 'Do a bounded task')
                result = supervisor.evaluate({'type': 'tool.before', 'id': 'x', 'client': 'test', 'session': 's', 'project': str(root), 'tool': 'Bash', 'input': {}})
            self.assertEqual(result['decision'], 'deny')
            self.assertEqual(len(result['audit']['classifier_calls']), 2)
