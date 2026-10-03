"""A bounded fast/slow decision cascade, not a recursive repair agent.

The outer engine still applies deterministic rules, authority and native permissions.
An uncertain label can escalate; a provider refusal is never a fallback trigger.
"""
from __future__ import annotations

import copy
import time
from .providers import Classifier
from .decision_transport import validate_decision
from gw_supervisor.api import canonical


def validate_strategy(config: dict) -> None:
    strategy = config.get("strategy", "single")
    if strategy not in {"single", "cascade", "managed"}:
        raise ValueError("Decision strategy must be single, cascade, or managed")
    fallback = config.get("fallback")
    if strategy != "cascade":
        if fallback:
            raise ValueError("Only cascade strategy accepts a fallback")
        return
    if config.get("provider") == "off":
        raise ValueError("A cascade needs an enabled primary provider")
    if not isinstance(fallback, dict) or set(fallback) - {"backend", "on_labels", "on_error"}:
        raise ValueError("Fallback requires backend, optional on_labels and on_error")
    backend = fallback.get("backend")
    if not isinstance(backend, dict) or backend.get("provider") == "off":
        raise ValueError("Fallback backend must be explicitly enabled")
    if any(k in backend for k in ("fallback", "strategy", "model_ref")):
        raise ValueError("Nested fallbacks and unresolved model references are not supported")
    validate_decision(backend)
    if type(fallback.get("on_error", False)) is not bool:
        raise ValueError("fallback.on_error must be boolean")
    labels = fallback.get("on_labels", {"*": ["uncertain", "unknown"]})
    if not isinstance(labels, dict) or len(labels) > 128:
        raise ValueError("on_labels must map goal IDs to exact labels")
    for key, values in labels.items():
        if not isinstance(key, str) or not key or not isinstance(values, list) or len(values) > 128 or any(not isinstance(v, str) or not v for v in values):
            raise ValueError("Invalid fallback labels")
    # Both transports are independently bounded to <=5 s. This validation keeps
    # the sum explicit instead of nesting several model-rescue attempts in a hook.
    if config.get("timeout_seconds", 2) + backend.get("timeout_seconds", 2) > 10:
        raise ValueError("Combined decision transport timeouts exceed ten seconds")


def _labels(value: dict, goals: dict) -> dict:
    if not isinstance(value, dict) or set(value) != set(goals):
        raise ValueError("Decision provider must answer exactly the supplied goals")
    if any(not isinstance(value[k], str) or value[k] not in g["choices"] for k, g in goals.items()):
        raise ValueError("Decision provider returned an invalid label")
    return value


class DecisionCascade:
    """At most one primary and one fallback call per decide invocation.

    Successful primary labels survive when only other goals escalate. A failed
    fallback returns an error to the existing per-goal error policy, not a guessed
    label. Managed mode leaves switching to one compatible external endpoint.
    """
    def __init__(self, config: dict, factory=Classifier):
        validate_decision(config)
        self.config = copy.deepcopy(config)
        self.factory = factory
        self.last_calls: list[dict] = []
        self.last_usage = None

    def _call(self, stage: str, backend: dict, state: dict, goals: dict, trigger: str) -> dict:
        started = time.perf_counter()
        provider = None
        call = {"stage": stage, "strategy": self.config.get("strategy", "single"),
                "model": backend.get("model"), "protocol": backend.get("provider"),
                "goal_ids": sorted(goals), "trigger": trigger, "status": "error"}
        try:
            provider = self.factory(backend)
            answer = _labels(provider.decide(state, goals), goals)
            call["status"] = "scored"
            return answer
        except Exception as exc:
            # Exception types only. Third-party strings can contain source data.
            call["error"] = type(exc).__name__
            raise
        finally:
            from gw_supervisor.api import usage_metadata
            call["usage"] = usage_metadata(getattr(provider, "last_usage", None))
            call["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
            self.last_calls.append(call)

    def decide(self, state: dict, goals: dict) -> dict:
        self.last_calls = []
        self.last_usage = None
        strategy = self.config.get("strategy", "single")
        fallback = self.config.get("fallback", {})
        primary_config = {k: v for k, v in self.config.items() if k not in {"strategy", "fallback"}}
        try:
            answer = self._call("primary", primary_config, state, goals, "initial")
        except Exception as exc:
            # Explicit provider refusal never becomes a way to shop for a bypass.
            refused = isinstance(exc, ValueError) and str(exc) == "decision_provider_refused"
            if strategy != "cascade" or not fallback.get("on_error", False) or refused:
                raise
            return self._call("fallback", fallback["backend"], state, goals, "primary_error")
        if strategy != "cascade":
            return answer
        triggers = fallback.get("on_labels", {"*": ["uncertain", "unknown"]})
        pending = {key: goals[key] for key, label in answer.items()
                   if label in triggers.get(key, triggers.get("*", []))}
        if not pending:
            return answer
        # Independent reread of the same evidence; do not bias the slow stage with
        # the primary answer or send already resolved questions unnecessarily.
        refined = self._call("fallback", fallback["backend"], state, pending, "configured_label")
        return {**answer, **refined}


def make_decider(config: dict):
    return DecisionCascade(config)


def append_calls(audit: dict, provider, purpose: str, elapsed_ms: float, model: str | None) -> None:
    """Preserve both calls and their usage; don't collapse a cascade into one call."""
    from gw_supervisor.api import usage_metadata
    calls = getattr(provider, "last_calls", None)
    if isinstance(calls, list) and calls:
        audit["classifier_calls"].extend({**entry, "purpose": purpose} for entry in calls)
    else:
        audit["classifier_calls"].append({"purpose": purpose, "stage": "primary", "model": model,
                                         "elapsed_ms": elapsed_ms,
                                         "usage": usage_metadata(getattr(provider, "last_usage", None))})
