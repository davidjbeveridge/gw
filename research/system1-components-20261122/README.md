# Explicit path components without a verdict

[Report](REPORT.md), [protocol](PROTOCOL.md), [design](design.json),
[fresh held-out cases](heldout-cases.json), [live responses](evidence/live-results.json),
[matched analysis](evidence/summary.json) and [reproduction](REPRODUCE.md).

The exact same Jev question was tested on 64 fresh scope cases, three trials under
raw and raw-plus-components input. Literal splitting supplied component lists,
not a root comparison or verdict. Outside misses fell from 27/72 to 3/72 without
new false outside flags or matched errors. fixture.snapshot/helper3.py remained
wrong in every trial, and two omitted-operation cases remained wrong under both
conditions. No main-plus-scope result is claimed. Earlier studies and deterministic
authority remain unchanged; no worker or proposed action ran.
