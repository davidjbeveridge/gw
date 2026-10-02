"""Run a source/cache example using only temporary local data and no inference."""
from __future__ import annotations

import json
import pathlib
import tempfile
from gw_knowledge import ContextCache, DocumentInput, LocalKnowledgeProvider, ReadRequest, Scope, SearchRequest


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="gw-knowledge-example-") as directory:
        root = pathlib.Path(directory)
        scope = Scope("local", "example", "owner")
        with LocalKnowledgeProvider(root / "sources") as provider, ContextCache(root / "cache") as cache:
            original = "Provider failures use the configured error policy."
            receipt = provider.put(scope, DocumentInput("architecture", "Architecture", original,
                                                        "https://example.test/architecture", {"kind": "decision"}))
            query = SearchRequest(scope, "provider failures")
            first = cache.assemble(provider, query)
            second = cache.assemble(provider, query)
            provider.put(scope, DocumentInput("operations", "Operations", "Provider failures require an operator check.",
                                               "https://example.test/operations", {"kind": "runbook"}))
            updated = cache.assemble(provider, query)
            cache.clear(scope)
            source = provider.read(ReadRequest(scope, "architecture", receipt["revision"]))
            result = {
                "first_hit": first["cache"]["hit"], "second_hit": second["cache"]["hit"],
                "after_addition_hit": updated["cache"]["hit"],
                "documents": sorted({p["document_id"] for p in updated["evidence"]}),
                "source_survives_eviction": source["text"] == original,
            }
            expected = {"first_hit": False, "second_hit": True, "after_addition_hit": False,
                        "documents": ["architecture", "operations"], "source_survives_eviction": True}
            if result != expected:
                raise AssertionError(f"Unexpected cache result: {result!r}")
            return result


if __name__ == "__main__":
    print(json.dumps(run(), separators=(",", ":")))
