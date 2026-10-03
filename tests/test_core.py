"""Offline unit/integration coverage. No provider keys or paid inference required."""
import copy
import json
import pathlib
import tempfile
import unittest
import uuid
from unittest import mock

from gw_supervisor.config import DEFAULTS, merge, resolve, trust_project, validate
from gw_supervisor.engine import Supervisor, matches
from gw_supervisor.providers import Classifier, HttpAuthority
from gw_supervisor.proxy import compact_json, compact_tools, inject_task, process_request, process_response
from gw_supervisor.util import canonical, finite, redact, safe_endpoint, strict_json, write_json


class FakeClassifier:
    def __init__(self, labels=None, failure=False):
        self.labels = labels or {}
        self.failure = failure
        self.calls = 0
    def decide(self, state, goals):
        self.calls += 1
        if self.failure:
            raise RuntimeError('secret-provider-error-MUST-NOT-LOG')
        return {key: self.labels.get(key, next(iter(g['choices']))) for key, g in goals.items()}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'home'
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / '.git').mkdir()
        self.home.mkdir()
    def config(self, value):
        write_json(self.home / 'config.json', value)
    def supervisor(self, **kw):
        s = Supervisor(self.home, **kw)
        self.addCleanup(s.close)
        return s
    def event(self, kind='tool.before', **kw):
        return {'type': kind, 'id': str(uuid.uuid4()), 'client': 'generic', 'session': 's1', 'project': str(self.project), 'tool': 'Bash', 'input': {'command': 'pytest'}, **kw}
    def task(self, s):
        s.store.set_task(str(self.project), 'Fix parser tests in this repository')


class ConfigTests(Fixture):
    def test_inheritance(self):
        self.config({'clients': {'codex': {'proxy': {'max_output_tokens': 1000}}}})
        write_json(self.project / '.gw.json', {'proxy': {'compact_tool_json': True}})
        trust_project(self.home, self.project)
        c, status = resolve(self.home, self.project, 'codex')
        self.assertEqual(c['proxy']['max_output_tokens'], 1000)
        self.assertTrue(c['proxy']['compact_tool_json'])
        self.assertEqual(status, 'trusted_snapshot')
    def test_locked_parent_blocks_override(self):
        self.config({'locked': ['mode'], 'mode': 'enforce'})
        write_json(self.project / '.gw.json', {'mode': 'observe'})
        with self.assertRaises(ValueError):
            trust_project(self.home, self.project)
    def test_locked_nested_goal(self):
        base = merge(DEFAULTS, {'locked': ['goals.retry_limit.threshold']})
        with self.assertRaises(ValueError):
            merge(base, {'goals': {'retry_limit': {'threshold': 900}}})
    def test_untrusted_project_is_not_loaded(self):
        write_json(self.project / '.gw.json', {'mode': 'observe'})
        c, status = resolve(self.home, self.project, 'generic')
        self.assertEqual(c['mode'], 'enforce')
        self.assertIn('untrusted', status)
    def test_trusted_project_edit_not_live(self):
        write_json(self.project / '.gw.json', {'proxy': {'max_output_tokens': 200}})
        trust_project(self.home, self.project)
        write_json(self.project / '.gw.json', {'proxy': {'max_output_tokens': 999}})
        c, status = resolve(self.home, self.project, 'generic')
        self.assertEqual(c['proxy']['max_output_tokens'], 200)
        self.assertIn('changed', status)
    def test_project_cannot_change_provider_endpoint(self):
        write_json(self.project / '.gw.json', {'decision': {'endpoint': 'https://example.com'}})
        with self.assertRaises(ValueError):
            trust_project(self.home, self.project)
    def test_project_client_cannot_change_authority(self):
        write_json(self.project / '.gw.json', {'clients': {'codex': {'authority': {'endpoint': 'https://example.com'}}}})
        with self.assertRaises(ValueError):
            trust_project(self.home, self.project)
    def test_invalid_effect_rejected(self):
        c = merge(DEFAULTS, {'goals': {'retry_limit': {'effect': 'ignore'}}})
        with self.assertRaises(ValueError):
            validate(c)
    def test_merge_does_not_mutate_defaults(self):
        c = merge(DEFAULTS, {'goals': {'retry_limit': {'threshold': 7}}})
        self.assertEqual(DEFAULTS['goals']['retry_limit']['threshold'], 3)
        self.assertEqual(c['goals']['retry_limit']['threshold'], 7)


