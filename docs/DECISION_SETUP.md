# Set up the supervisor's decision model

`gw setup` configures the **core classifier used by the supervisor**. This is
separate from `gw models`, which configures worker-model selection. Changing a
worker's model or adding it to OpenRouter does not automatically configure the
supervisor's classifier. No setup command changes your agent's login or billing.

## Quick paths

After installing gw, run the interactive guide:

```bash
gw setup
```

Or configure it noninteractively. Provision the indicated API key in the process
environment first; do not paste keys into chat, command-line arguments or Git.

```bash
# Jev through OpenRouter; OPENROUTER_API_KEY must be available.
gw setup --preset openrouter --check --yes

# Jev directly through TypeSafe; TYPESAFE_API_KEY must be available.
gw setup --preset typesafe --check --yes

# Existing, warm local servers. These two presets send no credentials.
gw setup --preset kev --check --yes
gw setup --preset laya --check --yes
```

`--check` sends **one synthetic request containing two choice questions** before
saving. It may incur provider charges, but it sends no project/task/transcript
data. It checks authentication, request/response compatibility, two expected
labels and warm latency. It is **not** a model-quality or security evaluation.
A failed check exits 2 and leaves the existing configuration unchanged. Without
`--check`, setup makes no network call and reports the configuration as untested.

Use `--dry-run` instead of `--yes` to preview; adding `--check` to a dry run still
makes the explicitly requested synthetic call. Existing config is backed up on
apply. The runtime config is written atomically; do not run concurrent config
editors. No models, GPU packages or background services are installed.

After setup, start **new agent sessions**. Existing sessions keep pinned policy.

```bash
gw decision status --client codex --project /path/to/project
gw decision check --client codex --project /path/to/project
gw doctor --project /path/to/project
```

Run the check in the **same environment as the agent**. A successful check in one
terminal does not prove a GUI-launched app received that terminal's environment.
Then verify the README's native deny canary inside each agent. A working model
endpoint does not prove the agent loaded its hooks.

## Choose a wire protocol, not just a brand

| Preset | Wire format | Defaults / requirements |
|---|---|---|
| `typesafe` | System One | `https://api.typesafe.ai/v1/systemone`, `jev-latest`, TypeSafe key |
| `openrouter` | System One | `https://openrouter.ai/api/v1/systemone`, `jev-latest`, OpenRouter key |
| `kev` | System One | `http://127.0.0.1:8009/v1/systemone`, `kev-latest`, no auth |
| `laya` | System One | `http://127.0.0.1:8000/v1/systemone`, `typed-decisions`, no auth |
| `systemone` | System One | Explicit complete endpoint and served model |
| `openai` | Chat Completions JSON | Explicit complete endpoint and schema-capable model |
| `custom` | gw HTTP classifier | Explicit endpoint implementing `state/goals → decisions` |
| `cua` | gw HTTP classifier bridge | Explicit **evaluated bridge**, not a turnkey CUA runtime |

The config's `decision.provider` is the protocol adapter: `systemone`, `openai`,
`http`, or `off`. Legacy `jev` remains an alias for the System One wire format.
Presets choose protocol, endpoint and credential reference without binding the
architecture to a model vendor. Override `--model` with the exact deployed ID.
Pin a version instead of a moving alias when reproducibility matters.

### TypeSafe and OpenRouter

