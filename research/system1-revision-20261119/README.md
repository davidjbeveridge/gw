# Failure investigation and held-out revision test

Read the [report](REPORT.md), [protocol](PROTOCOL.md), [exact design](design.json),
[held-out cases](heldout-cases.json), [live responses](evidence/live-results.json),
[paired analysis](evidence/summary.json) and [reproduction instructions](REPRODUCE.md).

Literal prerequisite instructions improved missing-information handling. The revised
setup had zero supporting alarms, two conflict misses and 30/30 correct incomplete-
information signals on 40 new cases tested three times. Old combined had zero
supporting alarms, six conflict misses and 9/30 information signals; original had
two supporting alarms, zero conflict misses and 18/30 information signals.

The revised setup improved old combined on this sample but still wrongly supported
one outside-directory case in two trials. Keep the result advisory. Diagnostics
did not establish basename confusion as the internal cause. Earlier studies and
deterministic authorization are unchanged. No proposed action or worker ran.
