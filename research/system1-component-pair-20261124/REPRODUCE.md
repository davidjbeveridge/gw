# Reproduce the enriched-pair validation without inference

Use Python 3.10+ with this directory and unchanged earlier study directories.
The previous curated snapshot is 4b6392162aa19a5a8291a21cd7ffbb293b3e2e0e.

```bash
python3 research/system1-component-pair-20261124/scripts/analyze.py
```

Output must match evidence/summary.json exactly. It joins independent main/scope
responses by case/trial and applies the unchanged conservative projection. Scope
and full-permission grades remain separate. Incomplete permission versus prohibition
answers, absent/null/empty operation forms and correct main review signals lost
to scope overrides are all reported. No model, credential or optional package is
required. Calling generate() in scripts/prepare.py reproduces design, cases and
request plan as JSON values without writing files; its CLI writes them.

freeze.json covers all new experiment inputs/code plus prior main/context,
component function, scope question/vocabulary, transport and composition sources.
The component function is imported unchanged: literal slash splitting and root
trailing-slash removal only, with no comparison or verdict. A pre-dispatch metadata
note records verifying the current standard/ZDR listing entries independently
against the same pinned TypeSafe model/rates/bounds; all changes were frozen before
any request. The inference body, no-fallback policy and classifier inputs did not
change to accommodate the listing.

There are 64 new full proposal states, three trials per component. Primary edit
minimal states are also new. Two non-edit missing-target controls can repeat earlier
raw scope shapes; disclose them rather than counting them as new scope evidence.
Known failure families informed the dot-root and absent-operation stress set.
Repeated calls and related cases are not independent population samples.

The main and component-enriched scope questions and conservative projection are
unchanged. Main prohibitions are retained; scope outside adds prohibition, missing
scope adds review, and inside/not-an-edit never grants permission or clears main.
An erroneous outside answer on an absent-operation case can override a correct
main missing-information signal: count it, do not silently correct it with an
input-derived operation check. No oracle replaces the model's returned label.

The unchanged serial transport persists US$0.0111 per paid call before dispatch,
settles only verified billed cost and halts on unknown outcomes. Its exclusive
ledger prevents rerun. Limits are 400 runner HTTP requests and US$0.50 incremental
inference with no token cap, retries, fallback or top-up. Never delete a ledger
to bypass those bounds. New paid replication requires its own explicit allocation;
all published grades can be recomputed offline.

The public-safe bundle overlays research/system1-component-pair-20261124/ alongside
prior unchanged directories. SHA256SUMS.json covers every bundled file except itself.
It excludes credentials, account IDs/balances, private captures, machine inventories
and Git history. No worker, proposed action, live authorization, personal-site
deployment or DB Consulting operation occurs here.
