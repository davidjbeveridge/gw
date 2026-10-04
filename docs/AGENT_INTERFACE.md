# Use GW from the agent

[Handbook](README.md) · [Decision cascades](DECISION_CASCADES.md) · [Context compiler](CONTEXT_COMPILER.md)

GW now has a tool interface, not just commands for the operator to remember. Once
installed, ask your agent to inspect a run, open the dashboard, configure a
backend, or compile context. The agent supplies the tool arguments.

## One installation, then ordinary requests

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh | bash -s -- --all --agent-tools --plugins --knowledge
```

This installs the optional MCP dependency and registers a server named `gw` in
supported local clients and includes the independent context compiler. `--plugins`
adds observability/learning/sync; `--knowledge` adds the optional knowledge store. On Windows, the PowerShell switches
are `-All -AgentTools -Plugins -Knowledge`. Existing core-only installations remain
valid. No API account or paid model is configured by installation.

Restart your agent and approve its native MCP/hook trust prompt where required.
Those user actions are not silently accepted. A shell-capable agent can perform
the requested installation itself; it should read this guide first, preserve
existing settings, and never ask you to compose configuration JSON.

Then ask, for example:

> Open the GW dashboard and show where it intervened in my last run.

> Configure Jev through my existing OpenRouter credential reference, with the
> reasoning model I specify as a fallback for uncertain decisions. Show the
> changes and any new data destinations before applying them.

> Compile the context needed to fix this login bug. Include the active testing
> skill, relevant project evidence, and the latest outcomes.

The MCP prompt `gw` provides the operating guide. Claude and Codex also receive a
`gw` skill in their supported skill locations. Other clients can use the prompt
and tools directly; identical slash-command syntax is not claimed across hosts.

## Tools

| Tool | What it does |
|---|---|
| `gw_status` | Inspect the bound project, pinned task, configuration, sessions and installed packages |
| `gw_setup_options` | Discover setup presets, strategy options, and compiler settings without inference |
| `gw_configure_plan` / `gw_configure_apply` | Prepare a scoped patch, then apply its reviewed revision with backup |
| `gw_decision_check` | Send one synthetic check to the configured primary or fallback; may incur provider cost |
| `gw_task_set` | Pin the user-requested task for new sessions |
| `gw_trace_start` / `gw_trace_finish` | Record explicit run boundaries and an asserted outcome |
| `gw_trace_query` | List runs, inspect reports/timelines/source records, or compare runs |
| `gw_dashboard_open` | Start the known local dashboard if needed and open its authenticated page |
| `gw_context_compile` | Assemble an inspectable evidence packet; does not permanently enable injection |
| `gw_knowledge` | Search/read the configured knowledge store; explicit writes require permission |
| `gw_models_select` | Return a worker execution plan; selection may invoke a configured classifier |
| `gw_learning_query` | Inspect the configured local learning store's proposals and history |

Tool descriptions and schemas are exposed through MCP. `gw://status` is a readable
resource. The knowledge and learning tools require their optional packages; they
do not silently install missing dependencies. Learning queries are over the
configured local store, which may contain proposals from several projects.

A CLI facade exposes the same operations for harnesses without MCP:

```bash
gw agent-guide
gw agent call --project . --client codex gw_status
```

The agent—not the user—can construct `--json` arguments when needed. Management
operations require the explicit `--manage` launch flag. `agent serve` uses stdio;
no public agent-control HTTP port is opened.

## Scope and management

An MCP process is bound to its project and client at launch. Tool arguments do
not allow changing that project or impersonating another client. Project-local
registrations pin an absolute project path. User-level registrations use the
host's launch working directory, `CLAUDE_PROJECT_DIR`, or operator-supplied
`GW_PROJECT`. The agent should inspect `gw_status` before acting. Hosts that do
not launch in the intended workspace should use project-local registration;
a guessed workspace is not a safe default.

The installer’s explicit `--agent-tools` option registers managed tools. A server
started without `--manage` omits setup application, task writes, run mutations,
provider checks and dashboard launch. Read operations still access local state
and may retrieve from a configured remote knowledge provider.

