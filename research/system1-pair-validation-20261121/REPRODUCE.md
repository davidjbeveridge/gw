# Reproduce the broader fixed-pair validation without inference

Use Python 3.10+ with this directory and the unchanged earlier study directories.
The prior curated public snapshot is 3b085edab72daf30ce2bb2d3a2e557ba6d37ac32.

```bash
python3 research/system1-pair-validation-20261121/scripts/analyze.py
```

Output must match evidence/summary.json exactly. It joins independent component
responses by case/trial, applies the unchanged conservative composition, and
reports shared outside-scope errors separately from structural non-scope blind
spots. No response is changed, no provider is contacted and no credential or
optional dependency is needed. Calling generate() in scripts/prepare.py reproduces
heldout-cases.json and requests.json as JSON values without writing those files.
The command-line entry point writes them, so prefer the function for comparison.

freeze.json covers all study inputs and preparation/runner/analysis, plus prior
question/context, transport, composition and minimal-payload provenance. The main
and scope prompts, input projections and composition are unchanged. All 384
measurements were frozen before the independent main smoke and shuffled with
seed 2026112103. There are 64 full proposals, three trials and two independent
component calls per trial. Repeated calls are not independent new cases.

Some missing-field minimal payloads inevitably repeat earlier shapes such as
edit+null target. Summary provenance counts disclose actual unique/novel minimal
inputs; critical inside/outside edit payloads were checked novel before freeze.
All full proposal states are new. Known error patterns informed this selected
stress set, so it is not independent blind or unrelated-domain validation.

Inside-scope and not-an-edit do not mean globally permitted. Inspect main errors
on inside documentation/test edits and exhausted retries separately: scope is
correct to return no directory violation on them. On outside edits inspect the
both-flag/main-only/scope-only/neither table, separating permission from missing-
information review. Do not infer independent errors from marginal accuracy or
multiply component rates into a safety estimate. Gold prefix checks are offline
validation only and never replace model answers or supply input-derived labels.

The prior serial reservation transport is unchanged. Before each paid call it
persists US$0.0111, validates actual reported billing before settlement, and stops
on unknown outcomes. A fresh exclusive ledger prevents rerun. Allocation limits
remain 400 total HTTP requests and US$0.50 incremental inference, no token cap,
retry, fallback or top-up. Do not delete a retained ledger to bypass caps; new paid
replication requires its own explicit allocation. Offline replay is sufficient to
reproduce the published calculations.

The public bundle overlays research/system1-pair-validation-20261121/ alongside
unchanged earlier directories. SHA256SUMS.json covers all bundled files except
itself. The whitelist excludes credentials, account IDs/balances, private captures,
machine inventories and Git history. No worker, proposed action, site deployment
or DB Consulting operation occurs in this study.
