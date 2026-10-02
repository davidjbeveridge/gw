"""Replaceable typed decision and authority providers; no recursive agent loop."""
from __future__ import annotations

import os
from typing import Any, Protocol
from .util import canonical, finite, post_json, redact
from .decision_transport import credential, parse_answers, request_body, validate_decision


class DecisionProvider(Protocol):
    def decide(self, state: dict, goals: dict) -> dict[str, str]: ...


class AuthorityProvider(Protocol):
    def authorize(self, request: dict) -> dict: ...


class InferenceExecutor(Protocol):
    """Extension seam for non-proxy plans. Selection is not execution authority.

    Implementations own native authentication, protocol validation, lifecycle and
    artifact results. This release never launches executors or extracts OAuth.
    """
    def execute(self, plan: dict, request: dict) -> dict: ...


class CredentialInjector(Protocol):
    """Future executor-side seam. No implementation resolves secrets in this release.

    request: credential_ref, target.origin, target.field, task/session,
    authorization receipt; result: an opaque injection receipt, NEVER the secret.
    """
    def inject(self, request: dict) -> dict: ...


class Classifier:
    def __init__(self, config: dict):
        self.config = config
        self.last_usage = None

    def decide(self, state: dict, goals: dict) -> dict[str, str]:
        self.last_usage = None
        c = self.config
        if c["provider"] == "off":
            raise RuntimeError("decision_provider_disabled")
        sanitized = redact(state)
        if len(canonical(sanitized)) > c.get("max_state_chars", 16000):
            raise RuntimeError("decision_context_too_large: abstained instead of truncating")
        validate_decision(c)
        body = request_body(c, sanitized, goals)
        if len(canonical(body)) > c.get("max_request_chars", 64000):
            raise RuntimeError("decision_request_too_large: abstained instead of truncating")
        raw = post_json(c["endpoint"], body, credential(c), c["timeout_seconds"])
        self.last_usage = raw.get("usage") if isinstance(raw.get("usage"),dict) else None
        return parse_answers(c, raw, goals)


class HttpAuthority:
    def __init__(self, config: dict):
        self.config = config

    def authorize(self, request: dict) -> dict:
        c = self.config
        result = post_json(c["endpoint"], {"version": 1, **redact(request)}, os.environ.get(c.get("key_env", "GW_AUTHORITY_TOKEN"), ""), min(c.get("timeout_seconds", 2), 5))
        if result.get("decision") not in {"allow", "deny", "approve"}:
            raise ValueError("Authority returned an invalid decision")
        # Never claim to enforce obligations this executor doesn't understand.
        if result.get("constraints") or result.get("obligations"):
            return {"decision": "deny", "reason": "Authority returned unsupported constraints; an executor integration is required"}
        return {"decision": result["decision"], "reason": str(redact(result.get("reason", "External authority")))[:1000], "receipt": redact(result.get("receipt"))}
