# Broader fixed-pair shared-miss validation

[Report](REPORT.md), [protocol](PROTOCOL.md), [fresh cases](heldout-cases.json),
[live responses](evidence/live-results.json), [paired overlap analysis](evidence/summary.json),
and [reproduction](REPRODUCE.md).

The unchanged pair was tested on 64 fresh full proposals, three trials of each
component. It reduced main's conflict misses from 19/96 to 7/96 but both checks
missed four root-like-prefix cases, including fixture-old/helper1.py in every
trial. Six supporting alarms and one incomplete permission answer remained.
The previous zero-error sample did not generalize to this selected stress set.
Earlier results, deterministic authority and the default branch are preserved.
No proposed action or worker ran.
