"""Cloud/self-hosted knowledge adapter and authenticated loopback reference server.

An arbitrary vendor REST API is not assumed compatible: implement the published
contract or an installed Python adapter. No redirects, token extraction, silent
fallbacks, response caching by HTTP intermediaries, or raw provider error logs.
"""
from __future__ import annotations

import hmac
import os
import pathlib
import stat
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, DocumentInput, KnowledgeError,
    InvalidRequest, Unsupported, NotFound, Conflict, Unavailable, canonical,
    loads, validate_capabilities, validate_revision, validate_search, validate_passage,
)

MAX_BODY = 16_777_216
ERRORS = {c.code: c for c in (InvalidRequest, Unsupported, NotFound, Conflict, Unavailable)}


def endpoint(url):
    if not isinstance(url, str):
        raise InvalidRequest("Endpoint must be a URL")
    u = urllib.parse.urlsplit(url)
    if not u.hostname or u.username or u.password or u.query or u.fragment:
        raise InvalidRequest("Endpoint must not contain credentials, query or fragment")
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise InvalidRequest("Use HTTPS or loopback HTTP")
    return url


def credential(key_env="", key_file="", auth="bearer"):
    if auth == "none":
        return ""
    token = os.environ.get(key_env, "").strip()
    if not token and key_file:
        path = pathlib.Path(key_file).expanduser()
        if not path.is_absolute():
            raise InvalidRequest("Credential file must be an absolute path")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, encoding="utf-8") as f:
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or (os.name != "nt" and (s.st_mode & 0o077 or s.st_uid != os.getuid())):
                raise InvalidRequest("Credential file must be private and owned by the current user")
            token = f.read(16385).strip()
    if not token or len(token) > 16384 or any(c.isspace() or ord(c) < 32 for c in token):
        raise Unavailable("Knowledge credential missing or invalid")
    return token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Unavailable("Knowledge redirect refused")


class HttpKnowledgeProvider:
    def __init__(self, url: str, *, key_env: str = "GW_KNOWLEDGE_API_KEY", key_file: str = "",
                 auth: str = "bearer", timeout_seconds: float = 5):
        self.url = endpoint(url)
        if auth not in {"bearer", "none"} or type(timeout_seconds) not in {int, float} or not 0 < timeout_seconds <= 30:
            raise InvalidRequest("Invalid knowledge transport settings")
        if not isinstance(key_env, str) or not isinstance(key_file, str):
            raise InvalidRequest("Credential references must be strings")
        self.key_env, self.key_file, self.auth = key_env, key_file, auth
        self.timeout = timeout_seconds

    def _call(self, method, request):
        body = canonical({"protocol": PROTOCOL, "method": method, "request": request}).encode()
        if len(body) > MAX_BODY:
            raise InvalidRequest("Knowledge request too large")
        headers = {"Content-Type": "application/json"}
        token = credential(self.key_env, self.key_file, self.auth)
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.url, body, headers)
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=self.timeout) as response:
                data = response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            # Only accept standardized error codes; discard external prose.
            try:
                raw = loads(exc.read(4097).decode())
                code = raw.get("error", {}).get("code") if raw.get("protocol") == PROTOCOL else None
            except Exception:
                code = None
            error = ERRORS.get(code, Unavailable)
            raise error("Knowledge endpoint rejected request") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Unavailable("Knowledge endpoint unavailable") from None
        if len(data) > MAX_BODY:
            raise InvalidRequest("Knowledge response too large")
        try:
            raw = loads(data.decode())
        except UnicodeError:
            raise InvalidRequest("Knowledge response is not UTF-8") from None
        if not isinstance(raw, dict) or set(raw) != {"protocol", "result"} or raw["protocol"] != PROTOCOL or not isinstance(raw["result"], dict):
            raise Unsupported("Invalid knowledge response envelope")
        return raw["result"]

    def capabilities(self):
        return validate_capabilities(self._call("capabilities", {}))

    def revision(self, scope):
        raw = self._call("revision", {"scope": scope.to_dict()})
        if set(raw) != {"revision"}:
            raise InvalidRequest("Invalid revision response")
        return validate_revision(raw["revision"])

    def search(self, request):
        return validate_search(self._call("search", request.to_dict()), request)

    def read(self, request):
        result = validate_passage(self._call("read", request.to_dict()), request.scope)
        if result["document_id"] != request.document_id or (request.revision and result["revision"] != request.revision):
            raise InvalidRequest("Mismatched remote document reference")
        if result["start_char"] != request.start_char or (request.end_char is not None and result["end_char"] != request.end_char):
            raise InvalidRequest("Mismatched remote range")
        return result

    def put(self, scope, document, *, expected_revision=None):
        raw = self._call("put", {"scope": scope.to_dict(), "document": document.to_dict(), "expected_revision": expected_revision})
        if set(raw) != {"document_id", "revision", "changed"} or raw["document_id"] != document.document_id or type(raw["changed"]) is not bool:
            raise InvalidRequest("Invalid write receipt")
        validate_revision(raw["revision"])
        if raw["revision"] is None:
            raise InvalidRequest("Write receipt needs a revision")
        return raw

    def delete(self, scope, document_id, *, expected_revision):
        raw = self._call("delete", {"scope": scope.to_dict(), "document_id": document_id, "expected_revision": expected_revision})
        if raw != {"document_id": document_id, "deleted": True}:
            raise InvalidRequest("Invalid delete receipt")
        return raw

    def export(self, scope):
        raise Unsupported("Bulk source export is not supported by this HTTP adapter")


def from_options(options):
    allowed = {"endpoint", "key_env", "key_file", "auth", "timeout_seconds"}
    if not isinstance(options, dict) or set(options) - allowed or not options.get("endpoint"):
        raise InvalidRequest("HTTP provider requires a complete endpoint and credential references")
    return HttpKnowledgeProvider(options["endpoint"], **{k: v for k, v in options.items() if k != "endpoint"})


def make_server(service, token: str, port: int = 0):
    if not service.scope:
        raise InvalidRequest("HTTP service must bind a scope/principal outside requests")
    if not isinstance(token, str) or len(token) < 20 or any(c.isspace() for c in token):
        raise InvalidRequest("Use a private bearer token of at least 20 characters")
    class Handler(BaseHTTPRequestHandler):
        server_version = "gw-knowledge/1"
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *args):
            pass
        def reply(self, status, payload):
            data = canonical(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            if self.headers.get("Origin") or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return self.reply(401, {"protocol": PROTOCOL, "error": {"code": "unavailable"}})
            if self.path != "/v1/knowledge":
                return self.reply(404, {"protocol": PROTOCOL, "error": {"code": "not_found"}})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 <= size <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                    raise InvalidRequest("Invalid body length")
                if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    raise InvalidRequest("Expected JSON")
                result = service.handle(loads(self.rfile.read(size).decode()))
                self.reply(200, result)
            except KnowledgeError as exc:
                status = 404 if isinstance(exc, NotFound) else 409 if isinstance(exc, Conflict) else 503 if isinstance(exc, Unavailable) else 400
                self.reply(status, {"protocol": PROTOCOL, "error": {"code": exc.code}})
            except Exception:
                self.reply(503, {"protocol": PROTOCOL, "error": {"code": "unavailable"}})
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
