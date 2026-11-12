# Getting started

[Handbook](README.md) · Next: [Decision setup](DECISION_SETUP.md) · Reference: [CLI](CLI.md)

The first goal is small: install gW, prove that a native tool action reaches it, and confirm that the host honors a denial. A model key, inference proxy, and knowledge store are not prerequisites for that test.

## Prerequisites

Install Python 3.10 or newer and the agent you intend to use. The core has no third-party runtime dependencies. Native agents retain their own prerequisites and authentication. The optional local knowledge provider requires a Python SQLite build with FTS5; the optional MCP transport adds the official Python SDK.

The scripts do not install Python, your agent, local model weights, LiteLLM, Caveman, or a service manager. The [adapter matrix](ADAPTERS.md) specifies what bootstrap writes.

## Choose an installation

### Lean setup from current source

The source installer on `main` uses the lean setup for a new state directory:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/main/install.sh | GW_REF=main bash -s -- --agents codex
```

Choose one adapter; `--all` is an explicit broader install. On Windows, use the
source PowerShell installer with `GW_REF=main` and `-Agents codex`. Set `GW_REF`
to a reviewed commit if you need a reproducible source install. The pinned
v0.8.1 release below keeps its original behavior.

Fresh bootstrap selects the native hook, state, policy, inference setup, and
governance plugins. Only the exact retry goal is active; literal rules apply
when configured. It records events locally. It does not expose MCP tools,
send model requests, or activate context, tracing, or learning by default.
Existing config files and existing state directories with session or trusted
project data retain their composition; bootstrap does not migrate them.

### Normal user-local installation

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh | bash -s -- --all
```

On macOS/Linux, this creates a virtual environment under `~/.local/share/gw`, links `~/.local/bin/gw`, and installs all six adapter families. `XDG_DATA_HOME`, `GW_INSTALL_DIR`, and `GW_BIN_DIR` can change these paths. The installer refuses to overwrite an unrelated `gw` executable at its chosen link location.

If `gw` is not on PATH, use the exact path printed by the installer or, for the default location:

```bash
export PATH="$HOME/.local/bin:$PATH"
gw --version
```

The installer does not edit your shell profile. Persist that PATH change yourself only if it suits your setup. Native hook commands contain the installation's Python path, so a missing interactive-shell `gw` command does not by itself prove the hook cannot run.

Select fewer agents with `--agents claude,codex`; omit both `--all` and `--agents` to use detection. Detection checks executables and familiar configuration directories. It is convenience, not runtime verification. `--all` can create configuration for agents you have not installed.

### Inspect first

```bash
curl -fsSLo gw-install.sh https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh
less gw-install.sh
bash gw-install.sh --agents claude,codex
```

Release artifacts include checksums. A checksum supplied alongside a download helps detect corruption; it is not independent publisher authentication. A release tag is not a promise of cryptographic immutability. Use an audited commit through `GW_REF` when that distinction matters.

### Windows

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.ps1))) -All
```

Python must be available as `python`. The default environment is `%LOCALAPPDATA%\gw\venv`; invoke its `Scripts\gw.exe` or use the printed command. The script does not change machine PATH or execution policy. Add `-Knowledge` for the independent knowledge package. Windows file-access restrictions require appropriate ACLs; POSIX permission bits are not a substitute.

### Local checkout or isolated trial

From a clone of the repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install . ./packages/gw-builtin
.venv/bin/gw --version
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\gw.exe`. To try behavior without touching your agent settings, run the [offline examples](../examples/README.md).

For a project-only trial, choose an existing project and a separate state directory:

```bash
.venv/bin/gw --home "$HOME/.config/gw-trial" bootstrap --agents claude --project /path/to/project --dry-run
.venv/bin/gw --home "$HOME/.config/gw-trial" bootstrap --agents claude --project /path/to/project
```

The second command writes the trial hooks. Use the same `--home` for subsequent trial commands. Remove an existing user-level gW installation for that agent before testing a project-local copy, or you may invoke both. Global and project installation are choices, not two required steps.

## Inspect, then set the task

```bash
gw doctor --project .
gw config --project . --client codex
gw task 'Fix login validation and add regression tests. Do not deploy.' --project .
```

Run from the relevant project. `gw task` stores the root task for new sessions. Without an explicit task, the first usable native user-prompt event can pin one. Later prompts do not replace it. When the assignment changes, pin the new task and start a fresh session.

A useful scope names the work and the important boundary. “Fix issue 123 and add a regression test; do not deploy” is more useful than “do coding.” Avoid scopes so narrow that ordinary setup and tests appear unrelated. Never put credentials in task text.

`doctor` reports configuration presence and runtime locations. It neither launches your agent nor proves that it loaded the hook. An API credential available to this shell may still be absent from a GUI-launched process.

