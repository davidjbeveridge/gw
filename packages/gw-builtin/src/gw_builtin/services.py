"""Reference service implementations. Peers resolve these contracts through the host."""
from __future__ import annotations
import importlib
from gw_supervisor.api import service


class InferenceService:
    def create(self, config):
        from .decisions import make_decider
        return make_decider(config)
    def decision_config(self, config):
        from .models import decision_config
        return decision_config(config)
    def normalize_requirements(self, value):
        from .models import requirements
        return requirements(value)
    def select(self, registry, request, decider, state):
        from .models import select
        return select(registry, request, decider, state)
    def append_calls(self, *args):
        from .decisions import append_calls
        return append_calls(*args)
    def setup_options(self):
        from .decision_setup import manifest
        return manifest()
    def probe(self, config):
        from .decision_setup import probe
        return probe(config)


class StateService:
    def trace_source(self, home):
        return {'path': home / 'state.sqlite3', 'kind': 'gw.sqlite', 'source_id': 'gw-core'}
    def open(self, home):
        from .store import Store
        return Store(home)


class PolicyService:
    def matches(self, event, conditions):
        from .matching import matches
        return matches(event, conditions)


class ContextService:
    def wants_delivery(self, config, target):
        c = config.get('context_compiler', {})
        return c.get('enabled', False) and c.get('delivery') == target
    def compile(self, *args, **kwargs):
        from .context import compile_context
        return compile_context(*args, **kwargs)
    def for_supervisor(self, *args, **kwargs):
        from .context import supervisor_context
        return supervisor_context(*args, **kwargs)
    def inject(self, *args, **kwargs):
        from .context import inject_context
        return inject_context(*args, **kwargs)
    def relative_path(self, path):
        from .context import relative_path
        return relative_path(path)
    def defaults(self):
        from .defaults import DEFAULT_CONTEXT
        return DEFAULT_CONTEXT


class KnowledgeService:
    def open(self, *args, **kwargs):
        from .knowledge import open_service
        return open_service(*args, **kwargs)
    def call(self, *args, **kwargs):
        from .knowledge import call
        return call(*args, **kwargs)
    def evidence(self, home, root, client, *, query, mode, limit, max_chars):
        # Only this knowledge adapter knows gw_knowledge's request/cache types.
        from gw_knowledge import SearchRequest
        with self.open(home, root, client) as access:
            request = SearchRequest(access.scope, '' if mode == 'structured' else query[:4096], mode=mode, limit=limit)
            return access.cache.assemble(access.provider, request, max_chars=max_chars)


class ObservationService:
    # Resolve on each invocation so legacy callers and injected test observers
    # still see the same implementation object. Other plugins never import it.
    def enabled(self, config):
        from .plugins import enabled
        return enabled(config)
    def proposal(self, event, config):
        from .plugins import proposal
        return proposal(event, config)
    def publish_intercept(self, *args, **kwargs):
        from .plugins import publish_intercept
        return publish_intercept(*args, **kwargs)
    def publish_component(self, *args, **kwargs):
        from .plugins import publish_component
        return publish_component(*args, **kwargs)
    def record_usage(self, home, config, identity, usage, *, model, request_id, provider='generic', cost_usd=None, billing_kind='unknown', start_ns, end_ns):
        from gw_observe.contract import normalize_usage
        from gw_supervisor.api import digest
        normalized = normalize_usage(usage, provider)
        if cost_usd is not None: normalized.update(normalize_usage({'cost_usd': cost_usd}))
        self.publish_component(home, config, identity, 'model.usage',
            {'request_id':request_id, 'model':model, 'usage':normalized, 'usage_source':'proxy',
             'billing_kind':billing_kind, 'cost_basis':'provider_reported' if 'cost_usd' in normalized else 'unknown'},
            start_ns=start_ns, end_ns=end_ns, event_id=digest(['model.usage',identity['session_id'],request_id]))
    def repository(self, *args, **kwargs):
        from .plugins import trace_repository
        return trace_repository(*args, **kwargs)
    def dashboard(self, *args, **kwargs):
        from .dashboard import open_dashboard
        return open_dashboard(*args, **kwargs)


class HarnessService:
    def bootstrap(self, *args, **kwargs):
        from .adapters import bootstrap
        return bootstrap(*args, **kwargs)
    def bootstrap_tools(self, *args, **kwargs):
        from .agent_bootstrap import bootstrap_agent_tools
        return bootstrap_agent_tools(*args, **kwargs)
    def normalize(self, *args, **kwargs):
        from .adapters import normalize
        return normalize(*args, **kwargs)
    def response(self, *args, **kwargs):
        from .adapters import native_response
        return native_response(*args, **kwargs)


class GatewayService:
    def request(self, *args, **kwargs):
        from .proxy import process_request
        return process_request(*args, **kwargs)
    def response(self, *args, **kwargs):
        from .proxy import process_response
        return process_response(*args, **kwargs)


class LearningService:
    def query(self, home, config, proposal_id=''):
        from gw_learning.engine import LearningCoordinator
        c = config['plugins']['learning']
        if c['provider'] != 'local':
            raise ValueError('Use the configured learning provider query interface')
        with LearningCoordinator(c['options'].get('directory', str(home / 'learning'))) as coordinator:
            return coordinator.get(proposal_id) if proposal_id else {'proposals': coordinator.list()}
