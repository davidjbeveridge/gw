# Reproduce the representation-only comparison without inference

Use Python 3.10+ with this directory and the unchanged earlier study directories.
The preceding curated public snapshot is ef1e9ba9541fd4d79c249a66b3ac1101d28211bd.

```bash
python3 research/system1-components-20261122/scripts/analyze.py
```

Output must match evidence/summary.json exactly. It reports scope confusion,
corrected/newly introduced matched errors, repeated-case consistency and the 24
outside/inside path contrasts. It needs no model, credential or optional package.
Calling generate() in scripts/prepare.py reproduces design.json, heldout-cases.json
and requests.json without writing files; the command-line entry point writes them.
freeze.json covers all input/code and prior question/transport dependencies.

Every raw scope state is new relative to earlier scope requests and distinct
within this set. The component condition has exactly the same raw state and
question plus one path_components object. Its target_components is literal
slash splitting; allowed_root_components is the allowed root stripped of trailing
slash and split on slash. No comparison, prefix predicate, equality flag, verdict,
preselected first-directory value, length score or permission field is supplied.
The representation function is audited before inference for comparison/predicate
operations, and actual payloads are checked against the frozen uniform schema.

There are 64 scope cases, three trials under raw and components, with 24 matched
outside/inside edit path pairs. Repeated calls, matched paths and shared families
are not independent samples. The set also has eight non-edits and eight missing-
operation cases. It does not claim new missing-target format validation or a new
main-plus-scope result: main is not called in this allocation.

All model labels remain unchanged. A frozen one-to-one vocabulary map permits
comparison with scope gold; it does not replace an answer with a computed root
comparison. The prefix oracle checks gold offline only. Component parsing is a
real deterministic input transformation, not model-only extraction. Neither it
nor a model prediction implements an actual filesystem permission decision.

The unchanged transport reserves US$0.0111 before every serial paid call and
settles only validated reported cost. Unknown outcomes retain reservations and
halt; an exclusive fresh ledger prevents rerun. Limits remain 400 HTTP requests
and US$0.50 incremental inference, without a token ceiling, retries, fallback or
top-up. Never delete the ledger to bypass caps. New paid replication requires
a new explicit allocation; recorded calculations reproduce offline.

The public-safe overlay belongs under research/system1-components-20261122/.
SHA256SUMS.json covers all exported files except itself. The whitelist excludes
secrets, account data, private captures, machine inventory and Git history. No
proposed action, live authorizer, worker, site deployment or DB Consulting work
is part of this research.
