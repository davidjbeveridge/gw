# Read-only context coverage diagnostic

This tool traces complete source evidence through the frozen
`HP-CTX-2026-10-11` treatment pipeline. It adds no retrieval-policy change,
model calls, or new efficacy result. Research data and derived case-level
reports are deliberately excluded from this public directory.

The diagnostic separates source ingestion/access, indexed chunk boundaries,
query matching, search limits, cache prefix truncation, and compiler selection.
Finding the right document or getting a cache hit is not counted as delivery
of the required source span. Complete-span coverage is not answer acceptance.

## Run against an authorized local archive

Install the knowledge and context packages matching the archive's recorded
module hashes. Extract the archive outside this checkout and pass the directory
containing its `research` folder. Keep output outside both the archive and any
public repository:

```bash
python -m pip install ./packages/gw-knowledge ./packages/gw-context
python benchmarks/context-coverage-20261012/diagnose.py /path/to/extracted-archive > /tmp/context-trace.json
python -m unittest discover -s tests -p test_context_coverage_diagnostic.py -v
```

The script reads JSON only; it never executes archived scripts. It rebuilds
temporary SQLite stores, applies declared source/access mutations, verifies
permitted documents, and compares retrieval evidence and compiled text with
the frozen records. It inspects the actual local chunk index and paginates the
matching search stream to identify the first stage missing each complete range.
This implementation is specific to the archive's SQLite-backed pipeline.

Module-hash changes, source-collection mismatches, or nonidentical replay packets
fail explicitly. All study files are hashed before and after to detect accidental
writes. JSON output goes to stdout and temporary stores are discarded. The output
includes case queries, paths, ranks and input hashes, so treat it with the same
access restrictions as the input research. Do not commit it without authorization.

## Diagnostic tests

Five offline tests use newly authored synthetic data. They check a real BM25
rank-one hit lost during compiler selection, a cached source prefix lacking
the required tail evidence, exact offsets with Unicode/repeated text, rejection
of a changed library as a frozen replay, and exclusion of empty revoked cases
from positive-support coverage. These are development diagnostics, not held-out
model evaluations or a claim that the current selection policy is desirable.

## Interpretation and next experiments

The first missing stage locates an omission; it does not isolate a causal effect
on answer quality. Chunk size, query construction, ranking and budgets interact.
For example, the compiler's documented lexical ranking can reorder successful
backend retrieval. Neither matching a source path nor preserving exact offsets
establishes that the selected evidence is sufficient to answer the question.

Keep frozen grades and separately reported label sensitivities unchanged. Any
changed retrieval behavior requires a new experiment: develop on separate cases,
freeze code, corpus, permissions, labels, budgets and success criteria, then
evaluate on unseen cases separated by repository and symbol family. Cases
already inspected during diagnosis cannot serve as held-out validation. Report
evidence coverage and answer quality alongside token usage; these diagnostics
do not establish developer-productivity benefits.
