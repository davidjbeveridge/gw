# Reproduce the follow-up without inference

Use Python 3.10+ in the repository containing this directory and the unchanged
original system1-20261119 directory. The original public snapshot is commit
`dbf077d404ba2ac7dcc6f84f4402bf222ceb231a`. This follow-up is additional evidence;
it never overwrites or relabels the original capture.

```bash
python3 research/system1-followup-20261119/scripts/analyze.py
```

The output must match evidence/summary.json exactly. The analysis joins the frozen
request list to retained typed responses, compares all matched transitions and
reconciles usage. It needs no credentials, provider, optional package or network.
The scripts/prepare.py generate() function deterministically reproduces design.json
and requests.json. Calling the function permits comparison without writing files.
freeze.json verifies all prespecified study inputs, analysis and dispatch code,
plus the original cases, transport and historical response capture.

Q0 and Q1 labels have different semantics. Do not merge unproven relevance into
supporting agreement, or missing information into a prohibition. Inspect all
selected control cases and the repeated C0Q0 control, not only the targeted helper
edits. The control selection and limitations are prespecified in PROTOCOL.md.

Live replication is paid and explicitly separate. The retained ledger prevents
accidental reruns. Do not delete it to bypass limits. No paid call is needed to
reproduce the recorded statistics. A new live replication needs its own allocation
and preserved ledger. Only synthetic proposal fields may be sent, with credentials
in the runner environment and never in request bodies, files, logs or arguments.

The public bundle overlays this follow-up directory under research/. The unchanged
original directory must be present for relative imports and frozen provenance.
Its SHA256SUMS.json covers every bundled file except itself. No Git history,
private captures, account identifiers, balances or machine inventories are included.
