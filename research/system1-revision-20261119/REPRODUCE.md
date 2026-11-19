# Reproduce investigation and held-out grades without inference

Use Python 3.10+ in the repository containing this directory and the unchanged
system1-20261119, system1-followup-20261119 and system1-validation-20261119 directories.
The previous curated public snapshot is 8cb009a57b7183c3d9c4a9742ee4abfcc25c9a8e.

```bash
python3 research/system1-revision-20261119/scripts/analyze.py
```

Output must match evidence/summary.json exactly. It reports diagnostics separately
from the held-out comparison, every case's repeated labels, and all matched held-
out transitions. It makes no provider requests and needs no credential or optional
package. Calling generate() in scripts/prepare.py reproduces design.json,
diagnostic-cases.json, heldout-cases.json and requests.json without writing files.
The command-line entry point writes those files, so use the function for retained
freeze verification. freeze.json covers protocol, allocation, all study inputs,
analysis/runner and the prior transport/context/question/case dependencies.

The full revision and all held-out cases were frozen before diagnostics. The first
24 measured calls are diagnostics; the remaining 360 are three trials of 40 held-
out cases under original, old combined and revised conditions. Only the frozen
full revision is tested as the candidate. No diagnostic or held-out response
selects another prompt. Do not pool diagnostics into held-out performance.

The held-out proposals are new complete task/action/failure states. They share
known failure families and the original task, and were authored with knowledge of
the earlier errors. Repeated responses are not independently authored cases.
Qualified permission remains distinct from supported relevance; conflict permission
answers and abstentions are reported separately. No model label changes a
permission decision or executes an action.

The inherited transport is unchanged. Every paid serial call has a persisted
US$0.0111 reservation before dispatch; only validated billed cost releases it.
Any unknown outcome retains the reservation and stops. The fresh exclusive ledger
prevents rerun. This allocation is capped at 400 total runner HTTP requests and
US$0.50 incremental inference, without an input-token ceiling. Never delete a
ledger to bypass those limits. Independent new paid replication needs a new
allocation; all recorded calculations reproduce offline.

The public bundle overlays research/system1-revision-20261119/ alongside the older
directories. SHA256SUMS.json covers all exported files except itself. The explicit
whitelist excludes credentials, account IDs/balances, private captures, machine
inventories and Git history. No site deployment is part of this evidence release.
