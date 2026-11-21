# Separate directory-scope question study

Read the [report](REPORT.md), [protocol](PROTOCOL.md), [design](design.json),
[held-out cases](heldout-cases.json), [live evidence](evidence/live-results.json),
[scope/permission analysis](evidence/summary.json), and [reproduction instructions](REPRODUCE.md).

The standalone scope question still made directory mistakes: three outside-edit
misses with full state and six with minimal state across 36 repeated outside-edit
decisions. The preselected conservative main-plus-minimal-scope projection caught
all 51 conflict decisions, retained all 30 incomplete-information signals and
introduced no supporting alarms in this sample. This was complementary error
coverage, not reliability of either model check alone. Earlier results and
deterministic authorization remain unchanged; no task action or worker ran.
