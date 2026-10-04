"""Twelve domain registrations, shipped together. None loads a model or source.

A distribution is a delivery unit; a plugin is an independently replaceable
runtime capability. Small domain helpers do not need their own distribution.
"""
from __future__ import annotations
import copy
import importlib
from types import MethodType
from gw_supervisor.api import Advice, Assessment, Plugin, ConfigSection, Evaluator, Command, Tool, service, safe_endpoint
from .defaults import REFERENCE_DEFAULTS, DEFAULT_PLUGINS

VERSION = '0.1.1'


def call(module, method):
    def invoke(*args, **kwargs):
        return getattr(importlib.import_module('gw_builtin.' + module), method)(*args, **kwargs)
    return invoke


def factory(name):
    return lambda host: getattr(importlib.import_module('gw_builtin.services'), name)()


def object_config(value):
    if not isinstance(value, dict):
        raise ValueError('Configuration section must be an object')


def section(name, validator=object_config, *, project=False, host_only=(), agent_writable=False, agent_validate=None):
    value = REFERENCE_DEFAULTS
    for part in name.split('.'):
        value = value[part]
    return ConfigSection(name, copy.deepcopy(value), validator, project, host_only, agent_writable, agent_validate)


def commands(*names):
    # Shared compatibility parser is just UI glue; runtime controls which commands
    # are visible, and new plugins can register their own without touching it.
    return tuple(Command(name, call('cli', 'main')) for name in names)


TOOL_OWNERS = {
    'agent': ('gw_status', 'gw_setup_options', 'gw_configure_plan', 'gw_configure_apply', 'gw_task_set', 'gw_runtime_inspect'),
    'inference': ('gw_decision_check', 'gw_models_select'),
    'context': ('gw_context_compile',),
    'knowledge': ('gw_knowledge',),
    'observe': ('gw_trace_query', 'gw_trace_start', 'gw_trace_finish', 'gw_dashboard_open'),
    'learning': ('gw_learning_query',),
}
MUTATING = {'gw_configure_plan', 'gw_configure_apply', 'gw_task_set', 'gw_trace_start',
            'gw_trace_finish', 'gw_dashboard_open', 'gw_models_select', 'gw_decision_check'}
WORLD = {'gw_models_select', 'gw_decision_check', 'gw_knowledge', 'gw_context_compile'}


def tools(domain):
    def bind(name):
        def bind_to(host):
            module = importlib.import_module('gw_builtin.agent_tools.' + domain)
            return MethodType(getattr(module, name), host)
        return bind_to
    return tuple(Tool(name, bind(name), name in MUTATING, name in WORLD, name == 'gw_configure_apply') for name in TOOL_OWNERS.get(domain, ()))


def validate_policy(config):
    from .host import EFFECTS, EVENTS
    for gid, goal in config['goals'].items():
        if not isinstance(goal, dict): raise ValueError('Goal must be an object: ' + gid)
        if goal.get('enabled', True) is False: continue
        if not isinstance(goal.get('on'), list) or not set(goal['on']) <= EVENTS:
            raise ValueError('Invalid events for ' + gid)
        if goal.get('evaluator') not in {'choice', 'metric', 'repetition', 'registry'}:
            raise ValueError('Unknown evaluator for ' + gid)
        if goal['evaluator'] == 'choice' and (not isinstance(goal.get('choices'), dict) or not goal['choices'] or not isinstance(goal.get('question'), str)):
            raise ValueError('Choice goal needs question and choices')
        if 'inputs' in goal:
            if goal['evaluator'] != 'choice':
                raise ValueError('Only choice goals declare decision inputs')
            from .decision_cache import validate_inputs
            validate_inputs(goal)
        effects = [*goal.get('effects', {}).values(), goal.get('effect', 'allow'), goal.get('on_error', 'advise')]
        if any(x not in EFFECTS for x in effects): raise ValueError('Invalid effect in ' + gid)
    for rid, rule in config['rules'].items():
        if not isinstance(rule, dict) or rule.get('effect') not in EFFECTS or not isinstance(rule.get('when'), dict):
            raise ValueError('Invalid rule: ' + rid)


def validate_authority(config):
    if config['authority'].get('endpoint'):
        safe_endpoint(config['authority']['endpoint'])
        if config['mode'] == 'baseline':
            raise ValueError('Baseline cannot bypass a configured external authority')


