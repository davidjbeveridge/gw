# Fresh main plus component-enriched scope validation

Read the [technical report](REPORT.md), [frozen protocol](PROTOCOL.md),
[reproduction instructions](REPRODUCE.md) and [deployment handoff](HANDOFF.md).
The [evidence](evidence/summary.json) contains case/trial comparisons and the
[sanitized ledger](evidence/live-results.json) retains actual typed payloads and outputs.

On 64 new full proposals, three trials per component, the fixed Jev pair reduces
conflict misses from 56/90 to 12/90 and leaves supporting false alarms at 10/48.
It introduces nine wrong prohibitions on incomplete proposals, losing nine correct
main missing-information signals. Four outside dot-root cases are accepted by both
checks in every trial. The frozen balanced-improvement criterion fails.

This is selected synthetic stress evidence. Earlier results, deterministic
runtime authorization and the default branch remain intact. Scope judgments do
not execute actions or establish production safety. Actual inference cost:
US$0.013372086 across 385 inference calls (388 total runner HTTP requests).

The public-safe archive is an overlay at research/system1-component-pair-20261124/
alongside unchanged earlier directories. Its manifest hashes every bundled file
except itself. It contains no private inputs, credentials, machine inventory or
private Git ancestry. No personal-site deployment or DB Consulting operation occurs.
