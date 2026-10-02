# Frequently asked questions

[Handbook](README.md) · [Troubleshooting](TROUBLESHOOTING.md) · [Security](../SECURITY.md)

## Is gW an agent, a proxy, or a supervisor?

A supervisor. It evaluates events and returns decisions. Native adapters and the optional LiteLLM callback connect it to execution and inference. The core is not a model gateway, planner, browser driver, or workflow scheduler. A custom application can call the same engine directly.

## Why not put all this in AGENTS.md?

Instructions can help the worker, but they are not external state or deterministic control. A hook can count exact failures and reject a matched action before execution even when the worker would prefer to continue. That does not eliminate useful project instructions; it separates what the model should understand from what the host should enforce.

## Does every decision use Jev?

No. Literal rules, thresholds, registry availability, and priority selection run in code. Active choice goals use the configured decision backend. Jev is supported directly and through compatible services; other decision models or JSON classifiers can implement the contract. The default provider is off.

## Does Jev make the result deterministic or injection-proof?

No such guarantee is made. Typed labels constrain the output format; they do not make the judgment correct. Model updates, context limits, adversarial inputs, and missing evidence can affect decisions. The error path is explicit and configurable. Use deterministic authority and execution checks where correctness cannot depend on a probabilistic label.

## Can I use it without paying for a model?

Yes. The core's rules, retry tracking, repetition candidates, and available-executable recommendations do not need inference. The local knowledge store also does not call a model. Semantic decisions require a configured backend, which can be local or paid. gW does not include model weights, account credits, or a promise that a chosen provider is free.

## Can a small model supervise a frontier model?

It can evaluate a bounded question over supplied evidence. That is not equivalent to being better at the whole task. Keep the classifier's job narrow, allow uncertainty, and measure false interventions. A supervisor that repeatedly blocks a useful path can reduce task quality even while saving tokens.

## Does this reduce model cost?

It is designed to make several kinds of waste controllable, but no gW workload benchmark has established a general savings figure. Classification, process startup, extra approvals, and altered model choices all have costs. Measure total cost per successfully completed task, not just a smaller request or a cheaper selected model. [Benchmark plan](BENCHMARKS.md).

## What does model selection actually execute?

The selection CLI/API returns a typed plan. A compatible model-gateway request can have its proxy alias changed. Native-harness and custom-adapter plans are not automatically launched. With classifier selection enabled, selecting the plan can itself make a classifier call; the selected worker model is not called by `gw models select`.

## Can I mix API models, local models, and subscriptions?

They can coexist as distinct registry entries. Their operation contracts, execution paths, and billing remain distinct. No subscription OAuth extraction or quota-to-API-credit conversion is implemented. Available quota and account access are declarations, not live provider monitoring.

## Is tool choice automatic?

The current executable registry recommends matching installed tools. It does not execute the suggestion or rewrite the worker's tool call. Different adapters deliver advice differently. There is no automatic universal skill/tool-loading manager in this release; that remains deferred.

## Does the supervisor see everything the agent knows?

No. A native event supplies a task, action/result fields, and state metrics. Proxy classification uses a bounded request projection. Hidden reasoning, omitted tool paths, external state, and a full transcript are not magically available. A good question includes an uncertainty option when that evidence is insufficient.

## Why did changing the task not affect my running session?

Sessions pin their task and policy. This avoids silent scope changes during execution, including accidental edits by the worker. Set the new task and begin a new session. A project-level task saved with `gw task` takes precedence over a new native prompt until changed again.

## Does observe mode turn off all enforcement?

No. It softens local blocking decisions into advice and records the would-be decision. External authority denials/failures still block at supported boundaries, and invalid configuration or hook processing can still fail conservatively. It is for studying local policy behavior, not bypassing every control.

## Why does review become denial in my agent?

The adapter does not claim a review UI the host cannot represent. When native approval is supported, gW asks. Otherwise it denies with an explanation so the operator can review and perform the intended action separately. Review must not become automatic approval in an unattended host.

## Can it override a model refusal or vendor policy change?

