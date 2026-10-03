"""A complete extension using only the versioned public GW plugin API."""
from gw_supervisor.api import Advice, Assessment, ConfigSection, Evaluator, Plugin, Tool


def validate(value):
    if not isinstance(value, dict) or set(value) != {'enabled'} or type(value['enabled']) is not bool:
        raise ValueError('review_demo requires enabled: true|false')


def assess(ctx):
    enabled = ctx.config['review_demo']['enabled']
    proposed = ctx.event.get('input', {}).get('command')
    if enabled and proposed == 'echo GW_EXTENSION_REVIEW':
        return Assessment((Advice('approve', 'Explicit demonstration review gate'),),
                          details={'review_demo': {'matched': True}})
    return Assessment()


def bind_status(host):
    def gw_review_demo_status() -> dict:
        """Inspect the review-demo configuration for this bound project."""
        return {'project': str(host.project), 'settings': host.configuration()['review_demo']}
    return gw_review_demo_status


def plugin():
    return Plugin(id='gw.example.review', version='0.1.0',
        config=(ConfigSection('review_demo', {'enabled': True}, validate, project=True, agent_writable=True),),
        evaluators=(Evaluator('gw.example.review', 'local', assess, ('tool.before',)),),
        tools=(Tool('gw_review_demo_status', bind_status),))
