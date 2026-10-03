# Architecture and method

[Handbook](README.md) · [Plugin contracts](PLUGINS.md) · [Configuration](CONFIGURATION.md) · [Security](../SECURITY.md)

GW is a runtime for decisions around an agent, not another agent supervising every
turn with an open-ended conversation. The worker performs the task. Plugins provide
judgment, context and integrations. The core gives those contributions stable
meaning and a recorded lifecycle.

## The dependency direction

```text
native agent / model gateway / management surface
                      |
              selected GW plugins
                      |
       public API + small runtime + configuration

reference plugins → independent context/knowledge/observation/learning/sync libraries
```

Plugins depend on the public runtime API, not the reverse. Peer services are
resolved by contract name. A compiler plugin can use a third-party knowledge source,
the local knowledge package, several sources, or no knowledge service. Its caller
does not instantiate a specific store.

The `gw-supervisor` wheel contains runtime, configuration, utilities and compatibility
aliases. `gw-builtin` delivers the standard domain plugins. Existing substantial
libraries retain their own wheels and APIs. The installer makes this a single
normal setup rather than twelve independent installation decisions.

## The action boundary

The kernel normalizes identity and obtains a session from the selected repository.
A session pins configuration and plugin implementation identities. Evaluators then
run in ordered local, plan, and authority phases. Their assessments contain effects
and evidence, not executable capabilities. The runtime reduces them, commits the
canonical result, and calls non-authoritative observers afterward.

An allow means no objection; native permissions still apply. A local or external
allow cannot cancel a denial. Observation mode softens local blocking before the
external authority is consulted. A post-tool result cannot be stopped retroactively.
A baseline records without running the normal evaluator chain; authority plugins
must explicitly validate that the baseline does not bypass their requirements.

These invariants belong to the core because every plugin depends on their meaning.
The rubrics, retry thresholds, choice labels and model routes do not belong there.
They are configuration and mechanisms owned by their reference domain plugins.

## Fast decisions are not complete reasoning

The reference inference plugin supports typed decisions, bounded primary/fallback
cascades, and managed adaptive endpoints. The policy plugin supplies questions and
state; the decision provider returns validated labels. A typed result is easier to
consume, but is not proof of correctness or calibrated authorization confidence.

The optional context service can supply evidence to the judge. Missing required
context follows the configured error path rather than becoming an invented answer.
Selection of a worker model is a separate operation: compatibility filters precede
preferences, and a selected plan is not automatic execution authority.

See [Decision cascades](DECISION_CASCADES.md), [Model selection](MODELS.md), and
[Context compilation](CONTEXT_COMPILER.md) for their actual contracts and limits.

## State without another transcript

The reference state plugin owns SQLite/WAL sessions, action records, usage and
candidates. The kernel knows the repository interface, not the database schema.
Policy/history consumers use a documented history facet. Additional plugin state
is namespaced and committed with the canonical event.

Existing source owners retain their material. Native transcripts stay in native
files; knowledge text stays in its provider; research output stays with learning.
Observability retains compact measurements and source locators. It is not a second
copy of every request. Missing or changed originals are explicit coverage gaps.

The supplied drift signal is an exponentially weighted score:

```text
next_drift = 0.7 * previous_drift + 0.3 * alignment_observation
```

This remains a policy/state implementation detail, not a kernel-wide definition
of success. It reads prior recorded observations and cannot measure unseen task
quality. Other policy plugins may use different progress models.

## Configuration and operating scope

Defaults are composed from selected plugin registrations, then inherit through
global, client, reviewed project and project-client settings. Plugins declare
which fields may be project-specific and which remain host-only. Worktree edits
do not silently replace trusted configuration or select new executable code.

Factories come from installed distribution metadata. The selected graph rejects
missing services, duplicate owners, incompatible APIs and cycles. Service creation
is lazy; closure runs in reverse construction order. Per-hook processes and network
judgments still have costs. No speed improvement is asserted merely because code
was extracted from a module.

## Deliberate limits

In-process plugins are trusted Python, not sandboxed programs. Declared versions
are not cryptographic code attestation. Repeated concurrent delivery can incur
more than one evaluation before storage picks its canonical result. The runtime
is not a durable job scheduler, an OS access-control platform, or a transaction
coordinator for external effects.

Hook enforcement still depends on the native host invoking and honoring the
codec. The codec can reject handled errors, but cannot repair disabled hooks,
host timeouts or operations that never pass through GW. The full
[plugin guide](PLUGINS.md) documents interface shape, replacement examples,
migration, failure policy and tests. [Benchmark design](BENCHMARKS.md) describes the
additional evidence needed before claiming better task outcomes or lower costs.
