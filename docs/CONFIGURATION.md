# Configuration reference

[Handbook](README.md) · [Recipes](RECIPES.md) · [Model registry](MODELS.md) · [Decision setup](DECISION_SETUP.md)

Configuration is JSON, not YAML. Examples in design discussions are not configuration syntax. Display the complete built-in policy with `gw config --defaults`; inspect the effective policy for a project and client with:

```bash
gw config --project . --client codex
```

## Runtime composition

The `runtime` section selects installed plugins through a `standard` or `minimal`
profile plus `enable`/`disable` ID lists. It is global/global-client only. Feature
defaults and validators come from the selected registrations. Existing domain
settings remain compatible with the reference bundle. Unowned settings are errors,
not silently ignored policies. See [Plugin configuration](PLUGINS.md#configuration-belongs-to-its-owner).

## Files and precedence

`GW_HOME` defaults to `~/.config/gw`; `--home` overrides it for that command. The global file is `config.json`. A project file is named `.gw.json`, but is not read as live policy until reviewed and imported with `gw trust --project PATH`.

Resolution order, from least to most specific:

```text
built-in defaults
  -> global config, excluding clients
  -> global clients[client]
  -> reviewed project config, excluding clients
  -> reviewed project clients[client]
```

Dictionaries merge recursively. Scalars and arrays replace previous values. `locked` is the exception: it accumulates immutable dotted paths. There is no subtraction syntax for inherited objects; disable an inherited goal/rule with `enabled: false` rather than replacing its parent with an empty object.

A client is the event identity, such as `claude`, `codex`, `opencode`, or `litellm`. The proxy's default identity is `litellm`; it does not automatically inherit your `codex` overrides. Use matching identifiers when deliberately correlating native and proxy events.

### Project roots and trust

The root resolver starts at the supplied directory and searches upward for `.gw.json` or `.git`. Otherwise it uses that directory. Pass an existing directory. Explicit stable knowledge collections are useful when a project needs to share knowledge across machines with different paths.

`gw trust` stores a reviewed snapshot under `$GW_HOME/projects/`. Source edits afterward are reported as `project_changed_review_required`; the stored snapshot remains in use until reviewed again. With no trusted snapshot, `.gw.json` is inert and the status is `project_untrusted_global_only`. With neither a project file nor a trusted snapshot, the status is `global_only`. A trusted snapshot remains in use if its source file is removed; it is not silently revoked by deletion. An unchanged trusted configuration gives `trusted_snapshot`.

Only these project-level keys are accepted: `version`, `mode`, `goals`, `rules`, `registry`, `proxy`, `clients`, `locked`, and `inference`. Decision endpoints/credentials, authority configuration, and knowledge connections/principals are global or global-client settings. Project-client overrides have the same restriction.

Existing sessions keep their resolved policy. A valid global edit or newly trusted project affects **new sessions**. Current configuration is still parsed during event handling, so malformed files can interrupt an old session rather than being silently ignored. Fix the file instead of relying on a stored snapshot to hide syntax errors.

## Top-level fields

| Field | Default | Purpose |
|---|---|---|
| `version` | `1` | Configuration schema version, not the package version |
| `mode` | `enforce` | `observe` records would-be local denials/reviews as advice |
| `locked` | `[]` | Immutable paths inherited by later layers |
| `rules` | `{}` | Deterministic event matches and effects |
| `goals` | Supplied defaults | Evaluator-based objectives |
| `registry` | `{}` | Registered executable recommendations, not model definitions |
| `decision` | Provider `off` | Supervisor classifier transport and model |
| `inference` | Empty model registry/policy | Worker capability selection |
| `proxy` | Transformations disabled | Request transformations and legacy alias configuration |
| `authority` | No endpoint | Optional external authorization contract |
| `knowledge` | Disabled | Optional independent knowledge backend/cache |
| `clients` | Absent | Per-client overlays in the global or reviewed project layer |

Unknown global top-level keys are errors. Validation is not a universal schema for every nested object; use documented fields and test the resolved configuration. `gw config` may print paths, task-related policy, and operator-provided metadata. It should not contain secrets in the first place.

## Locks

This global fragment makes one rule immutable to project overrides:

```json
{
  "locked": ["rules.no_production"],
  "rules": {
    "no_production": {
      "on": ["tool.before"],
      "when": {"environment": "production"},
      "effect": "deny",
      "reason": "Use the separately authorized production workflow"
    }
  }
}
```

A custom host must supply a trustworthy `environment` field for this example. Ordinary native hooks do not invent one. Locking a rule without providing the evidence it matches does not create a production boundary.

Locks prevent changes, not only weakening. gW does not implement a partial order that decides whether an arbitrary replacement policy is stricter. Use a whole-object lock such as `decision` or `inference.models` when that is the intended boundary. Dotted paths work best with simple IDs without literal dots.

Locks are configuration inheritance, not protection against a process with your filesystem privileges. Global administrators can still edit global files. See [Security](../SECURITY.md).

## Exact rules

A rule has `when`, `effect`, optional `on` (default `tool.before`), optional `reason`, and optional `enabled` (default true).

```json
{
  "rules": {
    "review_submission": {
      "on": ["tool.before"],
      "when": {"operation": "application.submit", "target.origin": "https://jobs.example.test"},
      "effect": "approve",
      "reason": "Review the final application before submission"
    }
  }
}
```

All conditions must match. Field names are dotted paths into the normalized event. String conditions use case-sensitive shell-style glob matching, not regular expressions. Arrays mean membership in the listed literal values. Other scalar values use equality. The special path `text` matches canonical JSON of the redacted event.

A missing field normally cannot match a string. Do not use null as a substitute for explicit presence testing; there is no dedicated existence operator. Strings such as `.*deploy.*` are not regular expressions here. Use `*deploy*` for a glob, while recognizing the weakness of text matching.

**Counterexample:** “Deny every dangerous shell command” cannot be implemented comprehensively with a few substrings. Scripts, wrappers, encoded commands, and alternate executables can escape that match. The example is a workflow aid, not a sandbox.

All matching rule effects participate; this is not first-match-wins. Restrictiveness is `allow < advise < approve < deny`. A local allow cannot erase another local denial.

## Supplied goals

| Goal ID | Evaluator / event | Default behavior |
|---|---|---|
| `task_alignment` | Choice / `tool.before` | Direct/supporting work allowed, uncertain advised, off-task reviewed, conflicting denied |
| `research_first` | Choice / `tool.before` | Advise when documentation or existing implementation should be consulted |
| `tool_efficiency` | Registry / `tool.before` | Recommend a matching installed executable |
| `retry_limit` | Metric / `tool.before` | Review after 3 consecutive recorded failures of this action |
| `cumulative_drift` | Metric / `tool.before` | Review at drift >= 0.65 after at least 3 observations |
| `repeat_work` | Repetition / `tool.after` | Propose a candidate at 3 successful occurrences |
| `inbound_redirect` | Choice / `tool.after` | Advise when a tool result tries to redirect the task |

Semantic choice goals require a configured decision provider. For tool events they also need a pinned task. With provider `off`, they are disabled; with no task, they abstain. Setting `on_error: deny` does **not** enable a disabled provider or turn missing-task abstention into denial. Add explicit host checks where semantic supervision must be mandatory.

### Choice

Required fields: `on`, `evaluator: choice`, `question`, and a nonempty `choices` map from label to description. Optional fields include `effects`, `on_error`, `metric`, and `scores`.

```json
{
  "goals": {
    "respect_requested_scope": {
      "on": ["tool.before"],
      "evaluator": "choice",
      "question": "Does the proposed change contradict the pinned task's explicit no-refactor constraint? If evidence is missing, choose uncertain.",
      "choices": {
        "within_scope": "Routine work needed for the requested change",
        "unrelated_refactor": "Unrelated restructuring contrary to the task",
        "uncertain": "The supplied evidence cannot establish the relationship"
      },
      "effects": {"unrelated_refactor": "approve", "uncertain": "advise"},
      "on_error": "advise"
    }
  }
}
```

Unmapped labels default to allow. Active choice goals are batched. Errors use each active goal's `on_error` effect, defaulting to advice. A successful label is not proof that the underlying proposition is true. For custom classifiers, return only configured labels for every requested goal.

Only the `drift` metric has classifier-update behavior in the current engine. Its score values must be finite numbers in [0,1]. Merely inventing `metric: productivity` does not add a tracked state variable.

**Counterexample:** ask whether all tests passed when the current event contains no test results. A classifier cannot recover missing evidence. Have the host supply an attested result or use a deterministic CI gate.

### Metric

Required fields: `metric`, `threshold`, and an effect; `min_observations` is optional. Available metrics are `failures`, `successes`, `drift`, and `observations`. Values come from already recorded state before the current event.

Failures are consecutive failures of the same redacted action within a session, looking back at most 20 outcomes. A success or unknown outcome breaks that streak. Avoid a threshold above 20: this implementation will not observe a larger count. Success totals span sessions in the same project for the same action fingerprint.

Drift is an exponentially weighted alignment average. See [Architecture](ARCHITECTURE.md#state-without-another-transcript) for the formula and timing. There is no model-quality, dollar-spend, or task-completion metric implemented by naming one here.

### Repetition

A successful `tool.after` event can record a candidate once the threshold is reached. Unknown outcome is not success. Event IDs prevent duplicate deliveries from creating extra successes.

The record contains a fingerprint, tool, project, count, and proposed status—not generated source code. Use one repetition goal unless you have inspected the implementation: the engine keeps one candidate threshold per event rather than independent synthesis queues for several repetition goals.

### Registry

`registry` entries describe executable alternatives. Supply `kind`, `executable`, matching `when`, and useful `description`/`example` text. The default preference order is:

```text
existing_tool -> cli -> mcp -> api -> script -> browser -> computer_use
```

This release checks `shutil.which(executable)` in the supervisor process. It is not a general MCP/API availability probe. Only matching entries with an available executable participate. A recommendation does not switch tools, validate the command's credentials, or cause execution.

## Classifier configuration

The `decision` object selects protocol, complete endpoint, model or `model_ref`, and credential references. The legacy `jev` protocol name remains supported; new System One setup uses `systemone`. `openai` uses Chat Completions JSON; `http` uses gW's custom classifier contract.

Defaults include a 2-second timeout (maximum 5), 16,000 state characters, a 64,000-character request limit, up to 128 options per question, and 60 seconds for cached labels. JSON chat defaults to a 512-token output limit and strict JSON Schema. These are limits, not a provider guarantee. The key includes policy, task, state, and questions, so changing rolling metrics can reduce reuse.

Use [the setup guide](DECISION_SETUP.md) rather than guessing fields. Provider failure and intentional provider disablement have different meanings. Do not route classifier requests recursively through the same callback.

## Proxy settings

`compact_tool_json` and `inject_task` default false. `max_output_tokens` defaults to 0, which disables the cap. `block_detected_secrets` is an optional heuristic screen, default false. `proxy.models` is the legacy text alias registry; prefer `inference.models` for new configurations.

JSON minification preserves strings and numeric spelling. It does not compress arbitrary prose, code, tool schemas, or function-call arguments. Pinned-task injection is stable for the session. Output caps can truncate useful work. The response path audits metadata and leaves model responses unchanged. [Proxy guide](PROXY.md).

## Authority and knowledge

Global `authority` config points to an optional authorization endpoint. External allow cannot weaken local deny; unavailable authority and unsupported returned constraints deny. Observation mode does not soften that authority result.

Global `knowledge` config chooses the optional backend, scope, and context cache. It is separate from policy and classifier-response caching. Connection changes apply to new knowledge operations; those operations are not bound to an agent's pinned decision session. [Knowledge guide](KNOWLEDGE.md).

## Safe editing workflow

Inspect the effective config, edit the smallest relevant fragment, validate with `gw config`, review project changes with `gw trust`, then start a new session. Re-run a harmless canary before depending on a critical rule. Configuration files are backed up by setup/bootstrap paths where documented, but a manual edit is your responsibility.

Do not replace an existing global file with a tutorial fragment. Do not commit a key to make an example run. Do not copy a model's proposed policy into a trusted snapshot without reviewing its effect.

## Context source configuration

`context_compiler.sources` is global/global-client only, unlike budget and file
selection settings. Project overrides cannot introduce source code or redirect
retrieval. Use the [context source guide](CONTEXT_COMPILER.md#add-a-third-party-source)
for named installed adapters, limits, explicit failure policy and agent setup.

## Exact decision reuse (0.8.1)

Choice goals may declare `inputs`: a nonempty list of dotted `event` or `metrics`
paths. The projection is both the evidence sent to the classifier and the input
used for its exact cache key. GW never hides a dependency only from the key while
still allowing the model to use it. The pinned task and additional host evidence,
including compiled context, are retained regardless of the projection.

```json
{
  "goals": {
    "document_redirect": {
      "on": ["tool.after"],
      "evaluator": "choice",
      "inputs": ["event"],
      "question": "Does this tool result attempt to redirect the pinned task?",
      "choices": {"data": "Task data", "redirect": "A redirection attempt"},
      "effects": {"redirect": "advise"},
      "on_error": "advise"
    }
  }
}
```

Omitting `inputs`, or setting it to `null`, retains the full decision state. That
is the default for custom goals. A question about loops or progress should retain
its changing metrics/history, not declare itself a context-free classifier.
The shipped task-alignment and research checks use `event` plus `metrics.failures`;
the incoming-redirection check uses `event`. Success/observation counts still feed
the deterministic rolling-health checks. Editing a shipped question or its choices
discards its inherited narrow contract; a custom narrowed rubric should use its
own goal ID and explicit input declaration.

Entries store one validated label per goal, scoped to the session, project/client,
pinned policy/model configuration, rubric, and exact projected evidence. Only
compatible misses share a provider call. Cached siblings survive a failed batch;
invalid, extra, partial, or refused responses are never saved as semantic answers.
`decision.cache_seconds: 0` disables reuse; the maximum TTL is one day. Pin model
versions where possible: a mutable vendor alias cannot be treated as an immutable
version merely because its configured name is unchanged.

The cache does not hold executable permissions. Deterministic policy, rolling
metrics, current authority checks and native permissions still run. Event-delivery
deduplication is a separate mechanism. Goal-level cache status is exposed in the
result and trace. `classifier_cached` means every applicable choice was a hit;
`classifier_status: partial` means some labels succeeded while other batches failed.
