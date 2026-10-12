"""Offline diagnostic checks, not additional study cases or model outcomes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


AVAILABLE = all(importlib.util.find_spec(name) for name in ("gw_knowledge", "gw_context"))
if AVAILABLE:
    from gw_context import ContextItem, DeterministicContextCompiler
    from gw_knowledge import ContextCache, DocumentInput, LocalKnowledgeProvider, Scope, SearchRequest
    spec = importlib.util.spec_from_file_location(
        "coverage_diagnostic", Path(__file__).resolve().parents[1]
        / "benchmarks/context-coverage-20261012/diagnose.py")
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)


@unittest.skipUnless(AVAILABLE, "Optional knowledge and context packages")
class CoverageDiagnosticTests(unittest.TestCase):
    def test_real_rank_one_hit_can_be_lost_at_compiler(self):
        # Synthetic development fixture, unrelated to the frozen 24 questions.
        # Rare exact evidence wins BM25; common terms win raw lexical overlap.
        with tempfile.TemporaryDirectory() as directory:
            with LocalKnowledgeProvider(Path(directory) / "p") as provider, \
                    ContextCache(Path(directory) / "c") as cache:
                scope = Scope("fixture", "development", "owner")
                for i in range(20):
                    provider.put(scope, DocumentInput(
                        f"filler-{i}", "filler", "alpha beta gamma\n" + "filler " * 100, "fixture"))
                target = "raretoken " * 5 + "\n" + "padding " * 205
                provider.put(scope, DocumentInput("target", "target", target, "fixture"))
                request = SearchRequest(scope, "raretoken alpha beta gamma")
                hits = diagnostic.all_hits(provider, request)
                self.assertEqual(hits[0]["document_id"], "target")
                packet = cache.assemble(provider, request, max_chars=6000)
                self.assertTrue(any(p["text"] == target for p in packet["evidence"]))
                items = [ContextItem(str(i), "repository", p["text"], p["document_id"],
                                     p["revision"], start_char=p["start_char"])
                         for i, p in enumerate(packet["evidence"])]
                result = DeterministicContextCompiler().compile(
                    "Find evidence", items, query=request.query, max_chars=3000)
                selected = {p["source"] for p in result["selected"]}
                self.assertNotIn("target", selected)
                self.assertEqual(diagnostic.first_loss(
                    ingested=True, permitted=True, indexed_whole=True, rank=1,
                    limit=8, cached=True, compiled="target" in selected), "compiler_selection")

    def test_cache_prefix_must_not_count_as_complete_support(self):
        with tempfile.TemporaryDirectory() as directory:
            with LocalKnowledgeProvider(Path(directory) / "p") as provider, \
                    ContextCache(Path(directory) / "c") as cache:
                scope = Scope("fixture", "development", "owner")
                content = "needle " + "x" * 900 + "\nproof = 'é'\n"
                provider.put(scope, DocumentInput("source", "source", content, "fixture"))
                request = SearchRequest(scope, "needle")
                start, end = diagnostic.span_offsets(content, 2, 2)
                hit = provider.search(request)["hits"][0]
                self.assertTrue(diagnostic.contains(hit, "source", start, end))
                packet = cache.assemble(provider, request, max_chars=512)
                self.assertTrue(packet["evidence"])
                self.assertTrue(packet["truncated"])
                self.assertFalse(any(diagnostic.contains(p, "source", start, end)
                                     for p in packet["evidence"]))
                self.assertEqual(diagnostic.first_loss(
                    ingested=True, permitted=True, indexed_whole=True, rank=1,
                    limit=8, cached=False, compiled=False), "cache_budget")

    def test_exact_offsets_disambiguate_repeated_text_and_unicode(self):
        content = "é = 1\r\nproof\r\nproof\r\n"
        start, end = diagnostic.span_offsets(content, 3, 3)
        self.assertEqual(content[start:end], "proof")
        wrong = {"document_id": "a", "start_char": 7, "end_char": 12}
        self.assertFalse(diagnostic.contains(wrong, "a", start, end))
        with self.assertRaisesRegex(ValueError, "outside source"):
            diagnostic.span_offsets(content, 3, 4)

    def test_modified_library_cannot_masquerade_as_frozen_replay(self):
        with self.assertRaisesRegex(ValueError, "not a frozen replay"):
            diagnostic.verify_libraries([{
                "distribution": "gw-context", "sha256": {"compiler.py": "0" * 64}}])

    def test_empty_revoked_cases_do_not_inflate_coverage(self):
        revoked = {"spans": [], "gold_path_in_final": False}
        summary = diagnostic.summarize([revoked, revoked])
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["nonrevoked_cases"], 0)
        self.assertEqual(summary["all_spans_in_compiler_cases"], 0)


if __name__ == "__main__":
    unittest.main()
