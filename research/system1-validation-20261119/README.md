# Full-cohort and fresh-case repeated Jev validation

Read the [report](REPORT.md), [frozen protocol](PROTOCOL.md),
[fresh cases](fresh-cases.json), [live responses](evidence/live-results.json),
[matched trial/case results](evidence/summary.json), and
[reproduction instructions](REPRODUCE.md).

The original 32 cases and 32 fresh cases received three trials under both the
unchanged original setup and the prior combined setup, with Jev fixed. The combined
setup removed 11 original-cohort supporting alarms but lost two conflict detections
on one outside-directory edit. Fresh conflicts were all caught under both setups;
the combined setup lost six information-missing signals on two incomplete cases.
This is a tradeoff, not an unqualified reliability improvement. Earlier studies
and deterministic authorization remain unchanged. No worker or proposed action ran.
