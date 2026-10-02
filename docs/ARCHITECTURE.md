# Architecture and method

[Handbook](README.md) · [Configuration](CONFIGURATION.md) · [API](API.md) · [Security](../SECURITY.md)

An agent supervisor should be easier to understand than the workflow it supervises. gW therefore does not run a second open-ended agent loop. It accepts an event, evaluates configured decisions, records the result, and returns control to the host.

The working hypothesis is that recurring judgments can often be made with less machinery than task execution itself. That hypothesis motivates the design; it is not yet a measured claim about gW's effect on real workloads. [Benchmark design](BENCHMARKS.md) explains how to test it.

## Four responsibilities

**The worker** plans and performs the user's task. It may be a frontier model, a local model, a browser agent, or another program. gW does not replace its reasoning with a universal classifier.

**The supervisor** decides what to recommend or permit at the integration points it receives. Exact rules run in code. Configured choice questions go to a decision provider. Model selection operates over an explicit registry.

**The executor** owns the actual action. It must honor a returned denial or pause for review. Native permissions still apply after gW has no objection. A JSON verdict is not an operating-system capability.

**The knowledge provider** stores and retrieves source evidence. It does not decide permissions, rewrite policy, or turn an old approval into a current one. It is a separate package because useful knowledge access should not require this supervisor.

These responsibilities can share a process without sharing authority.

## Deployment without a new orchestrator

```text
native command hook                 LiteLLM callback
        |                                  |
        +---------- gW Python engine ------+
                            |
                 configuration + SQLite
                            |
           optional decision / authority endpoints

custom host ---- authenticated loopback API ---- same engine

agent or host ---- knowledge CLI / MCP / API ---- independent provider + cache
```

A native hook starts a short-lived Python process. The LiteLLM callback uses the library in the gateway process and moves blocking work into a thread. Both use the same state location. The optional `gw serve` process exposes HTTP endpoints; normal hooks do not need it.

This keeps the minimum install small and makes failure modes visible. It also means every native hook pays process-startup and local-state overhead. Network classification adds its own latency. The project does not label those costs negligible without measurement.

LiteLLM owns provider connectivity. Caveman, when configured, owns its own compression and recovery. gW adds decisions around those systems rather than duplicating them. [Proxy integration](PROXY.md) describes the boundaries.

## The event path

The implementation in [engine.py](../gw_supervisor/engine.py) follows this sequence:

1. Validate the event, normalize the project root, and resolve configuration.
2. Find or create the session, which pins its effective policy and task. Return an existing result for a duplicated event delivery.
3. Read prior metrics and apply matching deterministic rules and goal primitives.
4. Batch active choice goals into a bounded classifier request when a backend is enabled and the required task is available.
5. For inference events, select among compatible configured models unless the local decision already blocks selection.
6. Apply observation mode, then consult the optional external authority at supported pre-action boundaries.
7. Convert impossible post-action blocking into advice, record the event and state changes, and return the verdict.

The host translates that verdict into its native behavior. The engine itself does not execute the proposed command, browse the page, launch a selected subscription agent, or run an automation candidate.

### Deterministic does not mean complete

A literal policy can reliably match `input.command == "echo GW_CANARY_DENY"`. It cannot reliably identify every possible spelling or indirect invocation of a deployment command. Text rules are useful workflow controls, not shell analysis or process isolation.

Likewise, retry counts are exact state, but the definition of “same action” is an exact fingerprint after redaction. Changing an argument can produce a different fingerprint. Two actions whose only difference was a redacted secret may share one. Neither property grants reusable consent.

### Structured does not mean infallible

TypeSafe's [System One interface](https://docs.typesafe.ai/concepts/system-one) supplies typed answers rather than open-ended prose. gW currently consumes Choice labels. That makes control flow and validation straightforward; it does not make a bad classification impossible or establish calibrated authorization confidence.

The decision interface also supports a JSON-generating chat model and a custom HTTP classifier. They must return valid labels for the configured questions. Invalid, truncated, refused, or unavailable responses take the configured error path. There is no hidden frontier-model repair loop.

The model judges the state it receives: pinned task, redacted current event, and bounded metrics. It does not receive a complete transcript by default. For proxied model requests, the projection includes a bounded latest-user excerpt, not the full model input. A question requiring unseen test history cannot be answered reliably by making the rubric more emphatic.

## Goals are policy; evaluators are mechanisms

The supplied goals express task alignment, research-first advice, tool preference, retry limits, cumulative drift, and repeated-work detection. Their IDs are ordinary configuration keys.

The current evaluator set is intentionally smaller:

