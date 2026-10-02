# CLI reference

[Handbook](README.md) · [Getting started](GETTING_STARTED.md) · [API](API.md)

The public executable is `gw`; `python -m gw_supervisor` is equivalent. Put the global `--home PATH` option **before** the command. Every command supports `--help`; `gw --version` prints the installed package version.

This reference describes 0.4.0. A fresh shell may need the installer's printed PATH update. Native hooks use the installed interpreter path rather than relying solely on your interactive PATH.

## Installation and diagnosis

| Command | Options | Effect |
|---|---|---|
| `bootstrap` | `--all` or `--agents NAMES`, `--project PATH`, `--dry-run` | Register user- or project-level hooks; default selection is detected agents |
| `uninstall` | Same options | Remove recognized gW hooks, preserving unrelated settings and retained data |
| `doctor` | `--project PATH` | Inspect configuration and executable presence; no live agent verification |
| `status` | None | Report recent sessions/candidates, event count, and recorded usage |
| `serve` | `--port N` (7777) | Start the authenticated IPv4 loopback supervisor API |

`--all` and `--agents` are mutually exclusive. Names are `claude`, `codex`, `gemini`, `cursor`, `copilot`, and `opencode`; aliases include `claude-code`, `gemini-cli`, `vscode`, and `github-copilot`.

A dry-run bootstrap does not write native settings, but ordinary command initialization can create the private state directory and API token. It is not a promise of zero filesystem effects. Multi-agent writes are atomic per file, not as a group.

`status` lists up to 100 sessions and 100 candidates. It does not print every event, raw transcript, provider account quota, or a computed dollar total. Missing usage fields remain unknown.

## Policy and tasks

| Command | Arguments | Effect |
|---|---|---|
| `init` | Optional `--project PATH` | Create an empty global/project policy file; refuse to overwrite an existing file |
| `config` | `--project PATH`, `--client NAME`, `--defaults` | Print effective policy/status, or complete built-in defaults |
| `trust` | `--project PATH` | Validate and snapshot the current project `.gw.json` |
| `task TEXT` | `--project PATH` | Pin the task used by new sessions in that project |

Project defaults use the current directory. New task/policy settings do not rewrite existing sessions. There is no built-in `task clear`, live session-policy migration, or arbitrary session deletion command.

```bash
gw --home "$HOME/.config/gw-trial" config --project . --client codex
```

This reads a different state/config location. It does not retarget hooks already installed with another `--home`; reinstall those hooks deliberately when changing their state location.

## Core decision backend

`gw setup` starts the interactive guide only in an appropriate terminal. Use explicit flags in agents and unattended scripts.

| Option | Meaning |
|---|---|
| `--describe` | Print a machine-readable setup manifest without initialization, writes, or inference |
| `--preset NAME` | `typesafe`, `openrouter`, `kev`, `laya`, `systemone`, `openai`, `custom`, or `cua` |
| `--endpoint URL` | Complete inference URL, not merely a provider base URL |
| `--model ID` / `--model-ref ID` | Direct served model or compatible registered decision model; mutually exclusive |
| `--key-env NAME` | Credential environment-variable name, never the token |
| `--key-file PATH` | Existing private token file; environment has precedence |
| `--no-auth` | Explicitly send no credential; do not combine with key references |
| `--client NAME` | Write a global client override instead of the global default |
| `--timeout SECONDS` | Warm request timeout within 0.1–5 seconds |
| `--max-state-chars N` | Bound supplied classifier state |
| `--response-format MODE` | `json_schema` or explicit `json_object` for the JSON chat adapter |
| `--token-parameter NAME` | `max_tokens` or `max_completion_tokens` for JSON chat |
| `--dry-run` | Show candidate config without saving; initialization may create state files |
| `--check` | Make one synthetic, possibly billable request before applying |
| `--yes` | Apply without an interactive confirmation |

`gw decision status --client NAME --project PATH` inspects the selected classifier configuration without inference. `gw decision check` uses the same options and performs the synthetic check. A failed checked setup leaves the existing configuration unchanged.

`gw enable-jev --key-env NAME` is the older direct-TypeSafe shortcut. It resets that transport to the direct preset rather than testing the existing endpoint. Prefer `setup` for review, backup, protocol selection, and testing. [Complete setup guide](DECISION_SETUP.md).

## Worker model selection

```bash
gw models list --project . --client generic
gw models select --operation code --input text --output text --capabilities code,tools
```

Selection accepts required `--operation`, `--input`, and `--output`; comma-separated `--capabilities`, `--execution`, and `--exclude`; optional `--context-tokens`; and `--project`, `--client`, and `--session`. Without a session argument it creates a new selection session.

The command returns a plan. It does not execute or bill the selected worker model. **With classifier selection enabled and multiple candidates, choosing that plan can call and bill the supervisor's classifier.** Priority selection and a single eligible candidate do not require that classification call.

