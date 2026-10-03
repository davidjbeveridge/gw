"""Small runtime kernel: lifecycle, dispatch, verdict reduction and persistence.

No model, goal, retrieval, SQLite, harness, or dashboard implementation lives here.
Plugins contribute assessments; only this reducer produces an executable verdict.
"""
from __future__ import annotations

import copy
import pathlib
import time
import uuid
from .api import Advice, Assessment, EvaluationContext, PluginError
from .config import EVENTS, home_path, initialize, project_root, resolve
from .registry import PluginManager, manager_for, CURRENT
from .util import canonical, digest, redact

RANK = {'allow': 0, 'advise': 1, 'approve': 2, 'deny': 3}
PROTECTED = {'version', 'decision', 'reason', 'reasons', 'advice', 'session_id',
             'policy_hash', 'config_status', 'runtime_manifest_hash', 'runtime_steps', 'plugin_errors', 'would_decision'}


def validate_event(event):
    if not isinstance(event, dict) or event.get('type') not in EVENTS:
        raise ValueError('Unknown supervisor event')
    out = copy.deepcopy(event)
    for key in ('client', 'session', 'project'):
        if not isinstance(out.get(key), str) or not out[key].strip() or len(out[key]) > 4096:
            raise ValueError('Event needs a nonempty ' + key)
    out['project'] = str(project_root(out['project']))
    out.setdefault('id', str(uuid.uuid4()))
    if not isinstance(out['id'], str) or not out['id'] or len(out['id']) > 4096:
        raise ValueError('Invalid event id')
    if out['type'].startswith('tool.'):
        if not isinstance(out.get('tool'), str) or not out['tool'] or not isinstance(out.get('input', {}), dict):
            raise ValueError('Tool event requires a tool name and object input')
    if 'success' in out and out['success'] is not None and type(out['success']) is not bool:
        raise ValueError('success must be true, false, or null')
    canonical(out)
    return out


def matches(event, conditions):
    """Compatibility convenience; matching belongs to the selected policy service."""
    from .api import service
    return service('policy').matches(event, conditions)


