# gw

**A configurable, local-first supervisor for agent actions and model calls.**

One decision engine. Native agent hooks. An optional LiteLLM callback and HTTP API. SQLite state. No runtime dependencies in the core. No new orchestration framework.

This is a **v0.2 prerelease**, not an enterprise security boundary or a claim that every agent runtime has been integration-tested. It implements deterministic policy, opt-in Jev/HTTP classification, cumulative drift, retry limits, repetition candidates and protocol-aware proxy transforms. It does not automatically generate/install tools or resolve passwords.

## Install and bootstrap

macOS / Linux, **Python 3.10+**:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.2.0/install.sh | bash -s -- --all
```

This installs an isolated virtual environment under `~/.local/share/gw`, links `~/.local/bin/gw`, and registers user-level hooks for Claude Code, Codex, Gemini CLI, Cursor, Copilot/VS Code and OpenCode's classic plugin API. It preserves unrelated configuration, backs up changed files, and does not use sudo or modify shell profiles, login credentials, model selection, billing or permissions. Python must already be installed. The installer prints the PATH command when `~/.local/bin` is not on PATH.

**Restart the agents. In Codex, review and trust the hooks through `/hooks`.** The installer cannot and should not silently accept a vendor's hook-trust prompt.

Windows / PowerShell, with Python 3.10+ on PATH:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/davidjbeveridge/gw/v0.2.0/install.ps1))) -All
```

Windows installs under `%LOCALAPPDATA%\gw\venv`; the script prints the full `gw.exe` path. It does not change execution policy or machine PATH.

Review the installer before piping it to a shell. For a local checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gw bootstrap --all
```

## Start using it

```bash
gw doctor
gw task 'Fix the login validation bug, add regression tests, and do not deploy' --project ~/code/myapp
# Start a fresh agent session in that project.
gw status
```

The first native user-prompt hook can also pin a task when none was explicitly set. Later prompts do not silently replace the root task. `gw task` and policy changes apply to **new sessions**; existing sessions retain their task and policy snapshot.

No API key is needed for local policy rules, retry tracking, repetition candidates, or proxy JSON minification. **Semantic goals are disabled until you opt in:**

```bash
export TYPESAFE_API_KEY='your-key'
gw enable-jev
# Start new sessions. Ensure GUI-launched agents also receive this environment variable.
```

`enable-jev` stores the environment variable's name, never the key. It opts in to sending redacted task/action context to the configured Jev endpoint. Redaction is best effort, not complete DLP; use opaque credential references instead of putting passwords in prompts. A vendor-neutral HTTP decision provider can replace Jev, including a local classifier.

## What runs where

```text
Agent hooks -------------------> gw engine <---------------- LiteLLM callback
                                 |                              |
                     config + rules + classifier                |
                                 |                         model provider
                              SQLite                      (Caveman optional)
                                 |
                         optional loopback API
                                 |
                    custom harness / future authority service
