# Reproduce the exact-root revision study without inference

Use Python 3.10+ with this directory and the unchanged earlier study directories.
The preceding curated snapshot is d20fb611acd91c981291d9ca0061ad6a319ba20b.

```bash
python3 research/system1-root-revision-20261121/scripts/analyze.py
```

Output must exactly match evidence/summary.json. Diagnostic scope grades remain
separate from held-out scope and full-permission projections. The script normalizes
revised labels only through the frozen one-to-one vocabulary map; it never fixes
model output from a computed path prefix. It requires no model call, credentials
or optional packages. Calling generate() in scripts/prepare.py reproduces design,
diagnostic/held-out cases and request order as JSON values without writing files.
The command-line entry point writes those files, so prefer the function for a
retained-freeze comparison.

freeze.json covers all new experiment inputs/code and prior question, transport
and composition dependencies. The candidate with the four-example block was
selected before all new inference. Diagnostics precede held-out requests but do
not alter the candidate. METHODS_NOTE.md clarifies that the base criterion already
contains one illustrative root; this is an added-example-block ablation, not a
clean zero-example contrast. The clarification did not change frozen bytes.

Every full held-out proposal is new; primary inside/outside raw scope states
are also new relative to prior scope calls. Exact example paths and diagnostic
raw states are excluded from held-out cases. Missing/non-edit format controls
may repeat earlier projected inputs; report those honestly. Cases target known
failure families in one synthetic task and are not independently sampled blind
external validation. Three trials are not independent newly authored cases.

The minimal state is unchanged raw operation/path/root. No first-component or
prefix result is precomputed and supplied. Main and old scope are unchanged;
conservative composition preserves main prohibition, adds scope prohibition or
missing-information review, and never turns inside/not-an-edit into permission.
No worker, action, delivered review or live authorizer is tested.

The unchanged serial transport persists a US$0.0111 reservation before each paid
call, settles only verified reported cost and halts on unknown outcomes. A new
exclusive ledger prevents rerun. Retained limits are 400 total HTTP requests and
US$0.50 incremental inference, no token cap, retry, fallback or top-up. Do not
delete the ledger to bypass limits; new paid replication needs a new allocation.
All recorded grades reproduce offline.

The public-safe overlay belongs under research/system1-root-revision-20261121/.
SHA256SUMS.json covers all exported files except itself. No secrets, account data,
private captures, machine inventory or Git history is included. No personal-site
deployment or DB Consulting operation is part of this study.
