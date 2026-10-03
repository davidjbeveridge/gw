"""Public plugin API v1. Plugins import this module, not runtime implementation.

The Python interfaces are in-process contracts, not a sandbox or remote protocol.
Feature packages may depend on this API without depending on any other plugin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import contextlib
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol
from .util import (canonical, digest, finite, redact, read_json, write_json,
                   atomic_write, strict_json, safe_endpoint, post_json)

API_VERSION = 1
Effect = Literal['allow', 'advise', 'approve', 'deny']
Phase = Literal['local', 'plan', 'authority']


class PluginError(RuntimeError):
    """A configuration, compatibility, or lifecycle error; never implicit allow."""


@dataclass(frozen=True)
class Advice:
    effect: Effect
    reason: str = ''


@dataclass(frozen=True)
class Assessment:
    """A contribution, never a replacement for the runtime's final verdict.

    details supplies feature metadata, audit supplies lists/measurements, and
    state is passed to the configured repository under this plugin's identity.
    """
    effects: tuple[Advice, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    audit: Mapping[str, Any] = field(default_factory=dict)
    state: Mapping[str, Any] = field(default_factory=dict)


class Services(Protocol):
    def require(self, name: str) -> Any: ...
    def optional(self, name: str) -> Any | None: ...


class SessionRepository(Protocol):
    """Runtime persistence. Implementations own schema, migration and atomicity."""
    def session(self, event: dict, config: dict) -> dict: ...
    def cached_event(self, session_id: str, event: dict) -> dict | None: ...
    def commit(self, session: dict, event: dict, result: dict, updates: dict) -> dict: ...
    def read_state(self, session_id: str, plugin_id: str) -> dict: ...
    def close(self) -> None: ...


class DecisionService(Protocol):
    def create(self, config: dict) -> Any: ...
    def normalize_requirements(self, value: dict | None) -> dict: ...
    def select(self, registry: dict, request: dict, decider: Any, state: dict) -> dict: ...
    def decision_config(self, config: dict) -> dict: ...
    def append_calls(self, audit: dict, decider: Any, purpose: str, elapsed_ms: float, model: str | None) -> None: ...
    def setup_options(self) -> dict: ...
    def probe(self, config: dict) -> dict: ...


class ContextService(Protocol):
    def wants_delivery(self, config: dict, target: str) -> bool: ...
    def compile(self, home: Path, project: Path, client: str, **kwargs: Any) -> dict: ...
    def for_supervisor(self, home: Path, session: dict, event: dict, state: dict, store: Any) -> tuple[dict, str | None]: ...
    def inject(self, payload: dict, wire: str, packet: dict) -> tuple[dict, bool]: ...
    def defaults(self) -> dict: ...


class KnowledgeAccess(Protocol):
    def open(self, home: Path, project: Path, client: str) -> Any: ...
    def call(self, home: Path, context: dict, method: str, request: dict) -> dict: ...
    def evidence(self, home: Path, project: Path, client: str, *, query: str, mode: str, limit: int, max_chars: int) -> dict: ...


@dataclass(frozen=True)
class EvaluationContext:
    """Detached input snapshots; changing them cannot weaken another contribution."""
    home: Path
    event: dict
    session: dict
    config: dict
    result: dict
    services: Services
    repository: SessionRepository
    overrides: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigSection:
    name: str
    default: Any
    validate: Callable[[Any], None]
    project: bool = False
    # An otherwise project-configurable section can contain host-only fields.
    host_only: tuple[str, ...] = ()
    agent_writable: bool = False
    # Validate a proposed partial operator patch; full validation still follows.
    agent_validate: Callable[[Any, dict], None] | None = None


@dataclass(frozen=True)
class Evaluator:
    name: str
    phase: Phase
    evaluate: Callable[[EvaluationContext], Assessment]
    events: tuple[str, ...] = ()
    # Explicit constraints, not accidental registration/import order.
    after: tuple[str, ...] = ()


@dataclass(frozen=True)
class Command:
    name: str
    run: Callable[[list[str]], Any]
    summary: str = ''


class AgentHost(Protocol):
    home: Path
    project: Path
    client: str
    manage: bool
    def configuration(self) -> dict: ...
    def require_management(self) -> None: ...


@dataclass(frozen=True)
class Tool:
    """Callable signature supplies MCP schema. Binding receives project-scoped host."""
    name: str
    bind: Callable[[AgentHost], Callable]
    mutating: bool = False
    open_world: bool = False
    destructive: bool = False


@dataclass(frozen=True)
class Plugin:
    id: str
    version: str
    api_version: int = API_VERSION
    requires: tuple[str, ...] = ()
    services: Mapping[str, Callable[[Services], Any]] = field(default_factory=dict)
    config: tuple[ConfigSection, ...] = ()
    validate: Callable[[dict], None] | None = None
    evaluators: tuple[Evaluator, ...] = ()
    commands: tuple[Command, ...] = ()
    tools: tuple[Tool, ...] = ()
    normalize_event: Callable[[dict], dict] | None = None
    # Observers receive copies AFTER the canonical commit, never action authority.
    observe: Callable[[EvaluationContext, dict], Mapping[str, Any] | None] | None = None
    # Optional deterministic baseline metadata; must not perform inference.
    baseline: Callable[[EvaluationContext], Mapping[str, Any]] | None = None


def configuration():
    """Public configuration facade, lazily imported to avoid discovery cycles."""
    from . import config
    return config


def service(name: str) -> Any:
    """Resolve a peer through the active runtime, not its implementation module."""
    from .registry import current_manager
    return current_manager().require(name)


def runtime(home=None, **kwargs):
    """Construct a supervised runtime without exposing its implementation module."""
    from .engine import Supervisor
    return Supervisor(home, **kwargs)


@contextlib.contextmanager
def plugin_scope(home=None, client='generic'):
    """Bind an operator-selected composition for standalone command/tool calls."""
    from .registry import manager_for, CURRENT
    previous = CURRENT.get()
    manager = previous or manager_for(home, client)
    try:
        with manager.activate():
            yield manager
    finally:
        if manager is not previous:
            manager.close()


def plugin_inventory(home=None, client='generic'):
    with plugin_scope(home, client) as manager:
        return manager.describe()

def usage_metadata(raw):
    """Keep only reported numeric counters, never arbitrary provider payloads."""
    if not isinstance(raw,dict):return None
    names={'input_tokens','output_tokens','prompt_tokens','completion_tokens','cached_input_tokens','reasoning_tokens',
           'cache_read_input_tokens','cache_creation_input_tokens','cache_write_input_tokens','reasoning_output_tokens','cost_usd'}
    import math
    out={k:v for k,v in raw.items() if k in names and type(v) in (int,float) and math.isfinite(v) and v>=0}
    for key in ('input_tokens_details','prompt_tokens_details','output_tokens_details','completion_tokens_details'):
        if isinstance(raw.get(key),dict):out[key]={k:v for k,v in raw[key].items() if k in {'cached_tokens','reasoning_tokens'} and type(v) is int and v>=0}
    return out




def optional_service(name):
    from .registry import current_manager
    return current_manager().optional(name)


def configured_plugins(home=None, client="generic"):
    from .registry import manager_for
    return manager_for(home, client)


class HistoryRepository(SessionRepository, Protocol):
    """Reference supervision/history facet; an alternative backend implements it
    when hosting the reference policy/context plugins. No SQL handle is required.
    """
    def task(self, project: str) -> str: ...
    def set_task(self, project: str, task: str) -> None: ...
    def get_session(self, session_id: str) -> dict | None: ...
    def recent_sessions(self, project: str, limit: int = 20) -> list[dict]: ...
    def recent_events(self, session_id: str, limit: int = 6) -> list[dict]: ...
    def counts(self, session_id: str, action_hash: str, project: str) -> dict: ...
    def get_cache(self, key: str) -> dict | None: ...
    def put_cache(self, key: str, result: dict, ttl: float) -> None: ...
    def learning_evidence(self, project: str, lookback_days: int) -> dict: ...
    def report(self) -> dict: ...


class StateService(Protocol):
    def open(self, home: Path) -> SessionRepository: ...


class ObservationService(Protocol):
    def record_usage(self, home: Path, config: dict, identity: dict, usage: dict, *, model: str, request_id: str, provider: str = 'generic', cost_usd: float | None = None, billing_kind: str = 'unknown', start_ns: int, end_ns: int) -> None: ...
    def enabled(self, config: dict) -> bool: ...
    def proposal(self, event: dict, config: dict) -> dict: ...
    def publish_intercept(self, home: Path, session: dict, event: dict, result: dict) -> None: ...
    def publish_component(self, home: Path, config: dict, identity: dict, kind: str, attributes: dict, **timing: Any) -> None: ...
    def repository(self, home: Path, config: dict) -> Any: ...
    def dashboard(self, home: Path, project: Path, client: str, config: dict, **options: Any) -> dict: ...


class GatewayService(Protocol):
    def request(self, supervisor: Any, context: dict, payload: dict, wire: str = 'chat') -> dict: ...
    def response(self, supervisor: Any, context: dict, response: dict) -> dict: ...
