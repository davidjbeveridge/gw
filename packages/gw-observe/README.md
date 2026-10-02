# gw-observe

Deterministic local run observability. Independent of the GW supervisor; MIT,
Python 3.10+, no runtime dependencies. Version 0.1.0. Metadata envelope
`gw.observation/1`; cloud interoperability uses standard OTLP/HTTP JSON.

Install this directory with `python -m pip install .`. The release includes a
standalone wheel/source archive; no PyPI publication is implied.

```bash
gw-observe start --project . --harness custom --model YOUR_MODEL --name "Experiment"
gw-observe runs
gw-observe show RUN_ID
gw-observe timeline RUN_ID
gw-observe finish RUN_ID --outcome succeeded --evidence "Operator checked results"
gw-observe serve --open
```

`--directory PATH` precedes the command and selects the local trace store. The
stdlib dashboard is read-only and bearer-authenticated. It shows per-goal state,
recorded judgments, usage coverage, source references, context relationships,
learning history and descriptive comparisons. It does not call models or infer
that an intervention caused savings.

`LocalTraceRepository` implements the `TraceRepository` protocol; producers need
only `ObservationSink.record(envelope)`. Use public start/finish/record/run/report/
timeline/event/compare methods. Records have stable ID, existing run ID, optional
session/parent ID, kind, Unix nanosecond start/end, bounded attributes and source
locator. Run manifests are immutable. Metadata, snapshots and source locators live
in SQLite WAL. Original transcripts and application records stay with their owner.

`import FILE --run ID --format claude-jsonl|codex-jsonl` explicitly indexes supported
native records by byte position/hash. It never scans unrelated histories or copies
full source content. Streaming message duplicates and cumulative usage counters
are normalized; overlapping sources for one session are not blindly summed. Local
import/revision is a capability of this repository, not a requirement for every
remote adapter.

`event ID --source` resolves only registered references and reports missing/changed
sources. `record FILE` accepts an explicit metadata envelope. `outcome --run ID
--goal NAME --value met|not_met|unknown --evidence REFERENCE` records an assertion,
not an automatically verified fact. `compare RUN_A RUN_B` exposes changed starting
variables and observed results. No code reset or task execution is performed.

`export-otlp RUN_ID --output trace.json` writes standard OTLP/HTTP JSON. An explicit
`--endpoint URL` sends metadata to a compatible collector; `--key-env NAME` or
`--headers-env NAME` supplies secret references. No automatic uploads, full prompt
exports, or stale collector-success claims. Partial rejection raises an error.

Counters have explicit coverage. Input/output totals do not add cache/reasoning
subsets twice. Anthropic cache inputs are normalized once. Costs are reported,
not guessed from plan prices. Semantic tool/task/skill attribution is not invented:
explicit fields or labeled name hints are used. Logging has CPU/disk overhead;
there are no inference tokens for logging or charts.

Read the source protocols and tests for adapter contracts. Full GW integration
and limitations are documented at
https://github.com/davidjbeveridge/gw/blob/main/docs/OBSERVABILITY.md.
Optional installed repository factories use the `gw.observability` entry-point
group. They must implement the public query/record contract and close/context-manager
behavior; the dashboard/exporter do not require a remote backend to use SQLite.

This directory is independently buildable. Run `python -m unittest discover -s
tests -v`. Tests require no model credentials or managed observability account.
SQLite and source files are user-owned, not tamper-proof audit storage. Prompt
capture is opt-in, source previews are bounded, and redaction is best effort—not
DLP or secure erasure. Back up and retain the source stores deliberately.
