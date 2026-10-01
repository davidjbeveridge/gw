# Capability-first inference routing

`gw` selects **any configured model**, not a built-in cheap/medium/frontier enum.
Price tiers can still be user-defined preferences, but they are not model types.

A registry entry separates:

- **Identity:** provider and opaque provider model ID. Multiple entries may name the same model with different execution/billing paths.
- **Contract:** operations, input modalities, output modalities, and optional capability tags. Image understanding does not imply image generation.
- **Execution:** a proxy alias, a native harness, or a custom adapter. Choosing a model does not create an executor.
- **Economics and availability:** billing kind, explicitly unit-labeled prices, operator priority, declared availability/remaining quota, and optional expiry.

## Configuration

Merge `inference` into the existing global `~/.config/gw/config.json`. These are
**templates**, not authenticated account configurations. Replace model IDs and
execution targets, verify capabilities, and only then set `enabled: true`.

```json
{
  "inference": {
    "models": {
      "my-coder": {
        "provider": "openrouter",
        "model": "YOUR_PROVIDER/MODEL_ID",
        "enabled": false,
        "availability": "unknown",
        "operations": ["chat"],
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "capabilities": ["tools", "streaming", "code"],
        "execution": {"kind": "proxy", "target": "my-litellm-coder-alias"},
        "billing": {"kind": "metered"}
      },
      "my-judge": {
        "provider": "typesafe",
        "model": "jev-latest",
        "enabled": false,
        "availability": "unknown",
        "operations": ["decision"],
        "input_modalities": ["text"],
        "output_modalities": ["decisions"],
        "capabilities": ["classification"],
        "execution": {"kind": "adapter", "target": "jev"},
        "billing": {"kind": "metered"}
      },
      "my-chatgpt-plan": {
        "provider": "openai",
        "model": "YOUR_SUBSCRIPTION_MODEL_ID",
        "enabled": false,
        "availability": "unknown",
        "operations": ["code"],
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "capabilities": ["code", "tools"],
        "execution": {"kind": "harness", "target": "codex"},
        "billing": {"kind": "subscription"}
      },
      "my-video-model": {
        "provider": "xai",
        "model": "YOUR_VIDEO_MODEL_ID",
        "enabled": false,
        "availability": "unknown",
        "operations": ["video.generate"],
        "input_modalities": ["text"],
        "output_modalities": ["video"],
        "execution": {"kind": "proxy", "target": "my-litellm-video-alias"},
        "billing": {"kind": "metered"}
      }
    },
    "policy": {
      "strategy": "priority",
      "prefer": ["my-chatgpt-plan", "my-coder"],
      "billing_preference": ["subscription", "local", "metered"],
      "on_unavailable": "approve"
    }
  }
}
```

Claude subscriptions use the same shape with a `harness` execution target of
`claude`. Grok, other hosted providers and local models use whichever configured
proxy/adapter actually supports them. Provider names, model IDs, operations,
modalities and capability tags are open strings. No vendor list or reasoning-tier
hierarchy is built into selection. Do not put keys, OAuth tokens, commands or
endpoints into `execution.target`: it is an **opaque adapter/alias reference**.

Client/project inheritance and `locked` paths apply normally. For example,
`locked: ["inference.models"]` fixes the catalog while allowing project-specific
policy preferences. `locked: ["inference.policy.allow"]` fixes an allowlist.
An empty `allow` list permits no models; an absent one imposes no extra allowlist.
Reviewed project changes and registry edits apply to **new sessions**.

## Selection and execution

```bash
gw models list --project .
gw models select --operation code --input text --output text --capabilities code,tools
gw models select --operation decision --input text --output decisions
gw models select --operation image.generate --input text --output image
gw models select --operation video.generate --input text,image --output video
```

The CLI prints a decision and `inference.plan`, including the selected registry
ID, provider model, operation, execution kind/target and billing metadata. It does
**not invoke the selected model**. Exit status 2 means selection was unavailable,
blocked, or needs approval; malformed configuration exits 1.

`--execution proxy,harness,adapter` limits execution kinds. `--context-tokens N`
requires a declared adequate context window. `--exclude ID1,ID2` excludes failed
or unavailable candidates for this attempt without changing the configuration.
Use a new request ID for each execution attempt; event IDs deduplicate deliveries.

The authenticated HTTP equivalent is `POST /v1/inference/select`:

```json
{
  "context": {"client":"custom", "project":"/existing/project", "session":"workflow-1", "id":"selection-1"},
  "requirements": {
    "operation":"image.generate",
    "input_modalities":["text"],
    "output_modalities":["image"],
    "capabilities":[],
    "execution_kinds":["proxy","adapter"]
  }
}
```

**A plan is not an authorization token.** Enforce the top-level decision and your
native permissions before execution. The external authority receives the selected
`inference_plan`. `InferenceExecutor` defines an extension seam for custom hosts;
this release does not launch native subscription agents or custom executors.