def validate_proxy(value):
    object_config(value)
    if type(value.get('max_output_tokens', 0)) is not int or value.get('max_output_tokens', 0) < 0:
        raise ValueError('max_output_tokens must be a nonnegative integer')


def plugin_settings(name):
    return lambda value: call('plugins', 'validate_plugins')({name: value})


def normalize_inference(event):
    if event['type'] == 'inference.select' or 'requirements' in event:
        return {'requirements': service('inference').normalize_requirements(event.get('requirements'))}
    return {}


def validate_agent_observation(patch, config):
    if not isinstance(patch, dict) or set(patch) - {'enabled', 'preview_chars'}:
        raise ValueError('Agent observation setup accepts enabled and preview_chars only')


def observe_event(ctx, result):
    observer = ctx.services.require('observation')
    observer.publish_intercept(ctx.home, ctx.session, ctx.event, result)
    return {k: result[k] for k in ('trace_id', 'observability_error') if k in result}


def state():
    return Plugin('gw.state', VERSION, services={'state': factory('StateService')}, commands=commands('status'))


def policy():
    return Plugin('gw.policy', VERSION, requires=('state', 'inference'), services={'policy': factory('PolicyService')},
        config=tuple(section(name, project=True, agent_writable=True) for name in ('rules', 'registry', 'goals')),
        validate=validate_policy, evaluators=(Evaluator('gw.policy.assess', 'local', call('policy', 'assess')),),
        baseline=call('policy', 'baseline'), commands=commands('task'))


def inference():
    return Plugin('gw.inference', VERSION, services={'inference': factory('InferenceService')},
        config=(section('decision', call('decision_transport', 'validate_decision'), agent_writable=True),
                section('inference', call('models', 'validate_registry'), project=True, agent_writable=True)),
        evaluators=(Evaluator('gw.inference.select', 'plan', call('routing', 'assess'), ('model.request', 'inference.select')),),
        normalize_event=normalize_inference, commands=commands('setup', 'decision', 'models', 'enable-jev'), tools=tools('inference'))


def governance():
    return Plugin('gw.governance', VERSION, config=(section('authority'),), validate=validate_authority,
        evaluators=(Evaluator('gw.governance.authorize', 'authority', call('governance', 'assess')),), baseline=call('governance', 'baseline'))


def context():
    return Plugin('gw.context', VERSION, requires=('state',), services={'context': factory('ContextService')},
        config=(section('context_compiler', call('context', 'validate_context'), project=True, host_only=('sources',), agent_writable=True, agent_validate=call('context', 'validate_agent_patch')),), tools=tools('context'))


def knowledge():
    return Plugin('gw.knowledge', VERSION, services={'knowledge': factory('KnowledgeService')},
        config=(section('knowledge', call('knowledge', 'validate_knowledge'), agent_writable=True, agent_validate=call('knowledge', 'validate_agent_patch')),), commands=commands('knowledge'), tools=tools('knowledge'))


def observe():
    return Plugin('gw.observe', VERSION, services={'observation': factory('ObservationService')},
        config=(section('plugins.observe', plugin_settings('observe'), agent_writable=True, agent_validate=validate_agent_observation),), commands=commands('trace'),
        observe=observe_event, tools=tools('observe'))


def learning():
    return Plugin('gw.learning', VERSION, requires=('state',), services={'learning': factory('LearningService')},
        config=(section('plugins.learning', plugin_settings('learning')),), commands=commands('learn'), tools=tools('learning'))


def sync():
    return Plugin('gw.sync', VERSION, config=(section('plugins.sync', plugin_settings('sync')),), commands=commands('sync'))


def harness():
    return Plugin('gw.harness', VERSION, services={'harness': factory('HarnessService')},
        commands=commands('bootstrap', 'uninstall', 'doctor') + (Command('hook', call('hook_transport', 'main')),))


def preflight(ctx):
    reason = ctx.event.get('preflight_denial')
    return Assessment((Advice('deny', str(reason)),)) if reason else Assessment()


def gateway():
    return Plugin('gw.gateway', VERSION, requires=('inference', 'state'), services={'gateway': factory('GatewayService')},
        config=(section('proxy', validate_proxy, project=True),),
        evaluators=(Evaluator('gw.gateway.preflight', 'local', preflight, ('model.request',)),), commands=commands('serve', 'proxy-init'))


def agent():
    return Plugin('gw.agent', VERSION, requires=('state',), commands=commands('agent', 'agent-guide'), tools=tools('agent'))
