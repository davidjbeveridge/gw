"""Optional authenticated loopback API. Not a public reverse proxy or tool executor."""
from __future__ import annotations

import hmac
import json
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from gw_supervisor import __version__
from .host import home_path, initialize
from gw_supervisor.api import runtime as Supervisor
from .proxy import process_request, process_response
from gw_supervisor.api import strict_json

MAX_BODY = 4_194_304


def make_server(home: pathlib.Path, port: int = 7777) -> ThreadingHTTPServer:
    initialize(home)
    token = (home / "api-token").read_text().strip()

    class Handler(BaseHTTPRequestHandler):
        server_version = "gw/" + __version__
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass  # No payloads, keys, query strings, or paths in access logs.

        def respond(self, status: int, value: dict):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            # No CORS. Browser-origin requests are not a supported API client.
            return not self.headers.get("Origin") and hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)

        def do_GET(self):
            if self.path == "/healthz":
                return self.respond(200, {"service": "gw", "version": __version__})
            if not self.authorized():
                return self.respond(401, {"error": "unauthorized"})
            if self.path == "/v1/status":
                with Supervisor(home) as supervisor:
                    return self.respond(200, supervisor.store.report())
            self.respond(404, {"error": "not_found"})

        def do_POST(self):
            if not self.authorized():
                return self.respond(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if length < 0 or length > MAX_BODY or self.headers.get("Transfer-Encoding"):
                    return self.respond(413, {"error": "invalid_body_size"})
                if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    return self.respond(415, {"error": "expected_json"})
                body = strict_json(self.rfile.read(length).decode())
                if self.path == "/v1/knowledge":
                    from gw_supervisor.api import service
                    call = service("knowledge").call
                    result = call(home, body["context"], body["method"], body.get("request", {}))
                    return self.respond(200, result)
                with Supervisor(home) as supervisor:
                    if self.path == "/v1/events":
                        result = supervisor.evaluate(body)
                    elif self.path == "/v1/inference/select":
                        result = supervisor.evaluate({**body["context"], "type": "inference.select", "requirements": body["requirements"]})
                    elif self.path == "/v1/model/request":
                        result = process_request(supervisor, body["context"], body["payload"], body.get("format", "chat"))
                    elif self.path == "/v1/model/response":
                        result = process_response(supervisor, body["context"], body["payload"])
                    else:
                        return self.respond(404, {"error": "not_found"})
                self.respond(200, result)
            except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
                self.respond(400, {"decision": "deny", "error": "invalid_request_or_policy"})
            except Exception:
                self.respond(503, {"decision": "deny", "error": "supervisor_unavailable"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(home: pathlib.Path, port: int = 7777):
    server = make_server(home, port)
    print(f"gw listening on http://127.0.0.1:{server.server_port}; bearer token in {home / 'api-token'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
