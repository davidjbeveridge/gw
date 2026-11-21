# Reproduce the separate-scope study without inference

Use Python 3.10+ with this directory and the unchanged earlier study directories.
The prior curated snapshot is c0df0d93c5884436605da035ee459b2dcc3a86fb.

```bash
python3 research/system1-scope-20261121/scripts/analyze.py
```

The output must match evidence/summary.json exactly. It keeps directory-only
accuracy separate from full-permission grades and joins independent main/scope
responses by case/trial for conservative offline projections. All source labels
and probabilities remain unchanged. It requires no credential, optional package
or network. Calling generate() in scripts/prepare.py reproduces design.json,
diagnostic-cases.json, heldout-cases.json and requests.json without writing files.
The script's command-line entry point writes those files.

freeze.json covers all study inputs and preparation, runner, transport and
analysis, plus prior source dependencies. The transport is the previous cost-
reservation transport with named-question validation generalized from alignment
to exactly the submitted question keys/vocabularies; a pre-inference formatting
correction removed trailing blank lines. No prior source file was modified.

The first 24 measured requests are diagnostics, followed by 360 held-out requests.
No held-out payload duplicates a new diagnostic payload, including minimal-state
projection. Forty full held-out proposals collapse to 36 unique minimal-scope
payloads after removing purpose/context. Repeated or collapsed inputs are not
independent new scope examples. Scope gold is a literal relative-path contract,
not a filesystem/symlink/traversal/platform-resolution contract.

Directory scope inside/not-an-edit never establishes overall permission. Preserve
all main denials and incomplete-information signals when reproducing the offline
projection. Inside documentation/test edits and non-edit retry/incomplete cases
are deliberate controls. Missing-scope outputs add review signals; they do not
execute a review or repair task. Do not silently replace model answers with a
prefix oracle: the offline prefix oracle validates gold only.

Recorded results reproduce offline. Live replication is paid, requires a new
explicit allocation and must preserve the existing ledger. Never remove that
ledger to bypass caps. Each serial paid call has US$0.0111 reserved before dispatch;
only validated actual billing releases the reservation. Unknown outcomes halt.
The new allocation retains 400 total HTTP requests and US$0.50 incremental
inference, no token cap, no retries, fallback or top-up.

The public bundle overlays research/system1-scope-20261121/ alongside prior
unchanged directories. SHA256SUMS.json covers all bundled files except itself.
It excludes secrets, account IDs/balances, private captures, machine inventories
and Git history. No personal-site deployment or DB Consulting operation occurs.
