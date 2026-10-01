import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from gw_supervisor.adapters import PROFILES, bootstrap, native_response, normalize, plugin_source, settings_for
from gw_supervisor.util import write_json

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def test_native_allow_does_not_bypass_permissions(self):
        for agent in PROFILES:
            self.assertEqual(native_response(agent, 'pre', {'decision': 'allow', 'advice': []}), {})
    def test_approval_mapping(self):
        result = {'decision': 'approve', 'reason': 'Review it', 'advice': []}
        self.assertEqual(native_response('claude', 'pre', result)['hookSpecificOutput']['permissionDecision'], 'ask')
        self.assertEqual(native_response('codex', 'pre', result)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(native_response('cursor', 'pre', result)['permission'], 'deny')
        self.assertEqual(native_response('gemini', 'pre', result)['decision'], 'deny')
        both = native_response('copilot', 'pre', result)
        self.assertEqual(both['permissionDecision'], both['hookSpecificOutput']['permissionDecision'])
    def test_camel_and_snake_normalization(self):
        snake = {'session_id': 's', 'cwd': str(ROOT), 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}, 'tool_use_id': 'id'}
        camel = {'sessionId': 's', 'cwd': str(ROOT), 'toolName': 'Bash', 'toolArgs': '{"command":"ls"}', 'toolUseId': 'id'}
        self.assertEqual(normalize('copilot', 'pre', snake), normalize('copilot', 'pre', camel))
    def test_cursor_workspace_fallback(self):
        event = normalize('cursor', 'pre', {'conversation_id': 's', 'workspace_roots': [str(ROOT)], 'tool_name': 'Shell', 'tool_input': {'command': 'ls'}})
        self.assertEqual(event['project'], str(ROOT))
    def test_failure_extraction(self):
        raw = {'session_id': 's', 'cwd': str(ROOT), 'tool_name': 'Bash', 'tool_input': {}}
        for output in ({'exit_code': 1}, {'exitCode': 2}, {'error': 'bad'}, {'isError': True}):
            self.assertFalse(normalize('codex', 'post', {**raw, 'tool_response': output})['success'])
    def test_cursor_stringified_exit_code(self):
        raw = {'session_id': 's', 'cwd': str(ROOT), 'tool_name': 'Shell', 'tool_input': {}, 'tool_output': '{"exitCode":1}'}
        self.assertFalse(normalize('cursor', 'post', raw)['success'])
    def test_missing_session_fails(self):
        with self.assertRaises(ValueError):
            normalize('claude', 'pre', {'tool_name': 'Bash', 'tool_input': {}})
    def test_settings_preserve_unrelated_hooks_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            for agent, profile in PROFILES.items():
                if agent == 'opencode':
                    continue
                event = next(k for k, v in profile['events'].items() if v == 'pre')
                handler = {'type': 'command', 'command': 'echo existing'}
                entry = {'matcher': '*', 'hooks': [handler]} if profile['grouped'] else handler
                original = {'model': 'unchanged', 'hooks': {event: [entry]}}
                one = settings_for(original, agent, pathlib.Path(d))
                self.assertEqual(settings_for(one, agent, pathlib.Path(d)), one)
                removed = settings_for(one, agent, pathlib.Path(d), False)
                self.assertEqual(removed['hooks'][event], original['hooks'][event])
                self.assertEqual(removed['model'], 'unchanged')
                self.assertEqual(original['hooks'][event], [entry])
    def test_mixed_group_only_removes_gw_handler(self):
        home = pathlib.Path('/tmp/gw-test')
        initial = settings_for({}, 'claude', home)
        initial['hooks']['PreToolUse'][0]['hooks'].append({'type': 'command', 'command': 'echo keep'})
        result = settings_for(initial, 'claude', home, False)
        self.assertEqual(result['hooks']['PreToolUse'][0]['hooks'][0]['command'], 'echo keep')
    def test_bootstrap_dry_run_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            home, user = root / 'state', root / 'user'
            target = user / '.claude/settings.json'
            write_json(target, {'model': 'keep'})
            before = target.read_text()
            bootstrap(home, ['claude'], user_home=user, dry_run=True)
            self.assertEqual(target.read_text(), before)
            bootstrap(home, ['claude'], user_home=user)
            self.assertTrue(list((home / 'backups').iterdir()))
            self.assertEqual(json.loads(target.read_text())['model'], 'keep')
    def test_unrelated_opencode_plugin_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            path = root / '.opencode/plugins/gw.mjs'
            path.parent.mkdir(parents=True)
            path.write_text('// my plugin')
            with self.assertRaises(ValueError):
                bootstrap(root / 'state', ['opencode'], project=root)
            self.assertEqual(path.read_text(), '// my plugin')
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for plugin syntax coverage')
    def test_opencode_plugin_parses(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'gw.mjs'
            path.write_text(plugin_source(pathlib.Path(d) / 'state'))
            subprocess.run(['node', '--check', str(path)], check=True, capture_output=True)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'state'
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        (self.project / '.git').mkdir()
        self.env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, '-m', 'gw_supervisor', '--home', str(self.home), *args], input=stdin, text=True, capture_output=True, cwd=self.project, env=self.env, timeout=20)
    def test_all_bootstraps_preserve_settings(self):
        result = self.cli('bootstrap', '--all', '--project', str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        changes = json.loads(result.stdout)['changes']
        self.assertEqual(len(changes), 6)
        second = json.loads(self.cli('bootstrap', '--all', '--project', str(self.project)).stdout)
        self.assertTrue(all(not x['changed'] for x in second['changes']))
    def test_corrupt_hook_payload_has_native_deny_exit_zero(self):
        result = self.cli('hook', 'codex', 'pre', stdin='not json')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
    def test_hook_subprocess_rejects_configured_canary(self):
        write_json(self.home / 'config.json', {'rules': {'canary': {'when': {'input.command': 'echo GW_CANARY_DENY'}, 'effect': 'deny'}}})
        raw = {'session_id': 's', 'cwd': str(self.project), 'tool_name': 'Bash', 'tool_input': {'command': 'echo GW_CANARY_DENY'}}
        result = self.cli('hook', 'claude', 'pre', stdin=json.dumps(raw))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
    def test_generic_hook_end_to_end(self):
        event = {'type': 'tool.before', 'client': 'custom', 'session': 'a', 'project': str(self.project), 'tool': 'read', 'input': {}}
        result = self.cli('hook', 'generic', 'pre', stdin=json.dumps(event))
        self.assertEqual(json.loads(result.stdout)['decision'], 'allow')
    def test_proxy_init_does_not_embed_keys(self):
        path = self.root / 'proxy.yaml'
        result = self.cli('proxy-init', '--model', 'openai/example-model', '--output', str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('os.environ/GW_UPSTREAM_API_KEY', path.read_text())
        self.assertIn('gw_supervisor.litellm.gw_callback', path.read_text())
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_opencode_plugin_really_blocks_via_python_subprocess(self):
        write_json(self.home / 'config.json', {'rules': {'canary': {'when': {'input.command': 'echo GW_CANARY_DENY'}, 'effect': 'deny'}}})
        plugin = self.root / 'plugin.mjs'
        plugin.write_text(plugin_source(self.home))
        script = self.root / 'run.mjs'
        script.write_text("import { GWPlugin } from './plugin.mjs';\n" + 'const hooks = await GWPlugin({directory: ' + json.dumps(str(self.project)) + '});\n' + "try { await hooks['tool.execute.before']({tool:'bash',sessionID:'node-test',callID:'one'}, {args:{command:'echo GW_CANARY_DENY'}}); process.exit(2); } catch(e) { if (!e.message.includes('canary')) { console.error(e); process.exit(3); } console.log('blocked'); }\n")
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'blocked')


if __name__ == '__main__':
    unittest.main()
