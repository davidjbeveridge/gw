"""Compatibility import only. Install gw-context for the extracted compiler.

Knowledge storage/search do not require that package. New integrations should
import gw_context directly. No implementation or hidden fallback lives here.
"""
try:
    from gw_context.compiler import (
        PROTOCOL, ContextItem, ContextCompiler, DeterministicContextCompiler,
        ContextBudgetExceeded,
    )
except ModuleNotFoundError as exc:
    if exc.name != "gw_context":
        raise
    raise ImportError("Context compilation moved to the independent gw-context package; install it and import gw_context") from exc
