"""Compile source-backed context without a knowledge store or agent harness."""
from .compiler import PROTOCOL, ContextItem, ContextCompiler, DeterministicContextCompiler, ContextBudgetExceeded
from .contract import ContextError, InvalidRequest
from .sources import ContextRequest, ContextSource, SourceResult, collect, open_source, installed_sources

__version__ = "0.1.0"
__all__ = ["PROTOCOL", "ContextItem", "ContextCompiler", "DeterministicContextCompiler",
           "ContextBudgetExceeded", "ContextError", "InvalidRequest", "ContextRequest",
           "ContextSource", "SourceResult", "collect", "open_source", "installed_sources"]
