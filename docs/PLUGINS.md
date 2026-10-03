# Plugin boundaries and local implementations

[Handbook](README.md) · [Observe](OBSERVABILITY.md) · [Learning](LEARNING.md) · [Sync](SYNC.md)

GW's core is MIT-licensed and retains no mandatory plugin dependency. The free
reference implementations are independent distributions in this repository, with
their own versions, licenses, CLIs, tests and build metadata. They import no
`gw_supervisor` code. Copying a package directory out of the repository must remain
a supported build. Commercial/cloud alternatives can implement the same boundary
without making the local workflow depend on them.

## Configuration

```json
{
  "plugins": {
    "observe": {"enabled": false, "provider": "local", "options": {}, "preview_chars": 0},
    "learning": {"enabled": false, "provider": "local", "options": {}},
    "sync": {"enabled": false, "provider": "local", "options": {}}
  }
}
```

Settings are global/global-client and support normal locks. Agent-writable project
files cannot choose Python plugins or redirect trace/sync data. `gw plugins`
reports installed distributions and configured state. `options.directory` changes
the local component state path. Learning's detailed policy lives in its own
versioned configuration, not in a growing list of hardcoded supervisor goals.

## Interfaces

| Boundary | Contract | Reference implementation |
|---|---|---|
| Observation production | `ObservationSink.record(envelope)` | Metadata-only SQLite index |
| Run/query storage | `TraceRepository` start/finish/bind/record/runs/report/timeline/event/compare | `gw-observe`; replacement factories under `gw.observability` |
| Trace export | Standard OTLP/HTTP JSON | Explicit exporter and collector receipt validation |
| Learning analysis | name/version + `propose(context, settings)` | Tool optimization, skill guidance, explicit-topic research; `gw.learning.plugins` |
| Learning execution | `gw.learning/1` stdin request → JSON report | Bounded operator-configured subprocess, no implicit model credentials |
| Harness bundle storage | `BundleProvider` put/get blob, publish CAS channel, resolve | Local content-addressed store and HTTP adapter; `gw.sync.providers` |
| Knowledge | Existing `KnowledgeProvider` capability/revision/search/read | Independent `gw-knowledge` local/HTTP/MCP implementation |
| Decisions/authority/inference | Existing protocols | Unchanged execution and permission boundaries |

OpenTelemetry and MCP are external standards. The `gw.*` backend envelopes are
project-defined, versioned open contracts, not a claim that an industry-wide
learning or harness-sync API exists. Unknown modes and incompatible payloads must
fail explicitly.

## Observation envelope

```json
{
  "protocol": "gw.observation/1",
  "id": "stable-observation-id",
  "run_id": "existing-run-id",
  "session_id": "optional-native-session-binding",
  "parent_id": null,
  "kind": "goal.outcome",
  "start_ns": 1,
  "end_ns": 2,
  "attributes": {"goal_id": "tests_pass", "value": "met", "basis": "host_reported"},
  "source": {"source_id": "registered-report", "offset": 0, "length": 100, "hash": "record-hash"}
}
```

Nanoseconds are Unix timestamps. IDs deduplicate the same observation, not new
work that happens to look similar. Metadata is limited to 32 KiB; original
payloads belong to their source owner. A custom sink must not issue LLM requests
merely to record or display an event. A cloud exporter should preserve coverage,
provenance and unknown measurements rather than populating invented defaults.

The local dashboard reads the repository interface. Native transcript indexing
is a local-store capability, not a requirement that every remote repository have
a filesystem or expose SQLite. The exporter uses public timeline operations.
Factories are trusted installed code and need context-manager/close behavior.

## Learning and sync contracts

Learning input contains bounded evidence metadata and explicit strategy/config.
A proposal names a stable key, kind (`guidance`, `tool_plan`, `research_job`), title,
body, evidence references and goal IDs. Changes to live permissions are not a
permitted observer side effect. Default plugins make no model calls; worker usage
is a separate opt-in workload and must be accounted independently.

Sync manifests contain protocol plus files with portable relative path, SHA-256,
size and executable bit. A channel update is compare-and-swap. The client verifies
content before applying a reviewed plan, regardless of provider. Portable manifests
are not signed authority tokens, and applying a bundle does not activate it.

## What should not become another plugin framework

The lifecycle/event normalizer, policy inheritance, native verdict translation,
idempotency and basic permission precedence stay in core. They are not dynamically
replaced by an untrusted worktree. Heavy retrieval, trace storage, learning jobs,
media/native inference executors and distribution belong behind narrow interfaces.
There is no general “run arbitrary plugin code on every token” extension point.

The observability and knowledge paths are read/record-oriented. Learning execution
and sync application are explicitly mutating operations with their own review,
limits and journals. Keeping those roles distinct avoids giving a charting plugin
permission to rewrite the harness it observes.

## Provider-independent context (0.7)

`gw-context` defines `ContextCompiler` and `ContextSource` without requiring a
knowledge backend. Named source factories use `gw_context.sources`. The GW host
loads only globally configured sources and delivers the compiled packet; the pure
compiler performs no provider discovery. See [Context compiler](CONTEXT_COMPILER.md).
