# Configuration and decisions

## Files and precedence

`GW_HOME` defaults to `~/.config/gw`. It contains `config.json`, `state.sqlite3`, private API token, project snapshots and settings backups. The install location is separate (`~/.local/share/gw` by default).

Resolution order: built-in defaults → global file (excluding clients) → global `clients[client]` → trusted project snapshot (excluding clients) → project `clients[client]`. Dictionaries merge; other values replace; goal and rule IDs remain stable. `locked` is additive and lists immutable dotted paths. The resolved policy is pinned at session creation. New global/project settings affect new sessions only.

Project `.gw.json` is inert until `gw trust --project PATH`. Do not place provider/authority configuration in a project: those are global-only. Changes to a reviewed worktree file are reported without changing the trusted copy. Malformed configuration is an error, not a silent reset to permissive defaults.

To require the classifier for alignment, set `goals.task_alignment.on_error` to `approve` or `deny`. Default `advise` favors usability while clearly reporting unavailable semantic scoring. Provider `off` intentionally disables all semantic goals; it is not a classification success. No pinned task means task-specific checks abstain. Set the task before starting a session.

## Custom goal

Goals are configuration, evaluated by small implementation primitives. A custom classifier goal does not require a new Python class:

```json
{
  "goals": {
    "test_before_finish": {
      "on": ["tool.before"],
      "evaluator": "choice",
      "question": "Is the agent proposing to commit changes without enough test evidence in the supplied context? Do not guess about evidence that is absent.",
      "choices": {
        "ready": "Sufficient evidence or not a commit",
        "uncertain": "Evidence is absent or ambiguous",
        "missing": "Clearly missing required validation"
      },
      "effects": {"uncertain": "advise", "missing": "approve"},
      "on_error": "advise"
    }
  }
}
```

This example is a judgment about supplied evidence, not a guarantee that gw has collected a full test history. A deterministic CI/commit check is stronger when available.

Supported evaluators:

| Evaluator | Configuration | Behavior |
|---|---|---|
| `choice` | question, choices, effects, on_error | Batched typed decision questions |
| `metric` | metric, threshold, optional min_observations, effect | Deterministic threshold over failures, successes, drift, observations |
| `repetition` | threshold | On successful post-action events, propose automation at N exact repetitions |
| `registry` | preference | Match installed registered executables; recommend, never secretly execute |

Effects: `allow`, `advise`, `approve`, `deny`. Most restrictive wins. Native adapters decide which effects they can represent; unsupported review fails closed. Post-action decisions are advisory because execution already happened.

Supported event types: `session.start`, `tool.before`, `tool.after`, `model.request`, `model.response`, `inference.select`. The normalized event is version 1. To add a new kind of side effect, send semantic fields such as `operation`, `target.origin`, and opaque `credential_ref` through the generic API. Rules can match dotted event paths. Native browser coordinates without semantic targets do not give the supervisor enough evidence to authorize an action.

## Model routing

Use the general `inference.models` registry and `inference.policy`, described in
[Model registry and routing](MODELS.md). There are no fixed model tiers.
Operations, input/output modalities, capabilities, execution and billing are
independent fields. Global/client/project inheritance and locks apply.

The v0.1 `proxy.models` plus choice-goal `route` mapping remains compatible for
existing text-proxy configurations. It is only used when the new inference
registry is empty. It is not a way to execute classifiers, media endpoints or
subscription harnesses. Disable obsolete tier-selection goals after migrating
to avoid spending classification calls on unused routes.

## Proxy configuration

`compact_tool_json`: whitespace-only lexical JSON minification for tool-result text, default false. It preserves numeric spelling and strings, rejects duplicate-key/non-finite JSON, and leaves prose/logs/code alone. It never minifies function-call arguments or tool schemas.

`inject_task`: add the pinned task once in a protocol-appropriate instruction location. Do not inject tool-output instructions into high-trust roles. The injected task is stable during the session to reduce unnecessary cache-prefix churn.

`max_output_tokens`: zero disables the cap; a positive integer caps the protocol's output budget. A cap can truncate useful work. It is not a cost/quality guarantee.

`block_detected_secrets`: heuristic request screening, default false. This is not complete DLP. Keep secrets out of model traffic rather than relying on regexes.

The response path audits usage and preserves the response. Arbitrary response rewriting, lossy transcript compression, cache-based answer reuse, and signed-thinking manipulation are intentionally absent.

## Telemetry and learning

A session is keyed by client, canonical project root and native session ID. Event IDs deduplicate retried delivery. Tool action fingerprints use the normalized, redacted tool name and arguments. Repetition is therefore exact after redaction, not a proof of semantic equivalence. A successful action is not proof that a human approved it.

Failure count tracks consecutive failures of the same action in a session, reset by a success/unknown outcome. The drift EWMA is `0.7 * previous + 0.3 * observation`, with the first observation used directly. Only real classifier alignment observations advance this measure. An inbound warning is not a fabricated zero-drift observation.

At three successful repeats, a candidate record is proposed. No source code is generated, no tools are registered, no cross-project capabilities are silently promoted. A later synthesis pipeline should collect consented fixtures, generate a candidate, test it in isolation, shadow/replay, promote a reviewed immutable version and keep rollback. See ROADMAP.md.
