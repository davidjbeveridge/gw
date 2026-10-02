"""Small, dependency-free security and serialization utilities."""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
import urllib.parse
import urllib.request
from typing import Any

SECRET_KEYS = re.compile(r"^(password|passwd|secret|token|access_token|refresh_token|api[_-]?key|authorization|cookie|set-cookie|private_key)$", re.I)
SECRET_TEXT = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----|\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|(?i:Bearer\s+)[A-Za-z0-9._~+/-]{8,}|(?i:(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)[^\s\"']{4,}", re.S)


def redact(value: Any) -> Any:
    """Best effort, not DLP. Secret references are the preferred interface."""
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SECRET_KEYS.match(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return SECRET_TEXT.sub("[REDACTED]", value)
    return value


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path: pathlib.Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return strict_json(path.read_text(encoding="utf-8"))


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError(f"Duplicate JSON key: {k}")
            result[k] = v
        return result
    def invalid(s):
        raise ValueError(f"Non-finite JSON value: {s}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def atomic_write(path: pathlib.Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".gw-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: pathlib.Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def finite(value: Any, low: float = 0, high: float = 1) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid numeric result")
    return float(value)


def safe_endpoint(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if u.username or u.password or u.fragment or not u.hostname:
        raise ValueError("Endpoint must not embed credentials or fragments")
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("Endpoint must use HTTPS, or HTTP on loopback")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused: do not forward credentials to a different endpoint")


def post_json(url: str, body: dict, token: str = "", timeout: float = 3, max_bytes: int = 4_194_304, *, key_header: str = "Authorization") -> dict:
    if key_header not in {"Authorization", "X-API-Key"}:
        raise ValueError("Unsupported credential header")
    headers = {"Content-Type": "application/json"}
    if token:
        headers[key_header] = f"Bearer {token}" if key_header == "Authorization" else token
    req = urllib.request.Request(safe_endpoint(url), canonical(body).encode(), headers)
    with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Response exceeded size limit")
    result = strict_json(raw.decode())
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result
