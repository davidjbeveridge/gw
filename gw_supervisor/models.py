"""Capability-first selection. A model ID is not an endpoint, credential or executor.

This module produces plans, never launches a process or transfers subscription
credentials. Operation/modality/capability names are open, user-defined strings.
"""
from __future__ import annotations

import copy
import datetime as dt
import math
from .util import canonical

DEFAULT_POLICY = {
    "strategy": "priority", "prefer": [], "deny": [],
    "billing_preference": [], "on_unavailable": "approve",
    "max_candidates": 32,
    "question": "Select the best configured model for this request from the admissible candidates. Consider the task, capabilities, operator preferences and declared billing. Price units are not interchangeable. Do not invent availability, quality, or subscription quota. Choose abstain when no candidate is suitable.",
}
KINDS = {"proxy", "harness", "adapter"}
BILLING = {"metered", "subscription", "local", "unknown"}
STATUSES = {"available", "unknown", "exhausted", "unavailable"}


def strings(value, field, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{field} must be a list of nonempty strings")
    return value


def number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return value


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("available_until requires a timezone")
    return parsed.timestamp()


def validate_registry(config):
    if not isinstance(config, dict) or set(config) - {"models", "policy"}:
        raise ValueError("inference accepts models and policy")
    models, policy = config.get("models", {}), config.get("policy", {})
    if not isinstance(models, dict) or not isinstance(policy, dict):
        raise ValueError("inference models/policy must be objects")
    if set(policy) - set(DEFAULT_POLICY) - {"allow"}:
        raise ValueError("Unknown inference policy key")
    if policy.get("strategy", "priority") not in {"priority", "classifier"}:
        raise ValueError("Inference strategy must be priority or classifier")
    if policy.get("on_unavailable", "approve") not in {"approve", "deny"}:
        raise ValueError("Unavailable inference must require approval or deny")
    for field in ("prefer", "deny", "allow", "billing_preference"):
        if field in policy:
            strings(policy[field], field)
    if not set(policy.get("billing_preference", [])) <= BILLING:
        raise ValueError("Unknown billing preference")
    limit = policy.get("max_candidates", 32)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 128:
        raise ValueError("max_candidates must be 1..128")
    if not isinstance(policy.get("question", ""), str):
        raise ValueError("Selection question must be text")
    fields = {"provider", "model", "description", "operations", "input_modalities", "output_modalities", "capabilities", "execution", "billing", "enabled", "availability", "priority", "context_window", "quota_remaining", "available_until", "metadata"}
    for mid, model in models.items():
        if not isinstance(mid, str) or not mid.strip() or not isinstance(model, dict) or set(model) - fields:
            raise ValueError(f"Invalid model entry: {mid}")
        for field in ("provider", "model"):
            if not isinstance(model.get(field), str) or not model[field].strip():
                raise ValueError(f"Model {mid} requires {field}")
        for field in ("operations", "input_modalities", "output_modalities"):
            strings(model.get(field), field, nonempty=True)
        strings(model.get("capabilities", []), "capabilities")
        execution = model.get("execution", {})
        if not isinstance(execution, dict) or set(execution) != {"kind", "target"} or execution["kind"] not in KINDS or not isinstance(execution["target"], str) or not execution["target"].strip():
            raise ValueError(f"Model {mid} requires an execution kind and opaque target")
        billing = model.get("billing", {"kind": "unknown"})
        if not isinstance(billing, dict) or billing.get("kind") not in BILLING or set(billing) - {"kind", "prices", "notes"}:
            raise ValueError(f"Invalid billing for {mid}")
        prices = billing.get("prices", {})
        if not isinstance(prices, dict):
            raise ValueError("prices must map explicit units to numbers")
        for unit, price in prices.items():
            if not isinstance(unit, str) or not unit:
                raise ValueError("Price units must be nonempty strings")
            number(price, unit)
        if not isinstance(model.get("enabled", True), bool) or model.get("availability", "unknown") not in STATUSES:
            raise ValueError(f"Invalid availability for {mid}")
        for field in ("priority", "context_window", "quota_remaining"):
            if field in model:
                number(model[field], field)
        if "available_until" in model:
            if not isinstance(model["available_until"], str):
                raise ValueError("available_until must be an ISO timestamp")
            timestamp(model["available_until"])


def requirements(source):
    if not isinstance(source, dict):
        raise ValueError("Inference requirements must be an object")
    allowed = {"operation", "input_modalities", "output_modalities", "capabilities", "execution_kinds", "context_tokens", "exclude", "execution_target"}
    if set(source) - allowed:
        raise ValueError("Unknown inference requirement")
    req = copy.deepcopy(source)
    if not isinstance(req.get("operation"), str) or not req["operation"].strip():
        raise ValueError("An explicit inference operation is required")
    for field in ("input_modalities", "output_modalities"):
        strings(req.get(field), field, nonempty=True)
    for field in ("capabilities", "execution_kinds", "exclude"):
        strings(req.get(field, []), field)
    if not set(req.get("execution_kinds", [])) <= KINDS:
        raise ValueError("Unknown execution kind")
    if "execution_target" in req and (not isinstance(req["execution_target"], str) or not req["execution_target"]):
        raise ValueError("execution_target must be a nonempty string")
    number(req.get("context_tokens", 0), "context_tokens")
    return req


def rejected_reason(mid, model, req, policy, now):
    if not model.get("enabled", True):
        return "disabled"
    if mid in policy.get("deny", []) or mid in req.get("exclude", []):
        return "excluded"
    if "allow" in policy and mid not in policy["allow"]:
        return "not_allowlisted"
    if model.get("availability", "unknown") != "available":
        return "availability_" + model.get("availability", "unknown")
    if model.get("quota_remaining") == 0:
        return "quota_exhausted"
    if "available_until" in model and timestamp(model["available_until"]) <= now:
        return "availability_expired"
    if req["operation"] not in model["operations"]:
        return "operation_mismatch"
    for field in ("input_modalities", "output_modalities", "capabilities"):
        if not set(req.get(field, [])) <= set(model.get(field, [])):
            return field + "_mismatch"
    if req.get("execution_kinds") and model["execution"]["kind"] not in req["execution_kinds"]:
        return "execution_mismatch"
    if req.get("execution_target") and model["execution"]["target"] != req["execution_target"]:
        return "opaque_state_bound_to_other_target"
    if req.get("context_tokens", 0) > model.get("context_window", 0):
        return "context_window_insufficient_or_unknown"
    return None


def select(config, request, classifier=None, state=None, now=None):
    """Only admissible candidates reach a classifier; failure never expands the pool."""
    validate_registry(config)
    req = requirements(request)
    policy = {**DEFAULT_POLICY, **config.get("policy", {})}
    models = config.get("models", {})
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    rejected, eligible = {}, []
    def rank(mid):
        m = models[mid]
        preferred, bills = policy["prefer"], policy["billing_preference"]
        billing = m.get("billing", {}).get("kind", "unknown")
        return (preferred.index(mid) if mid in preferred else len(preferred), bills.index(billing) if billing in bills else len(bills), m.get("priority", 100), mid)
    for mid, model in models.items():
        reason = rejected_reason(mid, model, req, policy, now)
        if reason:
            rejected[mid] = reason
        else:
            eligible.append(mid)
    eligible.sort(key=rank)
    result = {"status": "unavailable", "requirements": req, "eligible": eligible, "rejected": rejected, "strategy": policy["strategy"], "selection_only": True}
    if not eligible:
        return result
    selected = eligible[0]
    if policy["strategy"] == "classifier" and len(eligible) > 1:
        if classifier is None:
            return {**result, "status": "classifier_unavailable"}
        considered = eligible[:policy["max_candidates"]]
        result["considered"] = considered
        # Use safe opaque labels rather than provider IDs as classifier output keys.
        labels = {f"candidate_{i}": mid for i, mid in enumerate(considered)}
        options = {label: canonical({"id": mid, "description": models[mid].get("description", ""), "capabilities": models[mid].get("capabilities", []), "billing": models[mid].get("billing", {"kind": "unknown"}), "preference_order": i}) for i, (label, mid) in enumerate(labels.items())}
        options["abstain"] = "None of these candidates is suitable or evidence is insufficient"
        try:
            answers = classifier.decide({"request": req, "context": state or {}}, {"model_selection": {"question": policy["question"], "choices": options}})
            choice = answers.get("model_selection") if isinstance(answers, dict) else None
            if choice == "abstain":
                return {**result, "status": "abstained"}
            if choice not in labels:
                raise ValueError("Invalid selection")
            selected = labels[choice]
        except Exception as exc:
            return {**result, "status": "classifier_unavailable", "error": type(exc).__name__}
    model = models[selected]
    result.update(status="selected", plan={"model_id": selected, "provider": model["provider"], "model": model["model"], "operation": req["operation"], "execution": copy.deepcopy(model["execution"]), "billing": copy.deepcopy(model.get("billing", {"kind": "unknown"}))})
    return result


def decision_config(config):
    """Optionally name a registry model for the supervisor's own classifier.

    Endpoints/credentials stay in global decision configuration. This does not
    auto-run arbitrary adapters, and never routes its own decision recursively.
    """
    out = copy.deepcopy(config["decision"])
    ref = out.get("model_ref")
    if not ref or out.get("provider") == "off":
        return out
    model = config.get("inference", {}).get("models", {}).get(ref)
    if model is None or model["execution"] != {"kind": "adapter", "target": out["provider"]}:
        raise ValueError("decision.model_ref must reference its configured jev/http adapter")
    req = {"operation": "decision", "input_modalities": ["text"], "output_modalities": ["decisions"]}
    if rejected_reason(ref, model, req, {}, dt.datetime.now(dt.timezone.utc).timestamp()):
        raise ValueError("Configured decision model is unavailable or incompatible")
    out["model"] = model["model"]
    return out