class EngineTests(Fixture):
    def test_no_key_needed_for_local_rules(self):
        self.config({'rules': {'no': {'when': {'input.command': 'pytest'}, 'effect': 'deny'}}})
        result = self.supervisor().evaluate(self.event())
        self.assertEqual(result['decision'], 'deny')
        self.assertEqual(result['classifier_status'], 'disabled')
    def test_rule_precedence_deny_wins(self):
        self.config({'rules': {'no': {'when': {'tool': 'Bash'}, 'effect': 'deny'}, 'yes': {'when': {'tool': 'Bash'}, 'effect': 'allow'}}})
        self.assertEqual(self.supervisor().evaluate(self.event())['decision'], 'deny')
    def test_observe_records_would_decision(self):
        self.config({'mode': 'observe', 'rules': {'no': {'when': {'tool': 'Bash'}, 'effect': 'deny'}}})
        r = self.supervisor().evaluate(self.event())
        self.assertEqual((r['decision'], r['would_decision']), ('advise', 'deny'))
    def test_authority_allow_cannot_relax_local_deny(self):
        self.config({'rules': {'no': {'when': {'tool': 'Bash'}, 'effect': 'deny'}}})
        authority = mock.Mock()
        authority.authorize.return_value = {'decision': 'allow'}
        self.assertEqual(self.supervisor(authority=authority).evaluate(self.event())['decision'], 'deny')
    def test_authority_failure_is_closed_even_observe(self):
        self.config({'mode': 'observe'})
        authority = mock.Mock()
        authority.authorize.side_effect = TimeoutError()
        self.assertEqual(self.supervisor(authority=authority).evaluate(self.event())['decision'], 'deny')
    def test_exact_failure_loop_pauses(self):
        s = self.supervisor()
        for _ in range(3):
            s.evaluate(self.event('tool.after', success=False))
        self.assertEqual(s.evaluate(self.event())['decision'], 'approve')
    def test_success_breaks_failure_streak(self):
        s = self.supervisor()
        for _ in range(3):
            s.evaluate(self.event('tool.after', success=False))
        s.evaluate(self.event('tool.after', success=True))
        self.assertEqual(s.evaluate(self.event())['decision'], 'allow')
    def test_repeated_success_proposes_not_executes(self):
        s = self.supervisor()
        for _ in range(3):
            result = s.evaluate(self.event('tool.after', success=True))
        self.assertIn('automation_candidate', result)
        candidates = s.store.report()['automation_candidates']
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['status'], 'proposed')
    def test_duplicate_post_does_not_count_twice(self):
        s = self.supervisor()
        event = self.event('tool.after', success=True)
        s.evaluate(event)
        self.assertTrue(s.evaluate(event)['duplicate'])
        self.assertEqual(s.store.report()['events'], 1)
        self.assertEqual(s.store.report()['automation_candidates'], [])
    def test_separate_projects_do_not_share_repetitions(self):
        s = self.supervisor()
        for _ in range(2):
            s.evaluate(self.event('tool.after', success=True))
        other = self.root / 'other'
        other.mkdir()
        s.evaluate(self.event('tool.after', project=str(other), success=True))
        self.assertEqual(s.store.report()['automation_candidates'], [])
    def test_first_prompt_pins_task(self):
        s = self.supervisor()
        s.evaluate(self.event('session.start', task='First task'))
        s.evaluate(self.event('session.start', task='Different task'))
        self.assertEqual(s.session_context(self.event())['task'], 'First task')
    def test_session_policy_is_pinned(self):
        s = self.supervisor()
        s.evaluate(self.event())
        self.config({'rules': {'no': {'when': {'tool': 'Bash'}, 'effect': 'deny'}}})
        self.assertEqual(s.evaluate(self.event())['decision'], 'allow')
        self.assertEqual(s.evaluate(self.event(session='new-session'))['decision'], 'deny')
    def test_no_missing_session_fallback(self):
        with self.assertRaises(ValueError):
            self.supervisor().evaluate(self.event(session=''))
    def test_unknown_tool_input_is_rejected(self):
        with self.assertRaises(ValueError):
            self.supervisor().evaluate(self.event(input='raw'))
    def test_classifier_scores_cumulative_drift(self):
        classifier = FakeClassifier({'task_alignment': 'off_task'})
        s = self.supervisor(classifier=classifier)
        self.task(s)
        for n in range(3):
            s.evaluate(self.event(input={'command': f'cat other{n}.txt'}))
        r = s.evaluate(self.event())
        self.assertEqual(r['metrics']['observations'], 3)
        self.assertGreater(r['metrics']['drift'], .65)
        self.assertTrue(any('replan' in text for text in r['reasons']))
    def test_classifier_errors_not_converted_to_semantic_allow(self):
        self.config({'goals': {'task_alignment': {'on_error': 'approve'}}})
        s = self.supervisor(classifier=FakeClassifier(failure=True))
        self.task(s)
        r = s.evaluate(self.event())
        self.assertEqual(r['decision'], 'approve')
        self.assertEqual(r['classifier_status'], 'unavailable')
        self.assertNotIn('MUST-NOT-LOG', canonical(r))
    def test_missing_task_abstains(self):
        classifier = FakeClassifier()
        s = self.supervisor(classifier=classifier)
        self.assertEqual(s.evaluate(self.event())['classifier_status'], 'no_pinned_task')
        self.assertEqual(classifier.calls, 0)
    def test_model_alias_requires_capabilities(self):
        goal = {'on': ['model.request'], 'evaluator': 'choice', 'question': 'Choose model tier', 'choices': {'cheap': 'Simple task'}, 'route': {'cheap': 'cheap'}}
        self.config({'goals': {'route': goal}, 'proxy': {'models': {'cheap': {'alias': 'cheap-alias', 'capabilities': ['text']}}}})
        s = self.supervisor(classifier=FakeClassifier())
        result = s.evaluate(self.event('model.request', capabilities=['text', 'tools']))
        self.assertNotIn('model', result)
        result = s.evaluate(self.event('model.request', capabilities=['text']))
        self.assertEqual(result['model'], 'cheap-alias')
    def test_event_store_contains_no_raw_tool_payload(self):
        s = self.supervisor()
        s.evaluate(self.event(input={'password': 'highly-private-example-password', 'command': 'echo raw-code-MUST-NOT-STORE'}))
        content = (self.home / 'state.sqlite3').read_bytes()
        wal = self.home / 'state.sqlite3-wal'
        if wal.exists():
            content += wal.read_bytes()
        self.assertNotIn(b'highly-private-example-password', content)
        self.assertNotIn(b'raw-code-MUST-NOT-STORE', content)
    def test_unknown_outcome_not_a_success(self):
        s = self.supervisor()
        for _ in range(5):
            s.evaluate(self.event('tool.after', success=None))
        self.assertEqual(s.store.report()['automation_candidates'], [])


