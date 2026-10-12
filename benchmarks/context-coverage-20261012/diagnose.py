"""Read-only, post-hoc replay of HP-CTX-2026-10-11; never a new efficacy grade.

Pass the extracted closed archive root. Output goes to stdout, temporary stores
are discarded, and no archived code is executed. Requires the archived versions
of gw-knowledge and gw-context (checked by module hash before replay).
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import tempfile

from gw_context import ContextItem, DeterministicContextCompiler
from gw_knowledge import (
    ContextCache, DocumentInput, LocalKnowledgeProvider, NotFound, ReadRequest,
    Scope, SearchRequest,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_libraries(identities):
    """Fail closed: changed retrieval belongs in a separately frozen experiment."""
    checked = {}
    for identity in identities:
        package = importlib.import_module(identity["distribution"].replace("-", "_"))
        directory = Path(package.__file__).parent
        for name, expected in identity["sha256"].items():
            actual = sha256(directory / name)
            require(actual == expected, f"Library mismatch: {package.__name__}/{name}; not a frozen replay")
            checked[f"{package.__name__}/{name}"] = actual
    return checked


def span_offsets(content, start_line, end_line):
    lines = content.splitlines(keepends=True)
    require(1 <= start_line <= end_line <= len(lines), "Support range outside source")
    start = sum(len(line) for line in lines[:start_line - 1])
    end = sum(len(line) for line in lines[:end_line])
    end -= len(lines[end_line - 1]) - len(lines[end_line - 1].rstrip("\r\n"))
    return start, end


def contains(passage, path, start, end):
    return (passage["document_id"] == path and passage["start_char"] <= start
            and passage["end_char"] >= end)


def first_loss(*, ingested, permitted, indexed_whole, rank, limit, cached, compiled):
    """Earliest missing complete range; not a causal effect estimate or grade."""
    if not ingested:
        return "ingestion"
    if not permitted:
        return "permission"
    if not indexed_whole:
        return "chunk_boundary"
    if rank is None:
        return "query_match"
    if rank > limit:
        return "search_limit"
    if not cached:
        return "cache_budget"
    if not compiled:
        return "compiler_selection"
    return "delivered"


def all_hits(provider, request):
    hits, cursor = [], None
    while True:
        page = provider.search(replace(request, cursor=cursor))
        hits.extend(page["hits"])
        cursor = page["next_cursor"]
        if cursor is None:
            return hits


def audit_case(case, originals, saved):
    owner = Scope("hp-ctx", case["id"], "owner")
    worker = replace(owner, principal="worker")
    request = SearchRequest(worker, saved["query"], limit=8)
    with tempfile.TemporaryDirectory(prefix="gw-coverage-") as directory:
        with LocalKnowledgeProvider(Path(directory) / "provider") as provider, \
                ContextCache(Path(directory) / "cache") as cache:
            receipts = {}
            for path, content in sorted(originals.items()):
                receipts[path] = provider.put(owner, DocumentInput(
                    path, path, content, "repository:" + path, readers=["worker"]))
            warmup = None
            if case["condition"] in ("warm", "changed"):
                warmup = cache.assemble(provider, request, max_chars=6000)
            permitted = dict(originals)
            mutation = case.get("mutation")
            if mutation:
                path = mutation["path"]
                revoked = mutation["kind"] == "revoke"
                content = originals[path] if revoked else mutation["text"]
                provider.put(owner, DocumentInput(
                    path, path, content, "repository:" + path,
                    readers=[] if revoked else ["worker"]),
                    expected_revision=receipts[path]["revision"] if path in receipts else None)
                if revoked:
                    del permitted[path]
                    try:
                        provider.read(ReadRequest(worker, path))
                    except NotFound:
                        pass
                    else:
                        raise ValueError("Revoked source remains readable")
                    require(provider.read(ReadRequest(owner, path))["text"] == content,
                            "Revoked source was not ingested")
                else:
                    permitted[path] = content
            # Check every permitted original, not just successful retrievals.
            for path, content in permitted.items():
                require(provider.read(ReadRequest(worker, path))["text"] == content,
                        "Ingestion or source-access mismatch: " + path)
            access_hash = hashlib.sha256(json.dumps(permitted, sort_keys=True).encode()).hexdigest()
            require(access_hash == saved["source_access_sha256"], "Source collection mismatch")
            retrieval = cache.assemble(provider, request, max_chars=6000)
            require(retrieval["evidence"] == saved["retrieval"]["evidence"], "Retrieval replay mismatch")
            require(retrieval["cache"]["hit"] == (case["condition"] == "warm"), "Warm state mismatch")
            if warmup is not None and mutation:
                require(warmup["revision"] != retrieval["revision"], "Mutation failed to invalidate cache")
            items = [ContextItem(str(i), "repository", p["text"], p["document_id"],
                                 p["revision"], start_char=p["start_char"])
                     for i, p in enumerate(retrieval["evidence"])]
            compiled = DeterministicContextCompiler().compile(
                "Answer the owner question from permitted evidence.", items,
                query=request.query, max_chars=3000, scope=f'hp-ctx/{case["id"]}/worker')
            require(compiled["text"] == saved["text"], "Final packet replay mismatch")
            selected = [{**p, "document_id": p["source"]} for p in compiled["payload"]["items"]]
            require(saved["selected"] == [
                {"path": p["source"], "text": p["content"], "start_char": p["start_char"],
                 "end_char": p["end_char"]} for p in compiled["payload"]["items"]],
                "Saved selected-range mismatch")
            hits = all_hits(provider, request)
            require(all(p["document_id"] in permitted for p in hits), "Unauthorized search result")
            spans = []
            for support in case["gold"]["support_ranges"]:
                path = support["path"]
                start, end = span_offsets(permitted[path], support["start_line"], support["end_line"])
                # Read the actual derived index to distinguish a chunk boundary
                # from a whole chunk that simply fails to match/rank highly.
                whole = provider.db.execute(
                    "SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id=c.document "
                    "WHERE d.document_id=? AND c.start_char<=? AND c.end_char>=?",
                    (path, start, end)).fetchone()[0] > 0
                ranks = [i + 1 for i, hit in enumerate(hits) if contains(hit, path, start, end)]
                rank = min(ranks) if ranks else None
                cached = any(contains(p, path, start, end) for p in retrieval["evidence"])
                delivered = any(contains(p, path, start, end) for p in selected)
                spans.append({
                    "path": path, "start_line": support["start_line"], "end_line": support["end_line"],
                    "start_char": start, "end_char": end, "whole_in_index_chunk": whole,
                    "first_complete_search_rank": rank, "in_top_8": rank is not None and rank <= 8,
                    "complete_in_cache": cached, "complete_in_compiler": delivered,
                    "first_loss": first_loss(ingested=True, permitted=True, indexed_whole=whole,
                                             rank=rank, limit=8, cached=cached, compiled=delivered),
                })
            return {
                "case": case["id"], "condition": case["condition"], "query": request.query,
                "permitted_documents_verified": len(permitted), "source_access_sha256": access_hash,
                "retrieval_reproduced": True, "packet_reproduced": True,
                "warm_hit": retrieval["cache"]["hit"], "mutation_invalidated": bool(mutation),
                "revocation_checked": bool(mutation and mutation["kind"] == "revoke"),
                "ranked_hits": len(hits), "spans": spans,
                "gold_path_in_final": any(p["document_id"] == s["path"] for p in selected for s in spans),
                "cache_truncated": retrieval["truncated"],
                "compiled_chars": compiled["compiled_chars"],
                "compiler_selected_ids": [p["id"] for p in selected],
                "compiler_omitted": compiled["omitted"],
                "cache_ranges": [{"id": str(i), "path": p["document_id"],
                                  "start_char": p["start_char"], "end_char": p["end_char"]}
                                 for i, p in enumerate(retrieval["evidence"])],
            }


def summarize(rows):
    positive = [row for row in rows if row["spans"]]
    return {
        "cases": len(rows), "nonrevoked_cases": len(positive),
        "all_spans_in_top_8_cases": sum(all(s["in_top_8"] for s in r["spans"]) for r in positive),
        "all_spans_in_cache_cases": sum(all(s["complete_in_cache"] for s in r["spans"]) for r in positive),
        "all_spans_in_compiler_cases": sum(all(s["complete_in_compiler"] for s in r["spans"]) for r in positive),
        "gold_path_in_final_cases": sum(r["gold_path_in_final"] for r in positive),
        "span_first_loss_counts": dict(sorted(Counter(s["first_loss"] for r in rows for s in r["spans"]).items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_root", type=Path)
    args = parser.parse_args()
    root = args.archive_root / "research/harness-performance/context-study"
    identities = read_json(root / "results/installed-library-identity.json")
    libraries = verify_libraries(identities)
    # Hash every study file before and after: the diagnostic must not rewrite it.
    before = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    rows = []
    for case in read_json(root / "protocol/cases.json"):
        rows.append(audit_case(case, read_json(root / "inputs" / (case["repository"] + ".json")),
                               read_json(root / "results/packets" / case["id"] / "B.json")))
    after = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    require(before == after, "Frozen study files changed during diagnostic")
    report = {
        "kind": "post_hoc_frozen_pipeline_diagnostic_not_new_experiment",
        "scope": "Treatment evidence delivery only; no model calls, regrading, or efficacy estimate",
        "study_files_unchanged": True, "library_sha256": libraries,
        "input_sha256": {k: v for k, v in before.items() if k.startswith(("inputs/", "protocol/", "results/packets/"))},
        "label_caveat": "Coverage follows frozen support ranges; adjudicate ambiguous labels separately without regrading",
        "summary": summarize(rows), "rows": rows,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
