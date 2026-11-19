# Reproduce the calculations

Use Python 3.10+ from the gW repository root at the source revision in freeze.json.
The public-safe bundle is an overlay under research/system1-20261119/, not a runtime
distribution. Local reference packages must be available as described in Contributing.

```bash
python3 research/system1-20261119/scripts/replay.py --output /tmp/gw-system1-replay.json
python3 research/system1-20261119/scripts/analyze_live.py
python3 research/system1-20261119/scripts/summarize.py
```

Replay verifies the original frozen files and invokes the actual reducer with
explicit local reference plugins and temporary state. Compare all stable fields
to evidence/offline-results.json, excluding local_evaluation_ns. Its historical
semantic-arm status remains the initial unrun checkpoint; the live ledger and
summary provide the later observations. analyze_live.py reads the retained live
responses, unchanged cases and baseline, recomputes the exact-label confusion,
cost totals and frozen H/A projections, and imports the original reduce_effect.
Its output must exactly match evidence/live-summary.json. It makes no network call.

The hard-projection caveat is intentional: the frozen max-severity implementation
upgrades four retry approvals to denial, although the protocol prose describes
semantics only on otherwise allowed proposals. No live authorization changed.
Historical aggregate replay reproduces selected summary counts, not raw captures
or their original grading. Those private captures are excluded.

The original freeze remains byte-for-byte unchanged. AMENDMENT.md documents the
owner's pre-inference removal of the input-token cap. dispatch-freeze.json covers
that amendment and the hosted runner before smoke; cases, gold and grading were
not revised. evidence/live-results.json contains synthetic outbound payloads,
whitelisted typed responses, usage, elapsed time, account-access booleans and the
persisted reservation ledger. It contains no credential, account balance or account
identifier. Its 33 inference calls include smoke; its 36 HTTP requests include
three preflight/account checks. No automatic retries occurred.

Live inference is an explicit paid action, not required for reproduction. The
runner consumes OPENROUTER_API_KEY from the environment and refuses to run over
an existing ledger. Do not delete that ledger to bypass cumulative request/spend
limits. Independent new live replication needs a separately named allocation and
ledger; it is not an additional retry of this study. Never use old private dispatch
scripts, whose allocations and inputs differ.

Relevant documentation checks and offline examples:

```bash
export PYTHONPATH="$PWD:$PWD/packages/gw-builtin/src:$PWD/packages/gw-context/src:$PWD/packages/gw-knowledge/src"
python3 -m unittest discover -s tests -p test_documentation.py -v
python3 examples/supervision_demo.py
python3 examples/knowledge_demo.py
```

SHA256SUMS.json in the public archive covers all exported files except itself.
The bundle exporter uses an explicit whitelist, fixed archive metadata and a
sanitized historical route summary. It exports no Git history or machine inventory.
