"""One bounded dispatcher shared by HTTP, MCP, CLI and the GW bridge."""
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, DocumentInput, InvalidRequest,
    Unsupported, MutableKnowledgeProvider, object_fields, validate_capabilities,
    validate_revision, validate_search, validate_passage, text,
)


class KnowledgeService:
    def __init__(self, provider, cache=None, *, scope: Scope | None = None, writable=False):
        self.provider, self.cache, self.scope, self.writable = provider, cache, scope, writable

    def _scope(self, raw):
        scope = Scope.from_dict(raw)
        if self.scope is not None and scope != self.scope:
            raise InvalidRequest("This connection is bound to a different scope")
        return scope

    def dispatch(self, method: str, body: dict) -> dict:
        if method == "capabilities":
            object_fields(body, set())
            caps = dict(validate_capabilities(self.provider.capabilities()))
            caps["writes"] = caps["writes"] and self.writable
            caps["optional_operations"] = [op for op in caps["optional_operations"] if self.writable and op in {"put", "delete"}]
            return caps
        if not isinstance(body, dict) or "scope" not in body:
            raise InvalidRequest("Explicit scope required")
        scope = self._scope(body["scope"])
        if method == "revision":
            object_fields(body, {"scope"}, {"scope"})
            return {"revision": validate_revision(self.provider.revision(scope))}
        if method == "search":
            request = SearchRequest.from_dict(body)
            return validate_search(self.provider.search(request), request)
        if method == "read":
            request = ReadRequest.from_dict(body)
            result = validate_passage(self.provider.read(request), scope)
            if result["document_id"] != request.document_id or (request.revision is not None and request.revision != result["revision"]):
                raise InvalidRequest("Provider read does not match the requested reference")
            if result["start_char"] != request.start_char or (request.end_char is not None and result["end_char"] != request.end_char):
                raise InvalidRequest("Provider read does not match the requested range")
            return result
        if method == "context":
            request = SearchRequest.from_dict({k: v for k, v in body.items() if k != "max_chars"})
            if self.cache is None:
                raise Unsupported("Context assembly is not configured")
            return self.cache.assemble(self.provider, request, max_chars=body.get("max_chars", 12000))
        if method not in {"put", "delete"}:
            raise Unsupported("Unknown knowledge method")
        if not self.writable or not isinstance(self.provider, MutableKnowledgeProvider):
            raise Unsupported("This knowledge connection is read-only")
        if method == "put":
            object_fields(body, {"scope", "document", "expected_revision"}, {"scope", "document"})
            result = self.provider.put(scope, DocumentInput.from_dict(body["document"]), expected_revision=body.get("expected_revision"))
        else:
            object_fields(body, {"scope", "document_id", "expected_revision"}, {"scope", "document_id", "expected_revision"})
            result = self.provider.delete(scope, body["document_id"], expected_revision=body["expected_revision"])
        if self.cache:
            # Cache eviction is separate from durable-source deletion.
            self.cache.clear(scope)
        return result

    def handle(self, envelope: dict) -> dict:
        object_fields(envelope, {"protocol", "method", "request"}, {"protocol", "method", "request"})
        if envelope["protocol"] != PROTOCOL:
            raise Unsupported("Unsupported knowledge protocol version")
        return {"protocol": PROTOCOL, "result": self.dispatch(envelope["method"], envelope["request"])}
