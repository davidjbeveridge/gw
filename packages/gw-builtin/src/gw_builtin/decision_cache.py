"""Exact, per-goal decisions keyed by the same evidence sent to the provider.

Inputs are a declared dependency contract, not a fuzzy similarity threshold.
Unspecified contracts retain the entire state. Task and compiled evidence are
always included. Cache entries contain labels, never executable permissions.
"""
from __future__ import annotations

import copy
import re
from gw_supervisor.api import canonical, digest

_PATH = re.compile(r"^(event|metrics)(\.[A-Za-z_][A-Za-z0-9_-]*)*$")
_MISSING = object()
PROTOCOL = "gw.decision-cache/2"


def validate_inputs(goal: dict) -> None:
    paths = goal.get("inputs")
    if paths is None:
        return
    if (not isinstance(paths, list) or not 1 <= len(paths) <= 32
            or any(not isinstance(p, str) or len(p) > 128 or not _PATH.fullmatch(p) for p in paths)
            or len(set(paths)) != len(paths)):
        raise ValueError("Decision inputs must be distinct event/metrics paths (1..32)")
    for path in paths:
        if any(other != path and path.startswith(other + ".") for other in paths):
            raise ValueError("Decision inputs must not overlap")


def projected_state(state: dict, goal: dict) -> dict:
    """Project only event/metrics. Other host evidence cannot be silently removed."""
    validate_inputs(goal)
    paths = goal.get("inputs")
    if paths is None:
        return copy.deepcopy(state)
    # In particular retain task, compiled_context and future host evidence.
    out = {key: copy.deepcopy(value) for key, value in state.items() if key not in {"event", "metrics"}}
    for path in sorted(paths):
        parts = path.split(".")
        value = state
        for part in parts:
            value = value.get(part, _MISSING) if isinstance(value, dict) else _MISSING
            if value is _MISSING:
                break
        if value is _MISSING:
            continue  # Absence is distinct from an explicit null.
        target = out
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = copy.deepcopy(value)
    return out


def evaluate_goals(store, *, scope: dict, state: dict, goals: dict, ttl: float,
                   provider_factory, record_call=None) -> tuple[dict, dict, dict]:
    """Read individual labels, batch only compatible misses, isolate failures.

    A batch shares one exact projected state. Invalid, partial, or extra labels
    invalidate that whole returned batch; valid cached or other-batch answers
    survive. The caller reapplies current deterministic and authority rules.
    """
    labels, errors, diagnostics, batches = {}, {}, {}, {}
    provider = None
    for gid, goal in goals.items():
        projection = projected_state(state, goal)
        key = digest([PROTOCOL, scope, gid, goal, projection])
        cached = store.get_cache(key) if ttl > 0 else None
        # Persist one validated label, independent of sibling questions.
        hit = (isinstance(cached, dict) and set(cached) == {"label"}
               and isinstance(cached["label"], str) and cached["label"] in goal["choices"])
        diagnostics[gid] = {"status": "hit" if hit else "miss" if ttl > 0 else "disabled",
                            "key": key, "inputs": goal.get("inputs", "full_state")}
        if hit:
            labels[gid] = cached["label"]
        else:
            batch = batches.setdefault(canonical(projection), {"state": projection, "goals": {}, "keys": {}})
            batch["goals"][gid], batch["keys"][gid] = goal, key
    for batch in batches.values():
        pending = batch["goals"]
        try:
            if provider is None:
                provider = provider_factory()
            import time
            started = time.perf_counter()
            try:
                answer = provider.decide(copy.deepcopy(batch["state"]), copy.deepcopy(pending))
            finally:
                if record_call:
                    record_call(provider, sorted(pending), (time.perf_counter() - started) * 1000)
            if (not isinstance(answer, dict) or set(answer) != set(pending)
                    or any(not isinstance(answer[k], str) or answer[k] not in g["choices"] for k, g in pending.items())):
                raise ValueError("Invalid classification")
            for gid, label in answer.items():
                labels[gid] = label
                if ttl > 0:
                    store.put_cache(batch["keys"][gid], {"label": label}, ttl)
        except Exception as exc:
            # No error/refusal is converted into a cached semantic answer.
            for gid in pending:
                errors[gid] = type(exc).__name__
                diagnostics[gid]["status"] = "error"
    return labels, errors, diagnostics
