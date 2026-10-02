# Observe a run, then decide whether GW helped

[Handbook](README.md) · [Plugin interfaces](PLUGINS.md) · [Learning](LEARNING.md) · [Sync](SYNC.md)

GW 0.5 adds optional, free local observability. It records decisions and measured
operations without calling a model. It does **not** claim that issuing a denial
prevented drift, or that a lower bill proves the task was completed correctly.

## Install and open

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.5.0/install.sh | bash -s -- --all --plugins
gw trace init
gw trace serve --open
```

Restart agents after updating hooks and start new sessions after enabling tracing.
The default dashboard is on IPv4 loopback port 7789. Its data API requires the
private `dashboard-token` under `$GW_HOME/observability`. `--open` passes this in
a browser fragment, then removes the fragment; it is not sent as an HTTP query.
The dashboard is read-only, has no CDN assets, and makes no inference requests.

The core remains usable without any optional package. Install `--knowledge`
separately when using the knowledge integration. `--plugins` installs independent
`gw-observe`, `gw-learning`, and `gw-sync` packages, but does not enable learning,
launch a research worker, connect a cloud, or synchronize files automatically.

## Record the baseline before changing the harness

```bash
gw trace init --baseline
gw trace start --name "Login repair / baseline" --harness codex \
  --harness-version YOUR_VERSION --model YOUR_MODEL \
  --prompt-file task.md --bind
```

`task.md` must exist. Keep the returned run ID. Baseline mode records intercepts
but does not evaluate GW rules/goals, call the classifier, route models, or alter
proxy payloads. Native permissions still apply. Configuring external authority
with baseline is rejected: this mode must not silently bypass an existing
required authority. It is different from `mode: observe`, which evaluates policy
and can spend classifier tokens while softening local blocking decisions.

Run the task in a **fresh native agent session**. Then explicitly record the end:

```bash
gw trace finish RUN_ID --outcome succeeded --evidence "Regression tests passed; diff reviewed"
```

That outcome is an operator assertion, not an automatic quality judgment. The
elapsed time includes pauses between explicit start and finish. A live run has
unknown completion time; the observed event span is reported separately.

To compare another configuration, restore the workspace yourself, configure GW,
and repeat with a new run and agent session:

```bash
gw trace init --mode enforce
# Configure the intended goals/backends and prepare the same starting workspace.
gw trace start --name "Login repair / supervised" --harness codex \
  --harness-version YOUR_VERSION --model YOUR_MODEL --prompt-file task.md --bind
