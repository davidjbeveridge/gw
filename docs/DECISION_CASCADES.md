# Fast decisions, deliberate escalation

[Handbook](README.md) · [Agent setup](AGENT_INTERFACE.md) · [Decision transport](DECISION_SETUP.md)

A fast model should settle routine judgments. A slower model should be called
when a specific unresolved question justifies it—not as another open-ended agent
watching every action. GW supports that split without changing its decision schema
or giving either model authority over deterministic rules.

## Three strategies

`single` preserves the existing behavior: one configured endpoint decides.

`cascade` calls the primary first. Exact configured labels identify which
questions remain unresolved. One fallback receives those questions and the same
source evidence, without the primary answers as a suggestion. Resolved primary
answers are retained. A failed fallback returns to the existing error policy;
there is no hidden repair loop.

`managed` sends one request to an endpoint/model that performs its own switching
or adaptive reasoning. GW does not second-guess its internal router. It must still
return the supported System One, JSON-chat, or custom HTTP decision contract.

This reproduces the fast-path/escalation *pattern*, not another hybrid model's
training or calibration. No named Glide integration or equivalence in accuracy,
latency, or cost is claimed. Supply a real compatible endpoint and model ID; GW
has no fabricated vendor preset for it.

## Configuration

Ask the agent to configure the strategy using the setup tools. For implementers,
this is a template for a global/global-client `decision` object:

```json
{
  "decision": {
    "provider": "systemone",
    "endpoint": "https://openrouter.ai/api/v1/systemone",
    "model": "typesafe/jev-1.13",
    "key_env": "OPENROUTER_API_KEY",
    "timeout_seconds": 2,
    "strategy": "cascade",
    "fallback": {
      "on_labels": {"*": ["uncertain", "unknown"]},
      "on_error": false,
      "backend": {
        "provider": "openai",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model": "YOUR_REASONING_MODEL",
        "key_env": "OPENROUTER_API_KEY",
        "timeout_seconds": 5,
        "max_output_tokens": 2048,
        "request_options": {"reasoning": {"effort": "low"}}
      }
    }
  }
}
```

Replace model IDs with models available to your account and verify their actual
contract. `on_labels` maps exact goal IDs to exact labels; `*` supplies the default
for other goals. An explicit per-goal list takes precedence over the wildcard.
An empty list disables label escalation for that goal. A goal must offer an
uncertainty label before the primary can select one.

Error escalation is separately opt-in. Refusals/content-filter results do not
trigger a fallback. Authentication problems, malformed results or timeouts can
be configured to escalate, but doing so may add expense without fixing the
underlying problem. The fallback sees no invented missing evidence.

For a model/router that manages its own reasoning:

```json
{
  "decision": {
    "provider": "openai",
    "endpoint": "https://YOUR_GATEWAY/v1/chat/completions",
    "model": "YOUR_ADAPTIVE_MODEL",
    "key_env": "GW_DECISION_API_KEY",
    "timeout_seconds": 5,
    "strategy": "managed",
    "request_options": {"reasoning": {"effort": "low"}}
  }
}
```

The JSON-chat transport permits a small allowlist of request options: `reasoning`,
`reasoning_effort`, `temperature`, `top_p`, `seed`, and `verbosity`. The endpoint
must support the chosen fields. Options cannot override the prompt, credentials,
model, streaming mode, output bound or result schema. Managed System One/custom
HTTP backends can instead switch internally based on their model/configuration;
they do not accept these chat-specific options.

## Bounds and authority

There is at most one primary and one fallback per `decide` invocation. A single
intercept can have separate goal evaluation and worker-model selection decisions;
those invocations are accounted separately. Each transport retains its maximum
five-second timeout, and configuration caps their combined timeout settings at
ten seconds. Socket timeouts are not a strict end-to-end deadline. Slow reasoning
that cannot fit a synchronous native hook should use an explicit review workflow,
not an unbounded timeout hidden in the agent path.

No nested cascades, recursively routed classifier calls, tool calls from the
judge, or automatic worker execution are introduced. Output labels are strictly
validated. A more permissive fallback answer cannot erase a local rule denial,
external authority requirement, or native permission check.

The existing classifier-result cache can reuse a completed decision under the
same policy, task, state and questions. Both backend configuration and compiled
evidence participate in those dependencies. Cache hits do not fabricate new
provider calls or costs.

## Inspect and test

The agent can call `gw_decision_check` for `primary` or `fallback`. Each is one
synthetic contract check, not a live task or an end-to-end cascade benchmark.
Tracing records every actual stage, its trigger, goal IDs, model, latency,
status/error type and reported usage. It does not log private reasoning text.

Test clear cases, legitimate supporting work, uncertainty, missing evidence,
invalid fallback output, timeouts and refusal. Compare task quality and total
cost with the single-stage baseline. Moving work to a cheaper first call is not
enough: false escalations or bad fast-path decisions can make the system worse.

[OpenRouter reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
and [System One](https://docs.typesafe.ai/concepts/system-one) are relevant
transport/design references. Their capabilities are not GW performance results.