For intercepted proxy requests, gw **does** apply a selected compatible proxy
alias. `/v1/model/request` supports `chat`, `responses`, `anthropic`, `image`,
`video`, `speech`, `transcription`, `embedding`, `rerank` and `decision` formats.
The LiteLLM callback maps supported call types to these contracts. A format name
does not make a provider or a particular LiteLLM release support that operation.
Unknown LiteLLM call types fail explicitly rather than silently escaping supervision.

Image/video/audio/embedding requests retain their native payload fields. Text-only
transforms and token caps are not applied to them. A `chat` request cannot be
rewritten to a harness, classifier or video endpoint. Image generation carried
through chat must explicitly declare both that chat operation and image output.
Opaque provider state (signed reasoning, previous response IDs, conversations)
binds selection to the original execution target; it is not migrated across models.

## How preferences work

Hard filters run first: enabled, availability, expiry/quota, allow/deny/exclude,
operation, input/output modalities, capabilities, execution kind/target and known
context-window requirement. Each excluded model gets an inspectable reason.

`strategy: priority` then sorts by `prefer`, `billing_preference`, ascending
numeric model `priority` (default 100), and stable registry ID. It makes no model
call. A single admissible candidate also needs no classifier call.

`strategy: classifier` sends only admissible candidates to the configured
Jev/HTTP decision provider. Customize `inference.policy.question` to state the
actual selection objective. `max_candidates` (default 32, maximum 128) bounds that
call; preference ordering determines the shortlist, exposed as `considered`.
Invalid choices, outages and abstention do not secretly widen the pool or fall
back to paid generation. `on_unavailable` is `approve` or `deny`.

Optional model fields include `context_window`, `priority`, `quota_remaining`,
and timezone-qualified `available_until`. `availability` must be declared
`available` to participate; absent/unknown/exhausted/unavailable entries are
excluded. This is **declared state**, not a live account/quota monitor or an atomic
spend limiter. Unknown quota is not zero and is not unlimited free capacity.
Prices can be stored under `billing.prices` with explicit units such as
`USD/million_input_tokens`, `USD/image`, or `USD/video_second`. Different units
are never numerically compared by the deterministic priority selector.

Capabilities are operator assertions, not benchmark or provider validation.
Without `context_tokens`, gw does not claim to have counted the request's tokens.
Protocol-specific feature compatibility and quality need workload testing.

## OpenRouter catalog import

```bash
gw models import-openrouter --models 'provider/model-a,typesafe/jev-1.13' > catalog-fragment.json
# Or inspect a previously saved catalog without network access:
gw models import-openrouter --file catalog.json --models 'provider/model-a'
```

Only explicitly named IDs are imported; missing/duplicate IDs fail. Discovery
requests `output_modalities=all`, so decision/media/embedding models are not lost
behind a text-only default. The command prints a fragment and does not overwrite
configuration. Raw pricing and source/time are kept as metadata. Entries remain
**disabled, availability unknown**. Review modalities, endpoint contracts and
account access before merging/enabling them. Nontext output alone does not prove
the wire endpoint, so media entries deliberately require execution configuration.
Gateway aliases/authentication must also be configured in LiteLLM; importing the
catalog does not install those routes or alter native subscription authentication.

To use a registry entry for the supervisor's own classifier, set global
`decision.model_ref` to an enabled, available `decision` model whose adapter target
matches `decision.provider`: `systemone`, `openai`, `http`, or legacy `jev`. Endpoints/keys remain in the global
`decision` configuration. This is a pinned direct invocation, not recursive model
routing. The Jev System One-compatible endpoint can be TypeSafe's or OpenRouter's;
use the provider's matching model ID and API key environment variable.

## Subscription boundaries and references

Subscription-backed execution stays in its authorized native client/adapter.
No subscription OAuth tokens are extracted or forwarded into the proxy; no
ChatGPT, Claude or Grok plan is assumed to include general API billing. A catalog
entry is not proof that a model is available on a particular plan.

Primary contracts checked October 1, 2026:

- OpenRouter model catalog and nontext discovery: https://openrouter.ai/docs/guides/overview/models
- OpenRouter schema: https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties
- Jev endpoints: https://openrouter.ai/docs/guides/community/jev
- Image contracts: https://openrouter.ai/docs/guides/overview/multimodal/image-generation
- Codex authentication: https://developers.openai.com/codex/auth/
- Claude authentication: https://code.claude.com/docs/en/authentication
- xAI media APIs: https://docs.x.ai/developers/model-capabilities/imagine
- LiteLLM callbacks: https://docs.litellm.ai/docs/proxy/call_hooks

For core classifier onboarding, use [Decision setup](DECISION_SETUP.md). The `gw models` registry alone does not configure its transport or credentials.