| Mechanism | What it evaluates |
|---|---|
| `choice` | A configured natural-language question over named choices |
| `metric` | A threshold over an available state metric |
| `repetition` | Repeated successful post-action observations |
| `registry` | Matching registered executables available to this process |

A new choice goal needs configuration, not a new class. A fundamentally new evaluator still needs implementation and tests. There is no arbitrary policy-code execution language hidden in the JSON file.

The [configuration reference](CONFIGURATION.md) states what each primitive actually knows. This is important for efficiency: adding another question is easy, but every unnecessary classification can become overhead.

## Session state and cumulative drift

Session identity is the combination of client, canonical project path, and native session ID. The original task and effective policy are saved when the session starts. An explicit project task takes precedence over the first native prompt. Subsequent prompts do not silently change the assignment.

Alignment labels map to configured numbers. With the supplied defaults, direct work maps to 0, supporting work to 0.15, uncertain to 0.4, off-task to 0.8, and conflicting to 1. The first observation initializes the drift value. Later observations update it:

```text
next_drift = 0.7 * previous_drift + 0.3 * alignment_observation
```

A metric goal can require review after a threshold and minimum observation count. It reads the previously recorded state, so a crossing affects a subsequent event rather than retroactively preventing the action that produced the observation. Responses also report the metrics seen before that event's update.

This is a cumulative alignment signal, not a complete progress model. It does not measure code quality, actual task completion, semantic approach churn, or all forms of looping. No pinned task means task-dependent tool classifications abstain; no enabled provider means semantic goals are disabled. Neither condition is a successful alignment judgment.

## Model selection is separate from supervision

The worker registry answers “which configured capability can satisfy this request?” The supervisor's decision backend answers a different question: “which label fits this bounded state?” Configuring one does not configure the other.

Hard filters run before a model-selection classifier sees candidates. They include operation, input and output modalities, required features, enabled/available status, policy exclusions, and execution compatibility. A priority strategy can select without calling a model at all. A classifier strategy receives only the admissible shortlist and may abstain.

The plan separates a provider's model ID from its execution target. A proxy alias can be applied to a compatible request. A native harness or custom adapter needs an executor; selection alone does not launch it. Provider-specific opaque state binds a request to the existing route rather than being silently migrated.

This is why a media generator, a classifier, and a subscription-backed coding agent can share a registry without being interchangeable. [Model reference](MODELS.md).

## Knowledge and context reuse

`gw-knowledge` separates durable documents, derived indexes, and disposable evidence packets. Its four required adapter operations are capability discovery, scope revision, search, and exact read. Cloud and local implementations use the same contract; unsupported search modes remain unsupported.

A cached packet is reusable only under its recorded scope, provider/index identity, query, evidence budget, and freshness conditions. The local revision changes for additions as well as modifications and deletions. Otherwise an old empty search could stay “correct” forever while newly relevant documents accumulate.

The package does not automatically summarize conversations or inject text into requests. The caller chooses when to retrieve and where to present the result. A retrieved instruction remains source content, not a higher-trust instruction. [Knowledge guide](KNOWLEDGE.md).

## What learning means in this release

A repeated success can create a candidate record. That is an observation: “this happened often enough to inspect.” It is not proof that the sequence should become a tool or that future executions are authorized.

The intended next step is a separate, bounded pipeline: collect consented fixtures, propose an implementation, test it, compare behavior, approve it, then register an immutable version with rollback. That pipeline is not shipped. Neither are automatic policy edits or model fine-tuning. The distinction keeps a learning experiment from quietly becoming a new permission system.

## Failure boundaries

gW's own pre-tool wrapper tries to produce a native denial when it can handle invalid input or an internal failure. It cannot guarantee denial if the host never invokes the hook, kills it on timeout, or ignores its response. Vendor hook semantics are part of the execution boundary, not an implementation detail we can abstract away.

Observation mode softens local blocking verdicts into advice; external authority denials still apply. Classifier error policy is per goal, and defaults favor advice. Returned authority constraints that the executor cannot enforce are denied rather than treated as implemented.

The knowledge cache has a different failure policy: an unavailable provider does not justify returning stale evidence. API error paths and classifier error paths should not be conflated. See [Security](../SECURITY.md) and [Troubleshooting](TROUBLESHOOTING.md).

## Why the core stays small

The project reuses native hooks, an existing model gateway, and conventional storage. It keeps provider code behind interfaces and optional knowledge code outside the core distribution. It does not add a workflow framework merely because workflows may eventually consume it.

The resulting trade-off is deliberate: some integrations are explicit rather than automatic, and some capabilities stop at a tested contract. That makes it possible to inspect exactly what is running today. [References](REFERENCES.md) explains the upstream ideas; [Roadmap](ROADMAP.md) keeps the unimplemented ones visible.