No. gW does not rewrite refusals, make hidden tool calls, or force a vendor to support a hook. Explicit deterministic executors can make authorized workflows less dependent on model behavior, but the credential/legal-assent executors discussed in the architecture are not shipped. Verify the integration again after vendor updates.

## Is this suitable for enterprise containment?

Not by itself. User-owned config and hooks can be modified or disabled by processes running as the same user. A proxy sees only routed traffic. Hard isolation, workload identity, managed policy distribution, network controls, and receipt verification require real execution-side integrations. The authority protocol is an extension point, not a completed enterprise product.

## Is Warden integrated?

No. The external authority interface leaves room for Warden or another governance system. There is no Warden-specific adapter, policy schema translation, or capability verifier in this release. Unknown constraints from an authority are not treated as satisfied.

## What is the difference between memory and context caching here?

Durable knowledge stores explicit source documents and findings. Indexes make them searchable. The context cache stores prepared evidence packets while their dependencies remain valid. It does not replay old agent responses, share provider KV state, or make supplied evidence consume zero context tokens.

## Does knowledge automatically capture my conversations?

No. Ingestion and writes are explicit. The local reference backend accepts UTF-8 text snapshots and metadata. It does not crawl folders, sync enterprise sources, parse arbitrary PDFs, or automatically summarize every conversation. This avoids silently turning a supervisor into a transcript archive.

## Can another agent reuse the same knowledge?

Yes, when it uses the same authorized tenant/collection/principal. GW defaults to a project-derived collection, which can be shared across clients in that project. Cross-machine use needs a deliberately stable collection mapping and a suitable shared backend. Different scope or access conditions do not share a cached packet.

## Is semantic search included?

The interface supports providers that advertise semantic/hybrid search, but the bundled local backend implements keyword and structured search only. There is an optional embedding component protocol, not an embedded vector engine or automatic embedding-model download. Unsupported modes fail explicitly.

## What does “standard adapter interface” mean?

MCP is the standard agent-facing protocol. `gw.knowledge/1` is this project's versioned, documented backend contract with typed Python interfaces, JSON Schema, an HTTP adapter, and reusable conformance checks. It is not presented as an industry-wide knowledge-store standard. Vendor backends need to implement the contract or supply a bridge.

## Can I extract the knowledge package?

Yes. `packages/gw-knowledge` has its own build metadata, version, license, CLI, schema, docs, and tests. It imports nothing from the supervisor. CI builds and installs it outside the repository. Release assets include its separate wheel/source archive. It has not been implicitly published to PyPI.

## Does the cache stay valid after a source changes?

When the provider's revision contract is implemented correctly. The local token changes on ingestion, new documents, updates, metadata/access changes, expiration, deletion, and reindexing. An original file edited outside the store does not change an explicit snapshot until re-ingested. Unversioned caching is off by default; provider failure never returns stale evidence.

## Does a remembered approval permit the next action?

No. Knowledge is evidence, not authority. A saved approval may explain the past but cannot replace current authorization. Successful tool execution is not proof that a human approved it, and repetition fingerprints are never reusable consent.

## Does three successes automatically produce a tool?

No. It produces a candidate to inspect. Generalizing the workflow, collecting fixtures, generating code, testing it, approving promotion, and retaining rollback are separate future work. The source of truth remains the actual implementation, not the name of a roadmap item.

## Who should skip this project?

Anyone who needs a certified access system, universal agent support without runtime verification, a turnkey autonomous credential broker, or guaranteed savings should use a system that actually provides those properties. If one native hook or a deterministic script solves the job, use that simpler solution. gW earns its place when shared configuration, state, and adapter boundaries help.

## Is a hosted gW account required?

No. The project and independent knowledge package are MIT-licensed, and the local path works without a hosted gW service. Optional third-party providers have their own requirements. Commercial integrations are possible without making them prerequisites for the core.

## Where should I start contributing?

A reproducible native-harness canary, an adapter that passes the common contract, a documentation correction tied to source, or a paired workload measurement is more useful than another unsupported percentage. See [Contributing](../CONTRIBUTING.md).
