"""gw.knowledge/1: a provider-neutral JSON contract, with MCP as an optional transport.

This is an open project contract, not a claim of an industry-wide knowledge API.
Backends must filter access BEFORE returning search hits or document content.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Protocol, runtime_checkable

PROTOCOL = "gw.knowledge/1"
MAX_DOCUMENT_CHARS = 2_000_000
MODES = {"keyword", "structured", "semantic", "hybrid"}


class KnowledgeError(Exception):
    code = "knowledge_error"


class InvalidRequest(KnowledgeError, ValueError):
    code = "invalid_request"


class NotFound(KnowledgeError):
    """Missing and inaccessible documents deliberately share this error."""
    code = "not_found"


class Conflict(KnowledgeError):
    code = "revision_conflict"


class Unsupported(KnowledgeError):
    code = "unsupported"


class Unavailable(KnowledgeError):
    code = "unavailable"


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


def scalar(value: Any) -> bool:
    return value is None or type(value) in {str, bool, int} or (type(value) is float and math.isfinite(value))


def metadata(value: Any) -> dict:
    if not isinstance(value, dict) or len(value) > 64:
        raise InvalidRequest("Metadata must be a bounded object of scalar values")
    for key, val in value.items():
        text(key, "metadata key", 128)
        if not scalar(val):
            raise InvalidRequest("Metadata values must be finite JSON scalars")
    if len(canonical(value)) > 16000:
        raise InvalidRequest("Metadata too large")
    return value


def object_fields(raw: Any, allowed: set[str], required: set[str] | None = None) -> dict:
    if not isinstance(raw, dict) or set(raw) - allowed or not (required or set()) <= set(raw):
        raise InvalidRequest("Missing or unknown contract fields")
    return raw


@dataclass(frozen=True)
class Scope:
    tenant: str
    collection: str
    principal: str

    def __post_init__(self):
        for k, v in asdict(self).items():
            text(v, k, 256)
            if v == "*":
                raise InvalidRequest("Scope fields cannot be wildcards")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> Scope:
        return cls(**object_fields(raw, {"tenant", "collection", "principal"}, {"tenant", "collection", "principal"}))


@dataclass(frozen=True)
class SearchRequest:
    scope: Scope
    query: str = ""
    mode: str = "keyword"
    filters: dict = field(default_factory=dict)
    limit: int = 8
    cursor: str | None = None

    def __post_init__(self):
        if not isinstance(self.scope, Scope):
            raise InvalidRequest("Scope is required")
        text(self.query, "query", 4096, empty=True)
        if self.mode not in MODES or (self.mode == "structured" and self.query):
            raise InvalidRequest("Invalid search mode or structured query")
        if self.mode != "structured" and not self.query.strip():
            raise InvalidRequest("Search query required")
        metadata(self.filters)
        integer(self.limit, "limit", 1, 50)
        if self.cursor is not None:
            text(self.cursor, "cursor", 8192)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> SearchRequest:
        data = dict(object_fields(raw, {"scope", "query", "mode", "filters", "limit", "cursor"}, {"scope"}))
        data["scope"] = Scope.from_dict(data["scope"])
        return cls(**data)


@dataclass(frozen=True)
class ReadRequest:
    scope: Scope
    document_id: str
    revision: str | None = None
    start_char: int = 0
    end_char: int | None = None

    def __post_init__(self):
        if not isinstance(self.scope, Scope):
            raise InvalidRequest("Scope is required")
        text(self.document_id, "document_id", 256)
        if self.revision is not None:
            text(self.revision, "revision", 256)
        integer(self.start_char, "start_char", 0, MAX_DOCUMENT_CHARS)
        if self.end_char is not None:
            integer(self.end_char, "end_char", self.start_char, MAX_DOCUMENT_CHARS)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> ReadRequest:
        data = dict(object_fields(raw, {"scope", "document_id", "revision", "start_char", "end_char"}, {"scope", "document_id"}))
        data["scope"] = Scope.from_dict(data["scope"])
        return cls(**data)


@dataclass(frozen=True)
class DocumentInput:
    document_id: str
    title: str
    text: str
    source: str
    metadata: dict = field(default_factory=dict)
    readers: list[str] = field(default_factory=list)
    expires_at: float | None = None

    def __post_init__(self):
        for name, maximum in (("document_id", 256), ("title", 1024), ("text", MAX_DOCUMENT_CHARS), ("source", 4096)):
            text(getattr(self, name), name, maximum, empty=name == "text")
        metadata(self.metadata)
        if not isinstance(self.readers, list) or len(self.readers) > 64:
            raise InvalidRequest("Invalid readers")
        for reader in self.readers:
            text(reader, "reader", 256)
        if self.expires_at is not None and (type(self.expires_at) not in {int, float} or not math.isfinite(self.expires_at) or self.expires_at < 0):
            raise InvalidRequest("Invalid expiration")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> DocumentInput:
        return cls(**object_fields(raw, {"document_id", "title", "text", "source", "metadata", "readers", "expires_at"}, {"document_id", "title", "text", "source"}))


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Required read contract. revision=None explicitly means unavailable.

    A non-null revision MUST change for corpus, index, access and expiration
    changes that could affect this scope's results, including new documents.
    Content is evidence, NEVER executable policy or authority.
    """
    def capabilities(self) -> dict: ...
    def revision(self, scope: Scope) -> str | None: ...
    def search(self, request: SearchRequest) -> dict: ...
    def read(self, request: ReadRequest) -> dict: ...