## Prove that the hook runs

A classifier is not needed for this check. In the global configuration file, merge this rule while preserving the rest of the file:

```json
{
  "rules": {
    "installation_canary": {
      "on": ["tool.before"],
      "when": {"input.command": "echo GW_CANARY_DENY"},
      "effect": "deny",
      "reason": "gW installation canary: this command must not execute"
    }
  }
}
```

The default global path is `~/.config/gw/config.json`. Check the effective configuration with `gw config`; for this test use `mode: enforce`, not `observe`.

Restart the agent, accept any explicit hook-trust prompt, and start a new session. Ask it to run **exactly** `echo GW_CANARY_DENY`. The host should reject the tool call with the configured reason. `gw status` should show an event.

Three outcomes need different interpretations:

| Observation | What it establishes |
|---|---|
| The exact tool call is denied by gW | That tested tool path, agent version, and configuration honored the rule |
| The model declines without making a tool call | Nothing about hook delivery; it may have decided not to call the tool |
| The call executes or no event appears | The integration is not verified; inspect hook loading and the actual normalized fields |

Some agents wrap commands or use different argument fields. Inspect a harmless native payload before widening the canary. Do not claim that one shell denial verifies browser, MCP, subagent, or cloud execution paths. Remove the rule when finished and begin a new session. [Troubleshooting](TROUBLESHOOTING.md) covers the failure cases.

## Optional semantic decisions

```bash
gw setup
```

The guide configures the supervisor, not the working model. On a lean setup it
does not enable a semantic goal. After provisioning the relevant key outside the
conversation, a noninteractive example is:

```bash
gw setup --preset openrouter --check --yes
```

`--check` sends one synthetic request and saves only after it passes. Use `--dry-run` to inspect the proposed configuration; a dry run with `--check` still sends that explicitly requested test. `gw setup --describe` is the machine-readable guide.

For local Kev/Laya, start and warm the model server separately. Read [Decision setup](DECISION_SETUP.md) before choosing an endpoint: System One, OpenAI-compatible JSON chat, and the custom HTTP contract are not interchangeable wire formats.

Follow [goal opt-in](DECISION_SETUP.md#opt-in-to-a-semantic-goal) to enable one goal,
then start a new agent session. A successful connection check does not establish
decision quality. Try representative tasks before enabling blocking effects.

## Add only the optional component you need

On `main`, installer options install the supporting packages and select their
plugins. `--context` selects the context compiler; `--knowledge` adds knowledge;
`--agent-tools` selects MCP management tools and context; `--plugins` selects
the trace, learning, and sync commands. With packages already installed, pass
the same flags to `gw bootstrap` (`--dry-run` previews native registration).
Selection makes commands and tools available; it does not turn on background
observation, learning, sync, ingestion, or automatic context delivery.

See [runtime composition](CONFIGURATION.md#runtime-composition) for opting in to
a single plugin. Prefer a separate trial state directory to changing a
working setup in place.

**Proxy:** follow [Proxy integration](PROXY.md). The bootstrap does not redirect your existing subscription traffic. Routing model calls through an API gateway is a separate, explicit configuration choice.

**Knowledge:** install with `--knowledge`, then use [Knowledge setup](KNOWLEDGE.md). `gw knowledge init` enables explicit local storage; it does not scan your disk or inject documents into every prompt.

**External governance:** start with the [authority contract](EXTENSIONS.md#authorityprovider--future-warden-adapter). An interface is not a completed access-control integration.

## Update and recover

Rerun the installer for the release you intend to use. Hooks refer to the installed interpreter, so bootstrap should run after an installation-path change. Restart agents and repeat the canary after gW or vendor updates. Keep track of the actual agent version you tested.

Changed native settings are backed up under `$GW_HOME/backups`. Writes are atomic per file; the entire multi-agent bootstrap is not one transaction. If one adapter fails after others succeed, inspect the reported changes and fix that adapter rather than assuming nothing changed.

Do not blindly replace a live configuration with an old backup: unrelated settings may have changed since it was created. Compare the files first.

## Remove hooks without deleting your work

```bash
gw uninstall --all
```

For project-local hooks, provide the same `--project`; for a trial, provide the same `--home`. This removes recognized gW handlers while retaining unrelated settings, policy, traces, and knowledge. It does not uninstall Python packages, stop a separately launched server, or erase stored data.

Stop agents before manually removing the installation or state directories. Export knowledge and back up any records you need first. Data removal is an operator action, not a side effect of removing hooks.

## Runtime migration

The 0.8 installer includes `gw-builtin`; installing the core wheel alone no longer
installs the standard behavior. Existing command names and configuration fields
remain. Start fresh native sessions and restart the agent MCP interface so their
plugin manifests are pinned. See [Plugin migration](PLUGINS.md#migration-from-07).
