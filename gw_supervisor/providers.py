"""Replaceable typed decision and authority providers; no recursive agent loop."""
from __future__ import annotations

import os
from typing import Any, Protocol
from .util import canonical, finite, post_json, redact


class DecisionProvider(Protocol):
    def decide(self, state: dict, goals: dict) -> dict[str, str]: ...


class AuthorityProvider(Protocol):
    def authorize(self, request: dict) -> dict: ...


class CredentialInjector(Protocol):
    """Future executor-side seam. No implementation resolves secrets in this release.

    request: credential_ref, target.origin, target.field, task/session,
    authorization receipt; result: an opaque injection receipt, NEVER the secret.
    """
    def inject(self, request: dict) -> dict: ...


class Classifier:
    def __init__(self, config: dict):
        self.config = config

    def decide(self, state: dict, goals: dict) -> dict[str, str]:
        c = self.config
        if c["provider"] == "off":
            raise RuntimeError("decision_provider_disabled")
        sanitized = redact(state)
        if len(canonical(sanitized)) > c.get("max_state_chars", 16000):
            raise RuntimeError("decision_context_too_large: abstained instead of truncating")
        token = os.environ.get(c["key_env"], "")
        if c["provider"] == "jev":
            if not token:
                raise RuntimeError("decision_key_missing")
            questions = {key: {"type": "choice", "instructions": g["question"], "criteria": g["choices"]} for key, g in goals.items()}
            raw = post_json(c["endpoint"], {"model": c["model"], "state": canonical(sanitized), "questions": questions}, token, c["timeout_seconds"])
            answers = raw.get("answers", {})
            result = {key: answers.get(key, {}).get("choice") for key in goals}
        else:
            # Vendor-neutral classifier contract, useful for local SLMs or a service.
            raw = post_json(c["endpoint"], {"version": 1, "state": sanitized, "goals": goals}, token, c["timeout_seconds"])
            result = raw.get("decisions", {})
        if not isinstance(result, dict):
            raise ValueError("Malformed classifier response")
        for key, goal in goals.items():
            if result.get(key) not in goal["choices"]:
                raise ValueError(f"Missing/invalid choice for {key}")
        return {key: result[key] for key in goals}


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