```

Hooks and the LiteLLM callback call the same Python library in their own processes. They do not require a supervisor daemon. `gw serve` exposes that engine for clients that need an HTTP interface.

### Included behavior

| Capability | Behavior |
|---|---|
| Client and project configuration | Defaults → global → client → reviewed project → project client; locked paths cannot be overridden |
| Task alignment | Optional typed classifier questions; task remains pinned |
| Cumulative drift | Persisted exponentially weighted average, minimum sample gate, configurable intervention |
| Failed loops | Review/deny after a configurable number of consecutive failures of the same action |
| Tool efficiency | Recommend matching registered tools only when their executable is available; configurable preference order |
| Research first | Classifier-backed advice before speculative implementation; not a claim that gw performs web research itself |
| Repeated work | Three successful repetitions create a reviewable automation candidate; no arbitrary code is generated or executed |
| Model economics | Capability-first registry for arbitrary models and execution backends; compatible proxy routing; typed subscription/adapter plans |
| Context efficiency | Opt-in whitespace-only minification of JSON tool results; stable pinned-task injection; output-token cap |
| Telemetry | Idempotent events, session metrics, candidate counts, provider-reported input/output token usage |
| Governance | Local deterministic rules plus optional external authority contract; external allow never overrides local deny |
| Credentials | Executor-side `CredentialInjector` protocol only; no vault/clipboard/password implementation |

An internal **allow means no supervisor objection**, not a grant of tool permissions. Native permissions remain in force. An `approve` verdict becomes a native prompt where supported, otherwise a denial with an explanation. Post-tool checks cannot undo actions and are reported as advice, not retroactive enforcement.

## Configuration

The global file is `~/.config/gw/config.json` (`GW_HOME` overrides the directory). Display the complete defaults with `gw config --defaults`.

```json
{
  "version": 1,
  "mode": "enforce",
  "locked": ["rules.never_deploy"],
  "rules": {
    "never_deploy": {
      "on": ["tool.before"],
      "when": {"input.command": "*terraform apply*"},
      "effect": "deny",
      "reason": "Deployments require a separate workflow"
    }
  },
  "clients": {
    "codex": {"goals": {"retry_limit": {"threshold": 2}}}
  },
  "proxy": {
    "compact_tool_json": true,
    "inject_task": true,
    "max_output_tokens": 4096
  }
}
```

Rules use conjunctive literal/glob matching over normalized event paths. This example is a workflow rule, **not a shell sandbox**: indirect scripts or a different spelling can escape a text match. Use OS/container/network controls for hard isolation.

Create a project override:

```bash
gw init --project ~/code/myapp
# Edit ~/code/myapp/.gw.json
gw trust --project ~/code/myapp
```

```json
{
  "version": 1,
  "goals": {
    "retry_limit": {"threshold": 3},
    "task_alignment": {"on_error": "approve"},
    "cumulative_drift": {"threshold": 0.7}
  },
  "registry": {
    "github_pull_requests": {
      "kind": "cli",
      "executable": "gh",
      "when": {"tool": "*browser*", "text": "*github.com*"},
      "description": "Inspect GitHub pull requests with the authenticated gh CLI",
      "example": "gh pr view NUMBER --json title,body,statusCheckRollup"
    }
  }
}
```

Project files are not live policy. `gw trust` copies the reviewed configuration outside the worktree; later edits require another trust operation and fresh session. Projects cannot change provider or authority endpoints. Locks are immutable paths in v0.1, not a complex partial-order permission language. This protects against accidental agent edits, **not another process running with your user privileges**.

See [Configuration](docs/CONFIGURATION.md) for custom goals and model routing.

## Any configured model, not a fixed tier

Configure `inference.models` with arbitrary provider/model IDs, operations,
input/output modalities, capability tags, execution targets and billing sources.
System One classifiers, text/code models, local inference, images, video, audio,
embeddings and native subscription-backed agents can coexist in the registry.

```bash
gw models list
gw models select --operation decision --input text --output decisions
gw models select --operation image.generate --input text --output image
```

Selection filters compatibility before applying configured preferences or a
Jev decision. Proxy-compatible plans can rewrite the alias; native harness and
custom adapter plans require their executor. Selection does not launch agents,
create accounts or turn subscription quota into API credits. Optional OpenRouter
catalog import accepts an explicit model list and leaves entries disabled until
reviewed. See [Model registry and routing](docs/MODELS.md) for configuration,
subscription boundaries, the HTTP API and supported media contracts.

## Agent support and verification

| Adapter | Installed configuration | Tool gate | Approval | Notes |
|---|---|---|---|---|
| Claude Code | `~/.claude/settings.json` | Native pre/post hooks | Native ask | Normal allow/deny rules still apply |
| Codex | `~/.codex/hooks.json` | Native pre/post hooks | Review maps to deny | `/hooks` trust required; runtime tool coverage varies |
| Gemini CLI | `~/.gemini/settings.json` | BeforeTool/AfterTool | Conservative deny | No undocumented ask assumption |
| Cursor | `~/.cursor/hooks.json` | preToolUse/postToolUse | Review maps to deny | Native Cursor envelope, not Claude-shaped hooks |
| Copilot CLI / VS Code Local | `~/.copilot/hooks/gw.json` | Native pre/post hooks | Native ask | Shared file, identical decisions in CLI and Local envelopes |
| OpenCode classic v1 | `~/.config/opencode/plugins/gw.mjs` | JS plugin before/after hooks | Review throws/block | Classic plugin API only; not a claim of v2 support |
| Other harnesses | CLI JSON or HTTP API | Executor must honor verdict | Host responsibility | No invented universal-hook compatibility |

```bash
gw bootstrap                         # Detected agents only
gw bootstrap --agents claude,codex,opencode
gw bootstrap --all --project .       # Project-local, instead of user-wide
gw bootstrap --all --dry-run
gw uninstall --all                  # Removes gw handlers, preserves other settings/data
```

`vscode` is an alias for the shared Copilot profile. VS Code sessions using Claude or Codex need the corresponding native adapter. Do not enable cross-tool hook imports on top of equivalent native installations without checking for duplicate invocation.

**Run a real deny canary after installing or updating each agent.** Add this global rule, start a fresh session, and ask the agent to run exactly `echo GW_CANARY_DENY`:

```json
{"rules":{"installation_canary":{"when":{"input.command":"echo GW_CANARY_DENY"},"effect":"deny","reason":"gw installation canary"}}}
```

Merge that into the existing config; do not replace your whole file. The command must not execute, and `gw status` must show an event. Remove the canary rule afterward. `gw doctor` reports configuration presence, not proof that a vendor runtime loads and honors it. Tests include native JSON fixtures and a real Node → Python OpenCode-adapter subprocess, not licensed-agent end-to-end sessions.

## Optional proxy integration

Install `litellm[proxy]` into the **same Python environment** as gw. This is optional and is not installed by the one-line core installer:

```bash
~/.local/share/gw/venv/bin/python -m pip install 'litellm[proxy]'
gw proxy-init --model 'openai/YOUR_MODEL_ID' --output gw-litellm.yaml
export GW_PROJECT="$PWD"
export GW_SESSION="a-unique-id-for-this-workflow"
export GW_PROXY_KEY='a-local-proxy-access-key'
export GW_UPSTREAM_API_KEY='your-provider-api-key'
~/.local/share/gw/venv/bin/litellm --config gw-litellm.yaml --host 127.0.0.1 --port 4000
```

Configure an API-capable client to use `http://127.0.0.1:4000/v1`, model `gw-default`, and `GW_PROXY_KEY`. This **does not convert subscription quota into API credits**. Bootstrap intentionally leaves existing OAuth/subscription setups alone.

