# Troubleshooting

[Handbook](README.md) · [First run](GETTING_STARTED.md) · [Decision setup](DECISION_SETUP.md) · [FAQ](FAQ.md)

Start with the layer that failed. Installing a package, loading a hook, authenticating a model, judging correctly, and enforcing a decision are separate checks.

## Collect a small diagnostic record

```bash
gw --version
gw doctor --project .
gw config --project . --client codex
gw status
```

Replace `codex` with the actual event client. Record the native agent version, OS, installation path, whether hooks are user/project-local, and the actual operation that failed. Do not paste tokens, full private prompts, or raw production traces into an issue. Configuration may contain sensitive paths or metadata even when credentials are references.

## The `gw` command is missing

The default Unix link is `~/.local/bin/gw`; the environment is `~/.local/share/gw/venv`. Add the printed bin directory to this shell's PATH or use the full path. On Windows, use the printed `Scripts\gw.exe` path. The installer deliberately avoids persistent shell/machine PATH edits.

If the installer refuses an existing `gw`, inspect it rather than deleting it. Choose `GW_BIN_DIR` to avoid an unrelated command. After moving an environment, rerun bootstrap so native hooks no longer reference the old Python path.

## Bootstrap stopped partway through

Native settings must be valid JSON of the supported shape. A malformed existing hooks object, an incompatible version field, or an unrelated OpenCode plugin at the target path causes an error.

Inspect backups and the changes already reported. Bootstrap is not a transaction across every agent; earlier files may already have been updated. Do not overwrite all vendor configuration to recover one adapter. Fix or select that adapter and rerun idempotently.

## A hook file exists, but nothing is supervised

Restart the agent and begin a new session. In Codex, explicitly review/trust `/hooks`. Confirm whether the active environment is local, an IDE host, a container, remote development, or a cloud runner; the settings may live elsewhere.