TypeSafe accepts `model`, `state`, and named typed `questions`; gw currently uses
Choice questions and validates every returned label. OpenRouter documents a
compatible `/api/v1/systemone` endpoint. It maps bare `jev-latest` to its own
latest Jev alias; you can instead supply a versioned ID supported by the endpoint.
Use an **OpenRouter key** there, not a TypeSafe key. Sources:
[TypeSafe quickstart](https://docs.typesafe.ai/introduction/quickstart),
[OpenRouter System One / TypeSafe SDK guide](https://openrouter.ai/docs/guides/community/typesafe-sdk).

OpenRouter's `/api/alpha/decisions` and `/api/v1/chat/completions` are distinct
surfaces. This preset uses **System One**; do not substitute another path while
leaving the wire format unchanged. No separate TypeSafe subscription is required
for the OpenRouter endpoint; account access/balance must still work.

### Kev local server

Use the upstream runtime in its own environment, not gw's dependency-free venv:

```bash
git clone https://github.com/jaredpalmer/kev.git
cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
```

Review the upstream requirements and pin the code/checkpoint you evaluate. First
startup downloads weights; warm the server before running the five-second-bounded
gw check. Ensure it listens only on loopback unless you intentionally secure a
remote deployment. Upstream documents `KEV_API_KEY` for bearer authentication;
when enabled, configure gw with `--key-env KEV_API_KEY` as well.

```bash
gw setup --preset kev --check --yes
# Authenticated server:
gw setup --preset kev --key-env KEV_API_KEY --check --yes
```

The preset's `kev-latest` is a served alias, not the downloaded checkpoint ID.
Upstream documents the request/answer format and model aliases in
[Kev](https://github.com/jaredpalmer/kev) and its
[server](https://github.com/jaredpalmer/kev/blob/main/kev/serve.py).

### Laya local server and Laya-MLX

The `laya` preset targets the HTTP server from
[NandhaKishorM/laya](https://github.com/NandhaKishorM/laya), whose
[server config](https://github.com/NandhaKishorM/laya/blob/main/laya/serve.py)
provides host, port, preload and bearer-key controls. In a separate environment:

```bash
python -m pip install 'laya[serve]'
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 LAYA_MODELS=typed-decisions laya-serve
```

Then run `gw setup --preset laya --check --yes`. For a server configured with
`LAYA_API_KEY`, add `--key-env LAYA_API_KEY`.

[Laya-MLX](https://github.com/mizorewww/laya-mlx) is a separate Python/MLX runtime,
not the HTTP server above. To use it, keep `agent.predict(state, questions)` in a
long-running local bridge exposing System One or the gw HTTP contract. Select
that bridge with `--preset systemone` or `--preset custom`. gw does not load MLX
or download its weights inside every hook process.

Small checkpoint context/choice limits matter. The Laya preset uses conservative
character/option limits; **characters are not model tokens**. A server can still
truncate below those limits. gw rejects reported truncation; it cannot detect
silent truncation by an arbitrary server. Reduce the decision context/questions,
evaluate representative cases, or use a larger-context model. Do not describe
identical wire shapes as proof of equivalent decision quality.

### CUA: make the task boundary explicit

[CUA-S1-nano](https://huggingface.co/cua-ai/cua-s1-nano-0.1) and
[CUA-S1-forms](https://huggingface.co/cua-ai/cua-s1-forms) document narrow
computer-use/form decision tasks. They are not general-purpose replacements for
Jev over arbitrary task-alignment and model-routing questions. Changing a model
name does not turn a GUI element/action scorer into a supervisor classifier.

Use those checkpoints as task-specific capabilities in the worker registry. To
use an appropriate CUA-family model for supervision, supply your own evaluated
bridge that supports **every configured goal** and returns this HTTP contract:

```bash
gw setup --preset cua --endpoint http://127.0.0.1:9010/classify \
  --model YOUR_EVALUATED_BRIDGE_ID --no-auth --check --yes
```

There is no assumed CUA endpoint, checkpoint download or launch command. A
specialist bridge must reject unsupported goals/context, never guess a safe
label. The `cua` preset fails without an explicit endpoint/model.

## Other routers, proxies and local endpoints

System One-compatible proxy:

```bash
gw setup --preset systemone --endpoint https://gateway.example/v1/systemone \
  --model your-decision-alias --key-env GATEWAY_API_KEY --check --yes
```

A chat-only router can use an explicitly chosen generative model as a JSON
classifier. This is a compatibility option, not a claim of System One speed,
calibration or token efficiency:

```bash
gw setup --preset openai --endpoint https://gateway.example/v1/chat/completions \
  --model your-json-model-alias --key-env GATEWAY_API_KEY --check --yes
```

The same command can target OpenRouter's chat endpoint, a configured LiteLLM
route, or a compatible local server. Only the **tested model/endpoint combination**
is supported; arbitrary APIs need the `custom` bridge. This release implements
Chat Completions, not a generic Responses or Anthropic conversion layer.

The default requests strict `json_schema`; an operator can explicitly choose
`--response-format json_object` for a server that supports only JSON mode. Both
paths still require every exact goal ID and an allowed label locally. There is
no automatic downgrade, JSON healing, second model, hidden retry or tool call.
`--token-parameter max_completion_tokens` selects that field instead of
`max_tokens` when required. Refusals, incomplete generations, tool calls,
non-JSON text, duplicate JSON keys and invalid/missing/extra labels are failures.
See [OpenRouter structured output support](https://openrouter.ai/docs/guides/features/structured-outputs).

**Avoid recursive supervision.** Do not route the supervisor's classifier calls
back through a gw-instrumented inference path that invokes the same classifier.
Use a separate decision endpoint/deployment without that callback, or an
operator-enforced internal route in your gateway. gw adds no client-spoofable
"skip governance" header. Ordinary model calls should remain instrumented.

Use full inference URLs; gw does not append endpoint paths or follow redirects.
HTTPS is required off loopback. `--no-auth` explicitly sends no token. Endpoint
URLs cannot contain embedded credentials or query parameters.

## Credentials, clients and model references

Setup stores **references**, not raw keys. Environment variables take precedence
over a configured key file. For GUI agents, an existing private file avoids
relying on a terminal's exported environment:

```bash
gw setup --preset openrouter --key-file "$HOME/.config/gw/credentials/openrouter" \
  --check --yes
```

Create/provision that file outside the agent conversation with your secret
manager or secure editor. It should contain only the token, optionally followed
by a newline. On Unix, the reader requires a regular file owned by the current
user with no group/other permissions (`chmod 600`). Windows deployments must
restrict the file using user-only ACLs; POSIX-mode validation is not an ACL audit.
The path is stored; the token is never copied into gw config, logs or backups.
This is not a secure vault against other same-user processes.

Configure an individual harness without replacing global defaults:

```bash
gw setup --preset kev --client codex --check --yes
```

Project configs still cannot introduce new decision endpoints or credentials.
Global client overrides and locked policy paths are validated before applying.
An existing registered classifier can be named with `--model-ref ID` instead of
`--model`; its `execution` must be `{"kind":"adapter","target":"systemone"}`
(or `openai`/`http` matching `decision.provider`), with enabled/available
`decision`, text-input, decisions-output capabilities. See [MODELS.md](MODELS.md).
The supervisor's classifier is pinned, not recursively selected by itself.

## Troubleshooting and operational checks

| Result | Next step |
|---|---|
| Missing key | Provision the configured environment/file reference in the actual agent process |
| 401 / 403 | Check the key and provider/model access; do not switch providers silently |
| 404 | Check the full endpoint path and selected protocol |
| 400 | Check model ID and supported request/JSON-schema fields |
| 429 | Check balance/rate limits; gw does not fall back to paid alternatives |
| Timeout / connection error | Start/warm the local service; check host/port; timeout is capped at five seconds |
| Unexpected labels / invalid shape | The contract smoke failed; do not use as a production quality signal |
| Truncation | Shorten context/choice sets or choose a suitable model; never silently authorize from clipped evidence |

Runtime provider failures use each goal's configured `on_error` effect. Defaults
advise; configure critical goals to `approve` or `deny` when required. Setup does
not weaken those goals. Schema correctness and a smoke pass are not semantic
accuracy, calibrated confidence or proof of safe authorization. Evaluate your
actual coding/form workflows before enforcement and after model updates.

## Agent-readable setup

Run `gw setup --describe` for a no-network JSON manifest. See
[the setup skill](../skills/gw-setup/SKILL.md) for a repeatable agent workflow.
Use flags plus `--dry-run`, then explicit `--check --yes` after operator consent;
never start the interactive wizard from an unattended job.

## Fast/slow and managed strategies

See [decision cascades](DECISION_CASCADES.md) for exact-label escalation, bounded
fallbacks, per-stage usage, and compatible adaptive endpoints. The primary
`decision check` remains a single synthetic transport smoke; the agent tool can
check the fallback explicitly.