For multiple concurrent projects, callers must send `metadata.gw` with explicit `project`, `session`, and optionally `client`. The fixed `GW_PROJECT/GW_SESSION` fallback is only for a deliberately scoped workflow. Matching native and proxy traces requires the same client/project/session identifiers; gw does not pretend to infer them from arbitrary model traffic.

The callback transforms requests and audits completed responses. Streaming chunks, tool-call IDs, tool arguments, reasoning signatures and refusals are not rewritten. Completed-stream auditing cannot retroactively block delivered content. Actual usage comes from provider/LiteLLM usage fields; compaction reports **bytes**, not fabricated token/cost savings.

### Caveman

Caveman is optional and separately installed. Use its printed per-provider LiteLLM base URL, not a guessed root URL:

```bash
caveman snippets litellm --app gw
# Example OpenAI mount from Caveman's docs:
gw proxy-init --model 'openai/YOUR_MODEL_ID' \
  --api-base http://127.0.0.1:8787/w/gw/openai/v1 \
  --output gw-litellm-caveman.yaml
```

Then run that LiteLLM configuration with Caveman already running. Compression/recovery behavior and provider support belong to Caveman. gw does not ship an unverified Caveman SDK or silently enable lossy compression. Start with one compressor, benchmark your workflows, and preserve originals/recovery when enabling more aggressive compression. See [Caveman's LiteLLM integration](https://docs.caveman.so/docs/proxy/litellm).

## API and governance extension points

```bash
gw serve --port 7777
```

The API binds only to `127.0.0.1`. Read the local bearer token from `$GW_HOME/api-token` (default `~/.config/gw/api-token`). Authenticated endpoints:

- `POST /v1/events`: normalized session/tool/model event → decision.
- `POST /v1/model/request`: `{context, payload, format}` → decision and request payload.
- `POST /v1/model/response`: `{context, payload}` → audit and unchanged response payload.
- `POST /v1/inference/select`: capability requirements → typed execution plan (no inference execution).
- `GET /v1/status`: metrics and proposed automation candidates.

`GET /healthz` reveals only service/version. Browser-Origin requests are rejected; this is not a public multi-tenant API. The executor must enforce decisions. API caller identities are assertions, not enterprise workload identities.

[Extension contracts](docs/EXTENSIONS.md) cover typed classifiers, external authority, credential injection and future Warden adapters. There is **no claim that Warden is integrated**. Unknown authority constraints fail closed rather than being silently ignored.

## Security and limits

Read [SECURITY.md](SECURITY.md). In particular: same-user processes can modify user-owned files; hooks can be disabled or omitted by their host; some vendor hook timeouts fail open; classifiers are fallible; a proxy sees only routed API calls; approvals must not be inferred from a successful tool result; password injection and legal assent are not implemented; model/provider safety controls are not bypassed.

The SQLite event log stores hashes, metadata, verdicts and aggregate usage, not raw tool outputs or model transcripts. Pinned root tasks and configuration snapshots are stored locally. Do not put secrets in task text or configuration.

## Development

```bash
python -m pip install .
python -m unittest discover -s tests -v
python -m compileall -q gw_supervisor
bash -n install.sh
```

CI runs Python 3.10 and 3.13 on Linux, macOS and Windows, with Node for the OpenCode bridge tests. See [validation notes](docs/VALIDATION.md) for what is and is not exercised, and [roadmap](docs/ROADMAP.md) for the next slices.

MIT license. Inspired by the per-action monitor pattern in [shapor/jev-sentinel](https://github.com/shapor/jev-sentinel), but implemented as a generic, non-cyber-specific decision plane.
