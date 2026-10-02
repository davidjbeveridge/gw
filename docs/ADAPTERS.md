# Native agent adapters

[Handbook](README.md) · [First-run verification](GETTING_STARTED.md#prove-that-the-hook-runs) · [Generic API](API.md)

An adapter translates a host's events and response format. It does not give every host the same capabilities. This page describes the files and behavior implemented by gW 0.4.0, not every feature in the current vendor documentation.

The implementation is [adapters.py](../gw_supervisor/adapters.py). For vendor contracts, use the official links in the matrix; after either product changes, repeat the actual runtime test.

## Locations and events

| Adapter | User-level file | Project-level file | Events registered by gW |
|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/hooks) | `~/.claude/settings.json` | `.claude/settings.local.json` | UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure |
| [Codex](https://developers.openai.com/codex/hooks) | `~/.codex/hooks.json` | `.codex/hooks.json` | UserPromptSubmit, PreToolUse, PostToolUse |
| [Gemini CLI](https://geminicli.com/docs/hooks/reference/) | `~/.gemini/settings.json` | `.gemini/settings.json` | BeforeAgent, BeforeTool, AfterTool |
| [Cursor](https://cursor.com/docs/hooks) | `~/.cursor/hooks.json` | `.cursor/hooks.json` | beforeSubmitPrompt, preToolUse, postToolUse, postToolUseFailure |
| [Copilot CLI / VS Code Local](https://docs.github.com/en/copilot/reference/hooks-reference) | `~/.copilot/hooks/gw.json` | `.github/hooks/gw.json` | UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure |
| [OpenCode classic](https://opencode.ai/docs/plugins/) | `~/.config/opencode/plugins/gw.mjs` | `.opencode/plugins/gw.mjs` | chat.message, tool.execute.before, tool.execute.after |

`COPILOT_HOME` and `XDG_CONFIG_HOME` are honored for the corresponding user paths. Other vendor-specific home overrides are not inferred by this adapter. The `vscode` alias selects the shared Copilot profile; VS Code running a different agent needs that agent's adapter. See [VS Code's hook reference](https://code.visualstudio.com/docs/agent-customization/hooks) for host behavior.

OpenCode support here means its classic plugin interface. It is not a claim of v2 coverage. Custom harnesses use the generic CLI or HTTP interface rather than an invented universal native hook format.

## Verdict delivery

| Adapter | `approve` before a tool | Pre-tool advice | Post-tool advice |
|---|---|---|---|
| Claude | Native `ask` | `additionalContext` | `additionalContext` |
| Codex | Deny with review explanation | `additionalContext` | `additionalContext` |
| Gemini | Deny | Recorded only | AfterTool `additionalContext` |
| Cursor | Deny | Recorded only | `additional_context` |
| Copilot | Native `ask` in both supported envelopes | Recorded only | `additionalContext` |
| OpenCode classic | Throws before execution | Recorded only | Appended to the tool result |

A clean `allow` normally produces an empty native response, leaving ordinary permissions in place. An `advise` result is not necessarily visible to the working model before execution. Where the native path does not have a supported advisory field, gW records the recommendation rather than pretending the host acted on it.

The native `start` phase records the task and returns no control directive. Do not configure a session-start denial and assume these adapters stop the prompt. Pre-tool decisions are the enforcement path in this release.

## Identity and correlation

Normalization accepts native session identifiers and refuses missing identity rather than combining unrelated sessions. Project location comes from the host's working directory or workspace root, then the local root resolver. Tool IDs are used when available; timestamps can supply a stable derived event ID, otherwise a new ID is generated.

For generic integrations, supply your own stable event and session IDs. Deliver one `tool.before` and one `tool.after` with the same action ID and normalized input. The two event types remain distinct; duplicate delivery of one type reuses its recorded result.

The current adapters do not normalize a complete parent/subagent hierarchy. If a host reuses a session ID across workers, the resulting aggregation reflects that host's identity behavior. Do not infer individual subagent isolation from one gW session record.

## Failure interpretation

Explicit native failure events become `success: false`. For tool-result objects, the codec checks recognized error and exit-code fields. Otherwise native post-tool events are generally treated as success. That is a host-contract assumption, not a universal proof of success.

A generic caller should send `success: null` when the outcome is unknown. Incorrect success reporting changes retry counts and automation-candidate detection. Verify native result shapes, particularly when a vendor embeds an error inside a string or changes an exit-code field's type.

Bootstrap sets 20-second command-hook timeouts where the supported profile permits it; Gemini expresses that limit in milliseconds. The OpenCode bridge uses a 15-second subprocess timeout. Cursor has no timeout override added by this generator. These outer timeouts are not the classifier's shorter request timeout.

A Python exception caught by the hook wrapper can become a native denial. A host that never starts the command, terminates it, or discards the response is outside that guarantee. Official [Codex security documentation](https://developers.openai.com/codex/enterprise/agent-security) explicitly distinguishes a supported denial from a failed hook. Test the failure path, not only the happy path.

## Bootstrap and upgrades

Bootstrap merges recognized handlers into existing configuration and backs up changed files. It does not overwrite an unrelated OpenCode plugin occupying its destination. Repeated bootstrap is intended to be idempotent for the same installation and state paths.

Use the generated commands; they preserve interpreter and state-directory paths. Do not move a virtual environment and assume previously installed hooks follow it. Re-bootstrap after moving the installation. Avoid importing another tool's equivalent hooks in addition to installing gW natively; duplicate hooks can multiply judgments and observations.

A desktop application, remote development host, and cloud runner may load different settings. A local install says nothing about an agent that executes elsewhere. Codex's local/cloud orchestration distinction and Claude's managed settings are examples of why “same product name” is not sufficient evidence of coverage.

## Verify each controlled path

First use the [canary](GETTING_STARTED.md#prove-that-the-hook-runs). Record the gW version, agent version, OS, configuration scope, actual tool name, observed payload shape, and whether denial happened before execution.

Then test the boundaries you intend to depend on: shell, file writes, browser tools, MCP, failure reporting, and subagents as applicable. A fixture test verifies our codec against an input; a licensed live-agent test verifies the host actually emits and honors that exchange. Report those as separate evidence.

## Adding an adapter

Implement normalization and response mapping, define bootstrap locations/events, then add fixtures and an executable harmless-denial test. Preserve unrelated configuration and make uninstall remove only owned handlers. Document exactly where advice and approval are unsupported.

Do not translate unknown result shapes into a successful action. Do not turn an unavailable approval UI into allow. Do not add a broad permission grant to make the canary pass. Use [Contributing](../CONTRIBUTING.md) for test expectations and [API](API.md) for the normalized event contract.