class Supervisor:
    def __init__(self, home=None, classifier=None, authority=None, *, plugins=None):
        self.home = home_path(str(home) if home is not None else None)
        initialize(self.home)
        self._injected = plugins is not None
        self._owned = plugins is not None or CURRENT.get() is None
        self.manager = PluginManager(plugins) if plugins is not None else manager_for(self.home)
        try:
            self.store = self.manager.require('state').open(self.home)
        except BaseException:
            if self._owned: self.manager.close()
            raise
        self.classifier, self.authority = classifier, authority
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.store.close()
            finally:
                if self._owned:
                    self.manager.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _select(self, client):
        if not self._injected:
            candidate = manager_for(self.home, client)
            if candidate.manifest() != self.manager.manifest():
                self.store.close()
                if self._owned: self.manager.close()
                self._owned = True
                self.manager = candidate
                self.store = candidate.require('state').open(self.home)
            elif candidate is not self.manager:
                candidate.close()

    def _session(self, event):
        config, status = resolve(self.home, pathlib.Path(event['project']), event['client'], manager=self.manager)
        config['_runtime_manifest'] = self.manager.manifest()
        session = self.store.session(event, config)
        pinned = session['config'].get('_runtime_manifest')
        if pinned is not None and pinned != config['_runtime_manifest']:
            raise PluginError('Plugin composition changed during the session; start a new native session')
        # Existing sessions from before the plugin runtime must not silently migrate.
        if pinned is None:
            raise PluginError('Legacy session needs a fresh native session after runtime migration')
        return session, status

    def _normalize(self, event):
        for key in self.manager.order:
            normalize = self.manager.plugins[key].normalize_event
            if normalize:
                fields = normalize(copy.deepcopy(event))
                if not isinstance(fields, dict) or set(fields) & {'project', 'client', 'session', 'id', 'type', 'tool', 'input'}:
                    raise PluginError('Normalizer tried to replace event identity or proposed action')
                event.update(fields)
        return event

    def scope(self, client="generic"):
        """Bind this runtime for a transport or adapter invocation."""
        self._select(client)
        return self.manager.activate()

    def session_context(self, event):
        event = validate_event(event)
        self._select(event['client'])
        with self.manager.activate():
            return self._session(self._normalize(event))[0]

    def evaluate(self, source):
        started_ns, started_clock = time.time_ns(), time.perf_counter()
        event = validate_event(source)
        self._select(event['client'])
        with self.manager.activate():
            event = self._normalize(event)
            session, status = self._session(event)
            previous = self.store.cached_event(session['id'], event)
            if previous:
                return {**previous, 'duplicate': True}
            config = session['config']
            result = {'version': 1, 'decision': 'allow', 'reasons': [], 'advice': [],
                      'session_id': session['id'], 'policy_hash': digest(config),
                      'config_status': status, 'runtime_manifest_hash': digest(self.manager.manifest()), 'runtime_steps': []}
            updates, metadata_owners = {}, {}

            def context():
                return EvaluationContext(self.home, copy.deepcopy(event), copy.deepcopy(session),
                    copy.deepcopy(config), copy.deepcopy(result), self.manager, self.store,
                    {'classifier': self.classifier, 'authority': self.authority})

            def apply(advice):
                if not isinstance(advice, Advice) or advice.effect not in RANK or not isinstance(advice.reason, str):
                    raise PluginError('Invalid plugin effect')
                reason = str(redact(advice.reason))[:2000]
                if RANK[advice.effect] > RANK[result['decision']]:
                    result['decision'] = advice.effect
                if advice.effect != 'allow': result['reasons'].append(reason)
                if advice.effect == 'advise': result['advice'].append(reason)

            def metadata(plugin, values):
                if not isinstance(values, dict) or set(values) & PROTECTED:
                    raise PluginError('Plugin cannot overwrite runtime verdict fields')
                if len(canonical(values)) > 262144:
                    raise PluginError('Plugin metadata exceeds budget')
                for key in values:
                    if key in metadata_owners and metadata_owners[key] != plugin:
                        raise PluginError('Two plugins own metadata field: ' + key)
                    metadata_owners[key] = plugin
                result.update(copy.deepcopy(values))

            def soften():
                if config['mode'] == 'observe' and result['decision'] in {'deny', 'approve'}:
                    result['would_decision'] = result['decision']
                    result['decision'] = 'advise'
                    result['advice'].extend(result['reasons'])

            if config['mode'] == 'baseline':
                for owner, evaluator in self.manager.evaluators:
                    if evaluator.phase == 'authority' and self.manager.plugins[owner].baseline is None:
                        raise PluginError('Authority plugin must explicitly validate baseline: ' + owner)
                for key in self.manager.order:
                    hook = self.manager.plugins[key].baseline
                    if hook:
                        metadata(key, dict(hook(context())))
                result['reason'] = 'Measurement-only baseline; GW did not evaluate policy or change the action'
            else:
                authority_phase = False
                for owner, evaluator in self.manager.evaluators:
                    if evaluator.events and event['type'] not in evaluator.events:
                        continue
                    if evaluator.phase == 'authority' and not authority_phase:
                        soften(); authority_phase = True
                    began = time.perf_counter(); step = {'plugin': owner, 'evaluator': evaluator.name,
                        'phase': evaluator.phase, 'status': 'completed'}
                    try:
                        assessment = evaluator.evaluate(context())
                        if not isinstance(assessment, Assessment):
                            raise PluginError('Evaluator must return Assessment')
                        # Validate the entire contribution before applying any part.
                        for effect in assessment.effects:
                            if not isinstance(effect, Advice) or effect.effect not in RANK or not isinstance(effect.reason, str):
                                raise PluginError('Invalid assessment effect')
                        if len(assessment.effects) > 256 or len(canonical([dict(assessment.state), dict(assessment.audit)])) > 262144:
                            raise PluginError('Assessment exceeds its contribution budget')
                        if 'audit' in assessment.details:
                            raise PluginError('Supply audit fields through Assessment.audit')
                        next_audit = copy.deepcopy(result.get('audit', {}))
                        for key, value in assessment.audit.items():
                            if isinstance(value, list):
                                if key in next_audit and not isinstance(next_audit[key], list):
                                    raise PluginError('Conflicting audit field: ' + key)
                                next_audit.setdefault(key, []).extend(copy.deepcopy(value))
                            elif key in next_audit and next_audit[key] != value:
                                raise PluginError('Conflicting audit field: ' + key)
                            else: next_audit[key] = copy.deepcopy(value)
                        if len(canonical(next_audit)) > 524288:
                            raise PluginError('Combined audit exceeds its budget')
                        metadata(owner, dict(assessment.details))
                        if assessment.audit: result['audit'] = next_audit
                        for effect in assessment.effects: apply(effect)
                        if assessment.state:
                            updates.setdefault(owner, {}).update(copy.deepcopy(dict(assessment.state)))
                    except Exception as exc:
                        # A broken evaluator cannot become permission through a failed import.
                        step.update(status='error', error=type(exc).__name__)
                        result.setdefault('plugin_errors', []).append({'plugin': owner, 'error': type(exc).__name__})
                        apply(Advice('deny', owner + ': evaluator unavailable; inspect runtime diagnostics'))
                    finally:
                        step['elapsed_ms'] = round((time.perf_counter()-began)*1000, 3)
                        result['runtime_steps'].append(step)
                if not authority_phase: soften()
                if event['type'] in {'tool.after', 'model.response'} and result['decision'] in {'deny', 'approve'}:
                    result['would_decision'] = result['decision']; result['decision'] = 'advise'
                    result['advice'].extend(result['reasons'])
                result['reason'] = '; '.join(dict.fromkeys(result['reasons'])) or 'No supervisor objection; native permissions still apply'
            if 'audit' in result:
                result['audit'].update(start_ns=started_ns, end_ns=time.time_ns(),
                    evaluation_ms=round((time.perf_counter()-started_clock)*1000, 3))
            saved = self.store.commit(session, event, result, updates)
            for key in self.manager.order:
                observer = self.manager.plugins[key].observe
                if observer:
                    try:
                        info = observer(context(), copy.deepcopy(saved))
                        if info:
                            # Compatibility reporting is restricted to non-authoritative fields.
                            if not isinstance(info, dict) or len(canonical(info)) > 32768 or set(info) - {'trace_id', 'observability_error'}:
                                raise PluginError('Observer returned unsupported fields')
                            saved.update(info)
                    except Exception as exc:
                        saved['observability_error'] = type(exc).__name__
            return saved