# Run the task, then finish its new run ID.
gw trace compare BASELINE_ID SUPERVISED_ID
```

There is no benchmark scheduler, code reset, replay, or automated evaluator here.
Comparing different harnesses/models is allowed; the comparison lists changed
variables rather than calling the change an isolated GW effect.

`--bind` associates new native sessions in this project with the run. Use a
client-specific binding when needed, or export `GW_RUN_ID` into an explicitly
scoped process. An existing session remains assigned to its original run. Do not
reuse a native session across experiments and expect its earlier context to vanish.
Without an explicit run, observed sessions get automatically created run records
with clearly marked partial metadata.

## What a run captures

A manifest contains declared harness/version/model, mode, OS/runtime, policy
snapshot, prompt hash/reference, and a read-only Git fingerprint. Finishing stores
another workspace fingerprint. GW never resets, commits, or copies the source diff.
Untracked-file contents are **not** captured by the Git fingerprint. Use a clean,
controlled starting workspace for meaningful comparisons.

Prompt text stays in the supplied file unless `--capture-prompt` explicitly saves
a redacted snapshot. Policy snapshots are content-addressed and reused. Run
manifests are immutable; later observed model/policy identities remain visible in
the trace rather than silently changing the declared starting variables.

## Ask the agent, not just the dashboard

All views have deterministic JSON commands:

```bash
gw trace runs
gw trace show latest
gw trace timeline RUN_ID --limit 100
gw trace event EVENT_ID --source
gw trace compare RUN_A RUN_B
gw trace outcome --run RUN_ID --goal tests_pass --value met --evidence "test-report:run-17"
```

`show` provides aggregates, coverage, configuration and metadata. `timeline` is
paginated. `event --source` resolves a registered original on demand. `outcome`
records an explicit goal annotation with its evidence reference. Generic hosts
can submit a bounded `gw.observation/1` JSON envelope with `gw trace record FILE`.
Annotations are not automatically verified or converted into permissions.

## Proposal, intervention, execution, outcome

These are separate facts:

1. The host exposed a proposed operation.
2. GW evaluated or skipped specific goals and issued a verdict.
3. The adapter translated that verdict into a native response.
4. The host may emit execution/outcome evidence afterward.
5. The overall task has an independently supplied outcome.

A native hook's return does not prove that the host consumed it. The trace labels
this uncertainty. A later tool-result observation matching a denied call is a
contradiction worth inspecting, not something to hide in a “prevented” counter.
Per-goal data includes disabled/not-applicable/no-task/unavailable states, labels,
thresholds, and effects. Observation mode preserves the distinction between a
would-be intervention and the final advisory response.

The alignment chart shows recorded classifier judgments. Baseline mode has no
alignment curve because recording one would require the classifier work that the
baseline intentionally omitted. Markers link to the actual event; they are not
counterfactual savings estimates. Goals without a measured outcome remain
unmeasured. No extra classifier is run to make a dashboard look complete.

## Tokens, turns, costs, and mechanisms

| Measurement | Source and boundary |
|---|---|
| User/model turns | Observed prompt/model-request events or recognized imported assistant turns; hidden iterations remain unknown |
| Input/output tokens | Reported usage, not character-count estimates |
| Cache/reasoning tokens | Subsets displayed separately, never added twice to input/output totals |
| Cost | Explicit gateway/provider-reported USD; subscription allocation and local electricity remain unknown |
| Evaluation time | Measured GW evaluation duration, including decision-provider waits |
| Logging time | Aggregate trace-recording overhead; not an assertion of zero CPU/storage cost |
| Tools | Explicit host classification or labeled name-based hints; MCP transport and browser behavior are not assumed identical |
| Skills/subagents/task types | Explicit exposed IDs, parent links, and declared categories; omitted fields remain unknown |
| Context | Reported per-role/schema character sizes and exact knowledge provenance edges; not a full hidden context reconstruction |

The overview separates worker usage from the supervisor's classifier usage.
Classifier cache hits are not charged as new classifier calls. Unknown costs stay
null, not zero. A requested model and the model reported in a completion can differ;
inspect the trace and per-model usage table rather than only the manifest.

## Use existing native session files

Native hooks often do not include token usage or the full proposed payload.
Explicitly index the corresponding original transcript:

```bash
gw trace import /absolute/claude-session.jsonl --run RUN_ID --format claude-jsonl
gw trace import /absolute/codex-session.jsonl --run RUN_ID --format codex-jsonl
```

Use `--session NATIVE_ID` only when the file lacks the correct native session ID.
Index the intended session, not an unrelated multi-task history. Events outside
the declared run time window are flagged. Schemas vary across native releases;
imports report invalid/unsupported records and do not claim universal coverage.

Claude message IDs coalesce repeated streaming records. Codex cumulative counters
are converted to increments; repeated totals are not billed repeatedly, and
counter decreases are flagged. When proxy and imported usage overlap in one
session, one explicitly reported source lane wins; potentially duplicate lanes
are not summed. This is conservative and can undercount partial overlapping
sources. The report exposes the choice instead of inventing an exact merge.

No full transcript is copied. The index retains file ID, byte range, record hash,
identities and normalized measurements. Raw details are read only through a
registered source locator. Modified or deleted originals produce an explicit
source status, never fabricated content. Exact tool IDs link core verdicts to
recognized imported tool records. Unlinked calls remain visibly incomplete.

## Storage and failure policy

The existing GW SQLite ledger remains the owner of full decision/audit records.
The observation database owns run manifests, compact derived measurements, and
source references. Learning proposals and reports stay in the learning database;
sync manifests/journals stay with sync; knowledge text stays in its provider.
Compact goal indexes survive loss of the richer GW source, but the original
proposal cannot be reconstructed if neither preview nor original source exists.

`--preview-chars N` (0 by default, maximum 2000) opts into short best-effort-redacted
input previews. Redaction is not complete DLP. Do not put secrets in labels,
metadata, filenames, or prompts merely because an observer has a redactor.

SQLite WAL and run/time/session indexes support concurrent local hooks. Queries
iterate run records; timelines are paginated, chart points are sampled for display,
and the dashboard pauses polling when hidden or inspecting details. This is not
a published large-corpus throughput benchmark. History retention is operator-
managed; there is no automatic transcript duplication, deletion, or compaction.
Do not place live SQLite WAL databases on an arbitrary network filesystem.

Logging failure does not change the action verdict. The engine reports
`observability_error` or a bounded component warning; a missing observation is a
coverage gap. Crash-safe atomic delivery between the core ledger and an arbitrary
external sink is not claimed. For regulated audit retention, supply a durable
managed sink and explicit delivery policy rather than treating this local index
as a tamper-proof log.

## Existing observability stacks

```bash
gw trace export-otlp RUN_ID --output trace.json
gw trace export-otlp RUN_ID --endpoint https://collector.example/v1/traces --key-env OTLP_TOKEN
```

Export uses **OpenTelemetry OTLP/HTTP JSON**, GenAI usage attributes where
applicable, and `gw.*` attributes for goals and interventions. No full prompts,
responses, source text, or credentials are included. Export is explicit, not an
automatic remote upload. Collector partial rejection is not reported as success.

This is the interoperability path for MLflow, Phoenix, or another compatible
collector. GW adds local policy/context/learning views rather than replacing an
entire observability platform. These releases test the wire contract and local
receiver, not every third-party deployment or dashboard mapping.

References: [OTLP](https://opentelemetry.io/docs/specs/otlp/),
[GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/),
[MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/),
[Phoenix](https://arize.com/docs/phoenix/).