class ProviderTests(unittest.TestCase):
    def test_jev_contract_and_validation(self):
        config = {**DEFAULTS['decision'], 'provider': 'jev'}
        goals = {'a': {'question': 'Choose', 'choices': {'yes': 'Yes'}}}
        with mock.patch.dict('os.environ', {'TYPESAFE_API_KEY': 'fake'}), mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'a': {'choice': 'yes'}}}) as post:
            self.assertEqual(Classifier(config).decide({'password': 'secret'}, goals), {'a': 'yes'})
            self.assertNotIn('secret', post.call_args.args[1]['state'])
            self.assertEqual(post.call_args.args[1]['questions']['a']['type'], 'choice')
    def test_invalid_jev_choice_rejected(self):
        config = {**DEFAULTS['decision'], 'provider': 'jev'}
        with mock.patch.dict('os.environ', {'TYPESAFE_API_KEY': 'fake'}), mock.patch('gw_supervisor.providers.post_json', return_value={'answers': {'a': {'choice': 'arbitrary'}}}):
            with self.assertRaises(ValueError):
                Classifier(config).decide({}, {'a': {'question': '?', 'choices': {'yes': 'Yes'}}})
    def test_oversized_classifier_input_abstains(self):
        config = {**DEFAULTS['decision'], 'provider': 'http', 'max_state_chars': 10}
        with self.assertRaises(RuntimeError):
            Classifier(config).decide({'content': 'x' * 100}, {})
    def test_unsupported_authority_obligations_deny(self):
        with mock.patch('gw_builtin.governance.post_json', return_value={'decision': 'allow', 'obligations': ['unknown']}):
            self.assertEqual(HttpAuthority({'endpoint': 'https://example.test'}).authorize({})['decision'], 'deny')
    def test_endpoint_restrictions(self):
        self.assertEqual(safe_endpoint('http://127.0.0.1:7777'), 'http://127.0.0.1:7777')
        for url in ('http://example.com', 'https://user:pass@example.com', 'file:///tmp/x'):
            with self.assertRaises(ValueError):
                safe_endpoint(url)


