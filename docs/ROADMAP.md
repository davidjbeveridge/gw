# Roadmap

[Handbook](README.md) · [Current capabilities](../README.md#what-it-does-today) · [Benchmark plan](BENCHMARKS.md)

This page describes direction, not a release promise. A named interface or documented idea is not a shipped integration. Current behavior belongs in the reference pages and tests.

## Shipped foundation

The core has a shared decision engine, literal rules, typed decision backends, client/project policy inheritance, reviewed snapshots, pinned tasks, exact retry/repetition tracking, and cumulative alignment state. Six native adapter families, a generic API, and an optional LiteLLM callback expose that engine at different boundaries.

The model registry is capability-first. Compatible proxy aliases can be applied; native-harness and custom-adapter plans are selected without being automatically launched. Decision-backend setup supports direct/routed System One, local compatible services, JSON chat, and explicit custom bridges.

The optional independent `gw-knowledge` package supplies a versioned adapter contract, local SQLite/FTS5 storage, keyword/structured search, source revisions, dependency-aware context caching, HTTP access, and optional MCP transport. Ingestion is explicit; automated capture and prompt injection are not part of that release.

The handbook, API references, source-linked examples, and documentation checks describe this foundation. Package releases and documentation changes are separate; a docs update does not move a released tag.

## Next: prove usefulness in real workflows

A runtime conformance runner should record tested agent/OS versions and verify actual tool denial, advice delivery, failure reporting, and timeout behavior. OpenCode v2 requires its own verified adapter rather than a compatibility claim by association.

Paired workload evaluations should measure task success, total cost, latency, review burden, classifier overhead, and stale-context errors. [The benchmark protocol](BENCHMARKS.md) defines the evidence. There is no published savings number to preserve; an experiment that shows a feature is not worthwhile is useful.

Live model-route evaluation needs real endpoint compatibility, measured quality, accurate input requirements, and explicit quota/budget handling. Declared availability is not a live account monitor. Subscription/media executors remain separate from selection.

## Next: improve state without accumulating another transcript

Better request-to-session binding and explicit parent/subagent lineage would make concurrent work easier to interpret. Bounded progress evidence could improve decisions that currently see only a task, event, and aggregate metrics.

Any extra retention should be opt-in and purpose-specific. More stored text is not automatically better memory; it also creates exposure, deletion, and indexing work. The existing event log should not quietly become a full conversation archive.

## Knowledge extensions

Candidate adapters include self-hosted hybrid/vector retrieval engines and managed knowledge services. They should implement the same read contract, advertise unsupported features honestly, and pass access/invalidation tests. No commercial-first dependency is required.

Source synchronization, parsers, embeddings, retrieval ranking, and generated summaries should remain replaceable components. Local keyword retrieval stays useful without downloading a model. A future automatic context-injection feature needs an explicit host boundary and a freshness/quality evaluation; it is not implied by having a cache.

## Learning and deterministic tools

The next learning slice should retain consented fixtures and group repeated workflows semantically, rather than only counting exact action fingerprints. A bounded synthesis job can then propose a script or workflow.

Promotion requires deterministic tests, replay/shadow comparison, operator or policy approval, an immutable registered version, and rollback. Start project-local before considering cross-project promotion. Successful repetition must never silently widen authorization.

No self-editing production policy, automatic generated-tool installation, or reinforcement-learning claim is made by the current candidate recorder.

## Governance and execution

A Warden-specific adapter, workload identity, OS-managed policy, narrow capabilities, credential injection, origin-bound browser actions, and explicit legal-assent workflows all need real execution-side implementations. The generic authority/credential interfaces leave room for that work; they do not perform it.

## Deliberately deferred

Universal skill/tool loading and aggressive transcript optimization remain deferred. Their value and failure modes depend on the harness and model, especially with small local models. Any future work should preserve model-directed discovery and required instructions rather than optimizing context size in isolation.

A new orchestration framework, hosted control plane, and commercial distribution are not prerequisites for the next useful improvement. Keep the local open-source path complete enough to demonstrate the engineering on its own.