`--execution` restricts `proxy`, `harness`, and/or `adapter`. `--exclude` removes candidates for that request, not from configuration. Reusing `--session` reuses its pinned policy.

```bash
gw models import-openrouter --models 'provider/model-a,provider/model-b'
gw models import-openrouter --file catalog.json --models 'provider/model-a'
```

The first command performs public catalog retrieval. The second reads a saved catalog. Both print a disabled fragment; neither updates settings, proves account access, or configures gateway aliases. [Model reference](MODELS.md).

## Model-gateway setup

```bash
gw proxy-init --model 'openai/YOUR_MODEL_ID' --output gw-litellm.yaml
```

Options are required `--model`, optional `--output` (default `gw-litellm.yaml`), `--api-key-env` (default `GW_UPSTREAM_API_KEY`), and `--api-base`. It creates a LiteLLM config referencing environment variables and the gW callback. It refuses to overwrite the destination.

This does not install/start LiteLLM, authorize accounts, or point a client at the new gateway. [Proxy integration](PROXY.md) includes the remaining steps and the distinction from a subscription-backed native client.

## Native and generic hook transport

```bash
gw hook generic pre < event.json
```

`hook AGENT PHASE` reads JSON from stdin and prints JSON to stdout. Phases are `start`, `pre`, `post`, and `error`. A generic event already contains its normalized `type`; the phase does not construct it for you.

For recognized native agents, normalization translates field names and result envelopes. The generic path returns the engine result. A handled pre-hook error is represented as a denial in JSON, often with process exit status 0. **Read the verdict; do not treat exit 0 as execution permission.** [Event/API reference](API.md).

## Knowledge commands

Knowledge is optional. Install the independent package into the same environment first. Place its GW-scoping options before the operation:

```bash
gw knowledge --project /path/to/project --client codex context 'provider failures'
```

Use `gw knowledge help` for its full parser. The standalone executable instead accepts `--store`, `--provider`, `--options`, `--tenant`, `--collection`, and `--principal` before the operation.

| Operation | Main arguments | Effect |
|---|---|---|
| `init` | `--provider`, `--options FILE`, `--collection`, `--read-only`, `--allow-writes` | GW-only global backend setup; no remote request |
| `ingest FILE` | `--id`, `--title`, `--source`, `--metadata JSON`, `--expected-revision` | Explicit UTF-8 source snapshot; no background synchronization |
| `search [QUERY]` | `--mode`, `--filters JSON`, `--limit`, `--cursor` | Search authorized sources |
| `context [QUERY]` | Search options except cursor, plus `--max-chars` | Assemble/reuse a bounded evidence packet |
| `read ID` | `--revision`, `--start-char`, `--end-char` | Read exact current source/range |
| `delete ID` | Required `--revision` | Delete a source through compare-and-swap |
| `capabilities`, `revision` | None | Inspect supported operations or current scope token |
| `cache-status`, `cache-clear` | None | Inspect cache bounds or evict current-scope packets; retain sources |
| `export` | None | Write owner-visible sources as JSONL; backend-dependent |
| `restore FILE` | None | Stream explicit exported sources; differing conflicts are not overwritten |
| `reindex` | None | Rebuild the local store's index; not a project-only mutation |
| `check` | `--query` | Read-only provider-contract smoke; remote providers receive requests |
| `mcp` | `--writable` | Run optional MCP stdio transport |
| `serve` | `--port`, `--token-env`, `--token-file`, `--writable` | Standalone-contract loopback HTTP service |

MCP/HTTP serving defaults to read-only; the writable flag cannot widen a GW connection whose policy disallows writes. The standalone SDK assumes its caller provides trusted scope. `restore` is not atomic across the entire input. Cache size is reported as logical bytes, not guaranteed physical database size. [Knowledge guide](KNOWLEDGE.md).

## Exit status and output

Ordinary successful commands return 0. Handled GW configuration/administration errors commonly return 1; argparse usage errors return 2. Failed setup checks and unavailable/review/denied model selections return 2. Standalone knowledge commands report handled knowledge errors as 2; the GW wrapper commonly maps them to 1.

Hook commands are different: handled failures return a protocol-native verdict on stdout. API calls are different again: inspect both HTTP status and returned decision. Neither a clean process exit nor HTTP 200 means a tool action was allowed. Keep diagnostics off protocol stdout in custom adapters.

## Agent tools

`gw agent serve --project PATH --client NAME [--manage]` serves MCP over stdio.
`gw agent call --project PATH --client NAME [--manage] TOOL --json ARGS` invokes
the same operation locally. `gw agent-guide` prints the operating skill.
`bootstrap --agent-tools` and `uninstall --agent-tools` manage native MCP/skill
registrations. See [the agent guide](AGENT_INTERFACE.md).