class ProxyTests(Fixture):
    def test_json_compaction_preserves_strings_and_numeric_spelling(self):
        text = '{ "n": 1.0000000000000000000001, "s": " two  spaces ", "e": 1e+30 }'
        result = compact_json(text)
        self.assertEqual(result, '{"n":1.0000000000000000000001,"s":" two  spaces ","e":1e+30}')
    def test_invalid_json_and_duplicate_keys_untouched(self):
        for text in ('logs   remain', '{ "x":1, "x": 2 }', '{ "x": NaN }'):
            self.assertEqual(compact_json(text), text)
    def test_code_inside_json_string_is_unchanged(self):
        text = json.dumps({'code': 'function x() {\n  return "a b";\n}'}, indent=4)
        self.assertEqual(json.loads(compact_json(text)), json.loads(text))
    def test_compaction_does_not_modify_tools_or_assistant_calls(self):
        p = {'tools': [{'type': 'function', 'function': {'name': 'x'}}], 'messages': [{'role': 'assistant', 'content': '{ "x": 1 }', 'tool_calls': [{'id': 'abc', 'arguments': '{ "x": 1 }'}]}, {'role': 'tool', 'tool_call_id': 'abc', 'content': '{ "x": 1 }'}]}
        result = compact_tools(p)
        self.assertEqual(result['messages'][0], p['messages'][0])
        self.assertEqual(result['tools'], p['tools'])
        self.assertEqual(result['messages'][1]['tool_call_id'], 'abc')
        self.assertEqual(result['messages'][1]['content'], '{"x":1}')
    def test_anthropic_tool_result_compaction(self):
        p = {'messages': [{'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': '{ "a": 1 }'}, {'type': 'image', 'source': {'data': 'abc'}}]}]}
        result = compact_tools(p)
        self.assertEqual(result['messages'][0]['content'][0]['content'], '{"a":1}')
        self.assertEqual(result['messages'][0]['content'][1], p['messages'][0]['content'][1])
    def test_responses_tool_result_compaction(self):
        p = {'input': [{'type': 'function_call_output', 'call_id': 'a', 'output': '{ "a": 1 }'}]}
        self.assertEqual(compact_tools(p)['input'][0]['output'], '{"a":1}')
    def test_task_injection_idempotent_all_formats(self):
        for wire, p in [('chat', {'messages': []}), ('anthropic', {'system': 'Existing'}), ('responses', {'instructions': 'Existing'})]:
            first = inject_task(p, 'Do the work', wire)
            self.assertEqual(inject_task(first, 'Do the work', wire), first)
    def test_task_injection_preserves_signed_thinking(self):
        p = {'system': [], 'messages': [{'role': 'assistant', 'content': [{'type': 'thinking', 'thinking': 'hidden', 'signature': 'sig'}]}]}
        self.assertEqual(inject_task(p, 'Task', 'anthropic')['messages'], p['messages'])
    def test_proxy_cap_and_measurement(self):
        self.config({'proxy': {'max_output_tokens': 100, 'compact_tool_json': True, 'inject_task': True}})
        s = self.supervisor()
        self.task(s)
        p = {'model': 'x', 'messages': [{'role': 'tool', 'content': '{ "a": 1 }'}], 'max_tokens': 200}
        result = process_request(s, self.event(), p)
        self.assertEqual(result['payload']['max_tokens'], 100)
        self.assertIn('bytes', result['transform']['measurement'])
        self.assertEqual(p['max_tokens'], 200)
    def test_response_unchanged_and_usage_deduplicated(self):
        s = self.supervisor()
        response = {'model': 'x', 'choices': [{'message': {'refusal': 'no', 'tool_calls': [{'id': 'a', 'function': {'arguments': '{}'}}]}}], 'usage': {'prompt_tokens': 12, 'completion_tokens': 3}}
        context = self.event(id='request1')
        self.assertEqual(process_response(s, context, response)['payload'], response)
        process_response(s, context, response)
        self.assertEqual(s.store.report()['usage']['input_tokens'], 12)
        self.assertEqual(s.store.report()['usage']['calls'], 1)
    def test_proxy_detected_secret_blocks_when_enabled(self):
        self.config({'proxy': {'block_detected_secrets': True}})
        s = self.supervisor()
        r = process_request(s, self.event(), {'messages': [{'role': 'user', 'content': 'password=example-secret'}]})
        self.assertEqual(r['decision'], 'deny')


class UtilityTests(unittest.TestCase):
    def test_nonfinite_and_duplicate_json_rejected(self):
        for value in ('{"x":NaN}', '{"x":1,"x":2}'):
            with self.assertRaises(ValueError):
                strict_json(value)
        for value in (float('nan'), float('inf'), True, -1, 2):
            with self.assertRaises(ValueError):
                finite(value)
    def test_redaction_recurses(self):
        self.assertEqual(redact({'nested': [{'password': 'value'}]})['nested'][0]['password'], '[REDACTED]')
        self.assertEqual(redact({'credential_ref': 'credential://vault/item'}), {'credential_ref': 'credential://vault/item'})
    def test_rule_matching_no_eval(self):
        self.assertTrue(matches({'tool': 'Bash', 'input': {'command': 'git status'}}, {'tool': ['Bash', 'Shell'], 'input.command': 'git *'}))
        self.assertFalse(matches({'tool': 'Read'}, {'tool': 'Bash'}))


if __name__ == '__main__':
    unittest.main()