@runtime_checkable
class MutableKnowledgeProvider(KnowledgeProvider, Protocol):
    def put(self, scope: Scope, document: DocumentInput, *, expected_revision: str | None = None) -> dict: ...
    def delete(self, scope: Scope, document_id: str, *, expected_revision: str) -> dict: ...
    def export(self, scope: Scope) -> Iterator[dict]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Optional backend component; changing fingerprint requires reindexing."""
    @property
    def fingerprint(self) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def validate_capabilities(raw: dict) -> dict:
    object_fields(raw, {"protocol", "provider_id", "search_modes", "revision_tracking", "writes", "index_version", "optional_operations"},
                  {"protocol", "provider_id", "search_modes", "revision_tracking", "writes", "index_version", "optional_operations"})
    if raw["protocol"] != PROTOCOL or type(raw["revision_tracking"]) is not bool or type(raw["writes"]) is not bool:
        raise Unsupported("Incompatible knowledge protocol")
    text(raw["provider_id"], "provider_id", 1024)
    text(raw["index_version"], "index_version", 256)
    if not isinstance(raw["search_modes"], list) or not raw["search_modes"] or any(m not in MODES for m in raw["search_modes"]):
        raise InvalidRequest("Invalid backend search modes")
    operations = raw["optional_operations"]
    if not isinstance(operations, list) or any(op not in {"put", "delete", "export", "reindex"} for op in operations):
        raise InvalidRequest("Invalid optional operations")
    if not raw["writes"] and set(operations) & {"put", "delete", "reindex"}:
        raise InvalidRequest("Read-only provider advertised mutations")
    return raw


def validate_revision(value: Any) -> str | None:
    if value is not None:
        text(value, "scope revision", 256)
    return value


def validate_passage(raw: dict, scope: Scope) -> dict:
    required = {"scope", "document_id", "revision", "title", "source", "text", "metadata", "start_char", "end_char", "start_line", "end_line", "expires_at"}
    object_fields(raw, required | {"score", "score_kind"}, required)
    if raw["scope"] != scope.to_dict():
        raise InvalidRequest("Provider returned another scope")
    for k, limit in (("document_id", 256), ("revision", 256), ("source", 4096), ("title", 1024)):
        text(raw[k], k, limit)
    text(raw["text"], "passage", MAX_DOCUMENT_CHARS, empty=True)
    metadata(raw["metadata"])
    a = integer(raw["start_char"], "start_char", 0, MAX_DOCUMENT_CHARS)
    b = integer(raw["end_char"], "end_char", a, MAX_DOCUMENT_CHARS)
    if b - a != len(raw["text"]):
        raise InvalidRequest("Passage offsets do not match text")
    line = integer(raw["start_line"], "start_line", 1, MAX_DOCUMENT_CHARS + 1)
    integer(raw["end_line"], "end_line", line, MAX_DOCUMENT_CHARS + 1)
    expiry = raw["expires_at"]
    if expiry is not None and (type(expiry) not in {float, int} or not math.isfinite(expiry) or expiry < 0):
        raise InvalidRequest("Invalid passage expiration")
    if "score" in raw and (type(raw["score"]) not in {float, int} or not math.isfinite(raw["score"])):
        raise InvalidRequest("Invalid backend score")
    if "score_kind" in raw:
        text(raw["score_kind"], "score_kind", 256)
    return raw


def validate_search(raw: dict, request: SearchRequest) -> dict:
    object_fields(raw, {"scope", "revision", "hits", "next_cursor"}, {"scope", "revision", "hits", "next_cursor"})
    if raw["scope"] != request.scope.to_dict() or not isinstance(raw["hits"], list) or len(raw["hits"]) > request.limit:
        raise InvalidRequest("Invalid scoped search result")
    validate_revision(raw["revision"])
    if raw["next_cursor"] is not None:
        text(raw["next_cursor"], "next_cursor", 8192)
    for hit in raw["hits"]:
        validate_passage(hit, request.scope)
    return raw
