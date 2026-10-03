"""Small context-contract primitives. No knowledge, database or harness dependency."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class ContextError(ValueError):
    code = "context_error"


class InvalidRequest(ContextError):
    code = "invalid_request"


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidRequest("Expected finite JSON values") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def loads(text: str) -> Any:
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise InvalidRequest("Duplicate JSON key")
            out[k] = v
        return out
    def invalid(_):
        raise InvalidRequest("Non-finite JSON value")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError, RecursionError) as exc:
        raise InvalidRequest("Invalid JSON") from exc


def text(value: Any, name: str, maximum: int = 4096, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > maximum or "\0" in value:
        raise InvalidRequest(f"Invalid {name}")
    # Reject unpaired surrogates rather than breaking SQLite, hashing or stdout later.
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise InvalidRequest(f"Invalid UTF-8 {name}") from exc
    return value


def integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise InvalidRequest(f"Invalid {name}")
    return value
