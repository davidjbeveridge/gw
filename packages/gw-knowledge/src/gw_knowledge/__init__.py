"""Standalone knowledge contracts. No agent harness or inference dependencies."""
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, DocumentInput,
    KnowledgeProvider, MutableKnowledgeProvider, EmbeddingProvider,
    KnowledgeError, InvalidRequest, NotFound, Conflict, Unsupported, Unavailable,
)
from .local import LocalKnowledgeProvider
from .cache import ContextCache

__version__ = "0.3.0"
__all__ = ["PROTOCOL", "Scope", "SearchRequest", "ReadRequest", "DocumentInput",
           "KnowledgeProvider", "MutableKnowledgeProvider", "EmbeddingProvider",
           "LocalKnowledgeProvider", "ContextCache", "KnowledgeError",
           "InvalidRequest", "NotFound", "Conflict", "Unsupported", "Unavailable"]

def __getattr__(name):
    # Preserve explicit historical imports only when the optional compiler is
    # installed. Ordinary knowledge imports never load or require gw-context.
    if name in {"ContextItem", "ContextCompiler", "DeterministicContextCompiler", "ContextBudgetExceeded"}:
        from . import compiler
        return getattr(compiler, name)
    raise AttributeError(name)