Management is a local host capability, not a claim of tamper-proof identity. The
model must act on the user's request; the plan/apply sequence is not proof of
human consent. Native tool approval remains in force. The agent interface does
not expose arbitrary shell execution, authority changes, lock removal, or
arbitrary installed-plugin loading through configuration tools.

A setup plan records the old and proposed configuration hashes, scope, patch and
expiry. Applying refuses stale state, preserves unrelated fields, writes a
backup, and respects existing configuration locks. Runtime configuration remains
pinned to existing agent sessions; changes take effect in new sessions. Connection
checks are explicit and synthetic, not an automatic upload of project content.

## Native registration

| Host | User registration | Project registration |
|---|---|---|
| Claude Code | `~/.claude.json`, `mcpServers.gw` | `.mcp.json` |
| Codex | `~/.codex/config.toml`, `mcp_servers.gw` | `.codex/config.toml` |
| Gemini CLI | `~/.gemini/settings.json`, `mcpServers.gw` | `.gemini/settings.json` |
| Cursor | `~/.cursor/mcp.json`, `mcpServers.gw` | `.cursor/mcp.json` |
| Copilot CLI | `~/.copilot/mcp-config.json`, `mcpServers.gw` | `.github/mcp.json` |
| OpenCode | `~/.config/opencode/opencode.json`, `mcp.gw` | `opencode.json` |

Existing unrelated servers/settings are preserved; an unrelated server named `gw`
is not overwritten. Codex gets a marked TOML block rather than a rewrite of the
whole configuration. Existing OpenCode JSONC configurations cause an explicit
refusal rather than being shadowed with a new JSON file. VS Code editor MCP
configuration is distinct from Copilot CLI: this registration does not claim to
configure every VS Code agent mode. Use the host's MCP UI with the same stdio
server command when its format differs.

`gw uninstall --all --agent-tools` removes recognized GW registrations and the
owned skill, retaining unrelated settings and data. Files are updated atomically
one at a time; a multi-file bootstrap is not a filesystem transaction.

## Dashboard and credentials

The opener only launches GW's own loopback dashboard. It checks readiness before
opening the browser, reuses an existing authenticated instance, and does not
return its token to the model. The browser receives the token in a fragment,
which the dashboard removes. A remote/headless MCP host cannot open the user's
separate desktop browser; the result reports that limitation.

Credentials remain operator-provisioned environment or private-file references.
A GUI/MCP host may not inherit terminal environment variables; some hosts filter
secrets by default. Use supported host provisioning or an existing private file,
not pasted API keys or discovery of another application's OAuth tokens.

## Primary references

[Claude MCP](https://code.claude.com/docs/en/mcp) ·
[Codex MCP](https://developers.openai.com/codex/mcp/) ·
[Gemini MCP](https://geminicli.com/docs/tools/mcp-server/) ·
[Cursor MCP](https://cursor.com/docs/mcp) ·
[Copilot MCP](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers) ·
[OpenCode MCP](https://opencode.ai/docs/mcp-servers/) ·
[Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

Registration fixtures and an actual MCP client/server test verify this package's
behavior. They are not proof that every installed vendor release loads every
configuration automatically. Native approval and runtime checks still matter.

## Context sources without a knowledge store

Agent-tools installation now includes `gw-context`; it does not require
`gw-knowledge`. `gw_setup_options` lists installed context-source providers
without running them. Configure a requested adapter through the existing
plan/apply tools, or leave sources empty for project/session-only compilation.
The `gw_context_compile` operation and native permission behavior are unchanged.
See [Context sources](CONTEXT_COMPILER.md#add-a-third-party-source).

## Runtime plugins

`gw_runtime_inspect` shows selected plugins, service ownership, registered tools,
execution phases and configuration scope. Tool registration now comes from plugin
manifests rather than a fixed method list. Plugins can contribute their own typed,
project-bound tools and explicitly agent-editable configuration sections.

A configuration plan may enable/disable already installed runtime plugins; it does
not install packages. Apply only the user's requested change, respecting native
permissions, locks and review. Restart the MCP interface and begin a new native
session after composition changes. A callable bound to the old manifest fails
explicitly instead of running against a different schema/provider. See
[Runtime plugins](PLUGINS.md).
