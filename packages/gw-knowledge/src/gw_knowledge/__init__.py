"""Standalone knowledge contracts. No agent harness or inference dependencies."""
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, DocumentInput,
    KnowledgeProvider, MutableKnowledgeProvider, EmbeddingProvider,
    KnowledgeError, InvalidRequest, NotFound, Conflict, Unsupported, Unavailable,
)
from .local import LocalKnowledgeProvider
from .cache import ContextCache

__version__ = "0.1.0"
__all__ = ["PROTOCOL", "Scope", "SearchRequest", "ReadRequest", "DocumentInput",
           "KnowledgeProvider", "MutableKnowledgeProvider", "EmbeddingProvider",
           "LocalKnowledgeProvider", "ContextCache", "KnowledgeError",
           "InvalidRequest", "NotFound", "Conflict", "Unsupported", "Unavailable"]
