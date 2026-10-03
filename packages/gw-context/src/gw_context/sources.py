"""A narrow collection contract for optional knowledge, memory or other sources.

Factories are operator-installed code, selected by entry-point name. Scope is a
host assertion, not a credential. Sources must enforce access before collection.
The compiler itself neither imports providers nor initiates retrieval.
"""
from __future__ import annotations

import copy
import importlib.metadata
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from .compiler import ContextItem
from .contract import InvalidRequest, canonical, integer, text


@dataclass(frozen=True)
class ContextRequest:
    task: str
    scope: str
    query: str = ""
    limit: int = 16

    def __post_init__(self):
        text(self.task, "task", 100000)
        text(self.scope, "host scope", 4096)
        text(self.query, "query", 4096, empty=True)
        integer(self.limit, "source item limit", 1, 256)


@dataclass(frozen=True)
class SourceResult:
    items: tuple[ContextItem, ...]
    scope: str
    revision: str | None = None

    def __post_init__(self):
        text(self.scope, "result scope", 4096)
        if self.revision is not None:
            text(self.revision, "source revision", 4096)
        if not isinstance(self.items, tuple) or len(self.items) > 256 or any(not isinstance(i, ContextItem) for i in self.items):
            raise InvalidRequest("Source results need at most 256 typed context items")
        if sum(len(i.content) for i in self.items) > 2_000_000:
            raise InvalidRequest("Source result exceeds the content budget")


@runtime_checkable
class ContextSource(Protocol):
    def collect(self, request: ContextRequest) -> SourceResult: ...


def collect(source: ContextSource, request: ContextRequest, *, namespace: str) -> SourceResult:
    """Validate source output without allowing it to mint host instructions.

    Namespaces keep unrelated providers' document IDs from colliding. Atomic
    required instructions come from the host, never from this evidence boundary.
    Missing corpus revisions stay unknown; they are not inferred from hit hashes.
    """
    text(namespace, "source namespace", 128)
    result = source.collect(request)
    if not isinstance(result, SourceResult) or result.scope != request.scope:
        raise InvalidRequest("Context source returned an invalid or mismatched scope")
    if len(result.items) > request.limit:
        raise InvalidRequest("Context source exceeded the requested item limit")
    items = []
    for item in result.items:
        if item.required or item.trust != "evidence":
            raise InvalidRequest("A context source cannot grant instruction authority or required retention")
        # JSON array encoding is unambiguous even for provider IDs containing ':' .
        items.append(replace(item, id="source:" + canonical([namespace, item.id]),
                             source="source:" + canonical([namespace, item.source])))
    return SourceResult(tuple(items), result.scope, result.revision)


def installed_sources() -> list[str]:
    """Discover installed entry-point names without importing or running them."""
    return sorted({ep.name for ep in importlib.metadata.entry_points(group="gw_context.sources")})


def open_source(provider: str, options: dict) -> ContextSource:
    """Load one explicitly selected installed factory; never import a file path."""
    text(provider, "context source provider", 128)
    if not isinstance(options, dict) or len(canonical(options)) > 16000:
        raise InvalidRequest("Context source options must be a bounded JSON object")
    matches = list(importlib.metadata.entry_points(group="gw_context.sources", name=provider))
    if len(matches) != 1:
        raise InvalidRequest("Expected exactly one installed gw_context.sources entry point: " + provider)
    source = matches[0].load()(copy.deepcopy(options))
    if not callable(getattr(source, "collect", None)):
        close = getattr(source, "close", None)
        if callable(close):
            close()
        raise InvalidRequest("Context source must implement collect(request)")
    return source
