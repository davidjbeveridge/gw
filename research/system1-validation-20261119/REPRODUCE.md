# Reproduce the repeated validation without inference

Use Python 3.10+ from the gW repository containing this directory and the unchanged
original system1-20261119 and system1-followup-20261119 directories. Their curated
public snapshot is commit 28dd5aaeadd5aa0cbedbbdf0197b98271167034b.

```bash
python3 research/system1-validation-20261119/scripts/analyze.py
```

Output must match evidence/summary.json exactly. The analysis joins every frozen
case/setup/trial request to its retained typed answer, reports trial and case
statistics, computes all matched transitions and reconciles actual API charges.
It requires no credentials, provider connection or optional packages. It does not
pretend that three repetitions are three independently authored cases.

Calling generate() in scripts/prepare.py reproduces fresh-cases.json and
requests.json as JSON values without writing files. The script's command-line
entry point writes those files, so prefer the function when comparing a retained
freeze. freeze.json pins the protocol, approved allocation, all fresh cases,
full request plan, runner, preparation and analysis, plus the unchanged prior
question/context/case dependencies. The exact prior combined setup is reused.

Each cohort has 12 supporting cases, 12 conflicting cases and eight uncertain
cases. Each case has three trials in each setup. Trial denominators per cohort
and setup are 36 supporting, 36 conflicting and 24 uncertain responses. Unique
case denominators remain 12, 12 and eight. Inspect both denominators, per-case
variation, introduced/recovered signals and all error categories.

Qualified permission is separate from full supporting agreement. Conflict
non-detections are split into permission answers and abstentions. A failed
conflict detection is not proof that a proposed action executed or that the
unchanged deterministic authorizer would allow it.

The serial ledger persists a full per-call cost reservation before dispatch,
settles only validated reported cost, and halts on unknown outcomes. A known
completed call's reservation can be released; its actual cost remains counted.
The approved cap is 400 total runner HTTP requests and US$0.50 incremental
inference, with no input-token cap, retries, fallback or top-up. Do not delete an
existing ledger or rerun it to bypass cumulative accounting. New paid replication
requires a new explicit allocation and separately preserved ledger; recorded
statistics can be reproduced offline.

The public bundle overlays research/system1-validation-20261119/ alongside the
unchanged earlier directories. SHA256SUMS.json covers every exported file except
itself. The whitelist excludes credentials, private captures, account identifiers,
account balances, machine inventories and Git history. No personal-site deployment
or DB Consulting operation is part of this study.