Run the [canary](GETTING_STARTED.md#prove-that-the-hook-runs). If no event appears, inspect the native tool event and command path. If a model merely refuses to attempt the call, that is not a canary success. If the shell tool wraps the requested command, your exact match may not apply.

One denied shell call proves only that tested path. Test browser, MCP, or subagent execution separately before relying on it.

## The command runs even though a rule says deny

Check the effective `mode`; `observe` intentionally softens local blocking. Confirm the correct client/project/session and start a new session after changing policy. Check whether the rule's fields actually exist and whether a string condition uses a glob rather than a regular expression.

A literal `input.command` match is not a general shell policy. Finally, inspect the native host: hook timeout/error behavior can permit execution despite a failed hook. gW's handled error response is not a guarantee about what happens when the host kills or ignores the process.

## Advice appears in logs but the agent ignores it

Some adapters only record pre-tool advice. Others provide additional context, which is still advice rather than deterministic execution. Consult [verdict delivery](ADAPTERS.md#verdict-delivery).

A recommendation to use `gh` does not switch the next tool call. A classifier warning to consult documentation does not perform a search. Use a host-controlled deterministic workflow when an operation must happen in a prescribed sequence.

## Semantic labels are absent

`classifier_status: disabled` means the decision provider is off. Run `gw setup` if classification is intended.

`no_pinned_task` means task-dependent tool checks abstained. Pin the task before a fresh session or verify the native prompt event. A task string attached to an arbitrary tool event does not replace the pinned task.

`unavailable` is an actual provider/validation failure. Inspect `gw decision status` and run `gw decision check` from the agent's environment. Per-goal `on_error` controls that failure; it does not enable a disabled backend.

## A terminal check passes but a GUI agent fails

GUI processes may not inherit the environment exported in a terminal. Provision the configured variable in the actual launch environment or use an existing private key file. Setup records the reference, not the token. Restart the application after changing how it receives credentials.

On Unix, the decision key file must be regular, owned by the current user, and inaccessible to group/other users. Windows deployments need user-only ACLs; the POSIX mode test does not audit them.

## The classifier endpoint rejects requests

| Symptom | Check |
|---|---|
| Missing credential | Correct environment-variable name or private file; `--no-auth` only when intended |
| 401/403 | Correct provider's key, account access, and model permissions |
| 404 | Complete endpoint path and matching wire protocol |
| 400 | Served model ID, supported request fields, JSON Schema/JSON mode |
| 429 | Provider limits or balance; no automatic alternative provider is tried |
| Timeout | Local server started and warmed; correct host/port; bounded warm timeout |
| Invalid labels/shape | Backend must return every exact configured choice, not explanatory prose |
| Truncation reported | Reduce supplied context/options or use an appropriate model; do not accept partial evidence |

OpenRouter's System One endpoint is different from Chat Completions. Laya-MLX is not the same server as the Laya preset. CUA forms/nano need an appropriate bridge rather than a renamed Jev endpoint. [Setup guide](DECISION_SETUP.md).

## A policy edit does not change the current run

Tasks and policy are pinned per session. Review a changed project with `gw trust`, then start a new session. Inspect `config_status`; an untrusted worktree file is deliberately ignored, while an edited previously trusted file requires review.

Knowledge operations are different: they resolve their connection settings when opened, not from an agent's pinned decision session. Do not use a config edit as a way to retroactively reinterpret an old decision record.

## Model selection is unavailable

Inspect the result's `rejected` reasons. Models are filtered before preferences apply. Common causes are disabled/unknown availability, missing operation/modality/capability, exhausted declared quota, an expired availability timestamp, incompatible execution kind, or an unknown context window when a size requirement was supplied.

A proxy request requires a proxy execution target. A native subscription entry will not become compatible by raising its priority. An empty allowlist permits no models. Opaque provider state can bind a request to its existing alias.

If more than one candidate needs classifier ranking, that classifier must be configured. No suitable selection leads to approval or denial according to policy; the system does not secretly expand to a paid fallback. [Models](MODELS.md).

## LiteLLM reports missing scope or cannot import the callback

Install GW into the same Python environment as LiteLLM. Send `metadata.gw.project/session` or deliberately set `GW_PROJECT/GW_SESSION` for one workflow. Do not combine all concurrent projects under one fixed environment identity.

Unknown LiteLLM call types are explicit failures. A future provider endpoint may need a tested mapping; it is not automatically covered because LiteLLM can call it. Keep the supervisor's classifier on a nonrecursive internal path. [Proxy integration](PROXY.md).

## Knowledge search returns nothing

Verify knowledge is enabled and that the source was explicitly ingested into this project/collection. The local backend does keyword or structured search, not embeddings. Exact scalar filters distinguish strings, numbers, and booleans. Check the principal/read permissions and document expiration.

An ingested file is a snapshot, not a live mount. Editing the original file does not reindex it. A new machine's project path hashes to a different default collection; assign the same explicit collection only when sharing is intended.

A missing result is not the same as a backend failure. The HTTP adapter rejects malformed results and unavailable endpoints rather than silently returning empty hits.

## A context lookup misses the cache

That can be correct. The key includes provider, scope/principal, query/options, corpus/index revision, assembler version, and evidence budget. New documents, permission edits, expiration, and reindexing can invalidate retrieval. Changing `max_chars` creates a different packet.

Unversioned providers are not cached by default. Explicit TTL-bounded reuse revalidates every source, and cannot detect newly added documents until its TTL expires. A provider outage never justifies stale-on-error evidence.

Cache reuse avoids repeated discovery/preparation, not the context tokens of evidence subsequently supplied to a model. Compare successful work, not just hit counts.

## Source updates conflict

Read the current source revision. Reconcile your change, then retry with `--expected-revision REV`. Do not discard compare-and-swap just because a second writer changed the document first. Delete also requires the current revision.

Bulk restore imports records as it proceeds; a later conflict does not roll back earlier records. Inspect the result and rerun idempotently after resolving the conflict. Export belongs to the durable source store, not the cache.

## Cache clear did not shrink the database file

The limits and reports concern logical cached entries/bytes. SQLite free pages, WALs, and backups can outlive logical deletion. Clearing context does not delete source documents and does not promise secure disk erasure. Stop writers and follow an appropriate storage/retention procedure when physical reclamation or deletion assurance matters.

## Reporting a problem

Include the smallest reproducible input, expected behavior, actual verdict/error, configuration fragment, and versions. Label a fixture test, API test, and live-agent test accurately. Redact sensitive values without removing the structure necessary to understand the bug. [Contribution guide](../CONTRIBUTING.md).
