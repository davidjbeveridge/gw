# A small runtime, replaceable capabilities

[Handbook](README.md) · [Public API](../gw_supervisor/api.py) · [Reference bundle](../packages/gw-builtin/README.md) · [Working extension](../examples/runtime-plugin/README.md)

GW 0.8 separates the runtime from the behavior shipped with it. The core loads a
reviewed composition, resolves configuration, pins a session, orders evaluations,
and reduces their results. The reference plugins decide how to judge an action,
choose a model, assemble context, or connect an agent.

**The boundary is a domain capability, not a Python file.** Replacing the context
compiler should not require replacing knowledge storage. Adding a review rule
should not require forking the runtime. A string helper needs neither a manifest
nor an entry point.

## What stays in core

The `gw-supervisor` distribution owns the public API, installed-plugin discovery,
configuration inheritance and locks, project trust snapshots, session/plugin
identity, lifecycle ordering, and the final verdict reducer. It provides the
small command host and plugin inventory. It has no mandatory runtime dependency.

The core does not implement SQLite, goal rubrics, model transports, native hook
codecs, retrieval, the context compiler, a dashboard, or learning jobs. Old
`gw_supervisor` feature-module paths remain import aliases to the reference
bundle. They are migration aids, **not the extension API**.

The reducer is deliberately not another replaceable policy plugin. It establishes
what a contribution means: an allow cannot erase a denial; observation mode cannot
soften an external authority denial; a post-action check cannot undo execution.
Making those rules subject to whichever plugin ran last would make the interface
unreliable.

## What ships as plugins

The normal installer includes `gw-builtin`, a single MIT distribution containing
these individually selectable registrations:

| Plugin | Owns | Replace or extend it when… |
|---|---|---|
| `gw.state` | Session repository, task pinning storage, event ledger, history and decision cache | You need a different persistence service or storage environment. |
| `gw.policy` | Goal evaluation, literal rules, retries, repetition, cumulative alignment, tool recommendations | You need a different supervision policy. Extra evaluators can also coexist without replacing it. |
| `gw.inference` | Decision transports, fast/slow cascades, capability-first selection, model setup | You need a different decision/routing implementation, not merely another configured model. |
| `gw.governance` | External authority adapter and its baseline constraints | You are integrating Warden or another authorization service. |
| `gw.context` | Context collection and delivery around the compiler | You need another compiler/optimizer or collection strategy. |
| `gw.knowledge` | The optional knowledge-service bridge | You need a different knowledge integration. Existing provider adapters remain supported. |
| `gw.observe` | Trace production, local query/dashboard integration and usage accounting | You need another observation backend or presentation integration. |
| `gw.learning` | Evidence collection and the learning coordinator bridge | You need different learning orchestration or proposals. |
| `gw.sync` | Reviewed harness-distribution integration | You need another distribution or rollout implementation. |
| `gw.harness` | Native codecs, bootstrap and host diagnostics | You are adding a host integration or replacing the supplied adapter family. |
| `gw.gateway` | Model-request/response interception and LiteLLM/HTTP integration | You need another gateway, wire adapter or request-transform policy. |
| `gw.agent` | Agent-facing management, configuration plans, MCP and tool hosting | You need a different control surface or management workflow. |

A **distribution** is an installation unit. A **plugin** is a replacement boundary.
Shipping twelve tiny wheels would add versioning and installation work without
improving these boundaries. A vendor can ship one replacement plugin, several
plugins, or a bundle of its own.

The substantial independent libraries remain separate: `gw-context`,
`gw-knowledge`, `gw-observe`, `gw-learning`, and `gw-sync`. They do not import the
runtime. A reference plugin adapts one of those libraries into GW; the library
can still be used without GW. The normal installer keeps those optional package
flags rather than making every install download every feature.

## Composition, not import order

Installed distributions advertise zero-argument factories under
`gw_supervisor.plugins`. The factory returns an immutable `Plugin` descriptor.
Discovery reads package metadata and loads only selected factories. A package
being present is not permission to activate every entry point it contains.

The default `standard` profile selects the twelve names above. Selection is
operator/global-client configuration:

```json
{
  "runtime": {
    "profile": "standard",
    "disable": ["gw.context"],
    "enable": ["acme.context"]
  }
}
```

This is a template: `acme.context` must be installed first and implement the
services its consumers need. The existing agent configuration-plan tools can
review/apply the selection. They do not install untrusted Python packages or fetch
credentials. Restart the native session and MCP interface after changing its
composition; a bound tool from the old graph is rejected rather than silently
retargeted.

`minimal` starts with no plugin IDs. For an SDK-only installation, the core can
initialize and inspect that profile without importing reference code:

```bash
gw --home /absolute/trial-state init --profile minimal
gw --home /absolute/trial-state runtime inspect
```

An empty profile can inspect configuration but cannot execute supervision until
a state provider is selected. A programmatic host can instead supply a list of
`Plugin` objects to `gw_supervisor.api.runtime(..., plugins=[...])`. This is useful
for a controlled embedded host and the core-isolation tests.

### Validation before use

Each service, command, tool name and configuration section has exactly one owner.
Two selected providers for `context` are an error, not a first-import-wins choice.
A replacement disables the previous owner and supplies the same required service.
Additive policy plugins normally contribute another evaluator and their own
configuration namespace instead.

Required services must exist. API-major mismatches, duplicate entry points,
conflicting configuration ownership and dependency/order cycles fail explicitly.
Services are constructed lazily and reused within their runtime; cleanup closes
constructed services in reverse construction order. Per-call native hook processes
still pay startup/discovery overhead. No daemon or remote service was introduced
by this refactor.

Dependencies are service names rather than implementation IDs. `gw.policy` needs
`inference`, not specifically `gw.inference`. Optional services are resolved through
`Services.optional`; a missing optional integration stays absent. A declared
service dependency is not an OS capability restriction—plugins are trusted code.

## The public interface

New integrations import **`gw_supervisor.api`**, whose API major is `1`. Do not
import `gw_builtin`, the registry implementation, or the old feature aliases to
obtain a peer's functionality.

The registration vocabulary is small:

| Contract | Purpose |
|---|---|
| `Plugin` | Identity/version, required services and contributed capabilities. |
| `ConfigSection` | Defaults, validation, project scope, host-only subfields and permitted agent administration. |
| `Evaluator` | One named, ordered assessment at a known phase/event. |
| `Assessment` / `Advice` | Effects plus bounded feature metadata, audit fields and plugin state. |
| `Command` | A CLI handler receiving the complete GW argv, including the host's `--home`. |
| `Tool` / `AgentHost` | A typed callable bound to project/client scope, with explicit mutation annotations. |
| `Services` | Required/optional peer resolution without concrete imports. |
| `SessionRepository` | Runtime persistence; `HistoryRepository` adds the reference history/policy facet. |

Python protocols document the named services used by reference consumers:
`DecisionService`, `ContextService`, `KnowledgeAccess`, `ObservationService`, and
`GatewayService`. The [API source](../gw_supervisor/api.py) is the signature
reference. Implement the complete consumed facet, not just a method that happens
to make the first test pass. Service method contracts evolve with the SDK major;
plugin/distribution versions identify the selected implementation separately.

### A complete small extension

The [installable example](../examples/runtime-plugin/README.md) adds an exact,
harmless review gate and a status tool using only the public API. Its registration
has this form:

```python
from gw_supervisor.api import Advice, Assessment, Evaluator, Plugin


def assess(ctx):
    if ctx.event.get("input", {}).get("command") == "echo GW_EXTENSION_REVIEW":
        return Assessment((Advice("approve", "Review the demonstration command"),))
    return Assessment()


def plugin():
    return Plugin(
        id="example.review",
        version="0.1.0",
        evaluators=(Evaluator(
            name="example.review", phase="local", evaluate=assess,
            events=("tool.before",),
        ),),
    )
```

The distribution would advertise that factory in `pyproject.toml`:

```toml
[project.entry-points."gw_supervisor.plugins"]
"example.review" = "example_package:plugin"
```

The fully runnable repository example additionally declares a validated,
project-configurable setting and an agent status tool. No runtime or agent-host
source edit is needed to discover them. The example does not install a shell
policy or claim that an exact string match contains an adversarial agent.

### Configuration belongs to its owner

Plugin sections contribute defaults to the existing inheritance chain:

```text
runtime defaults + selected plugin defaults
    → global → global-client → reviewed project → project-client
```

Project snapshots cannot select code, change the plugin profile, or redirect
host-only provider settings. Each plugin declares which section may be overridden
in a project and which nested fields remain host-only. The previous `goals`,
`decision`, `context_compiler`, and other setting names remain valid in the
standard profile; no mechanical rewrite of every config file is required.

Agent administration is separately opt-in per section (`agent_writable`). An
optional patch validator can further constrain operator-facing edits. The managed
agent surface uses those declarations, then validates the complete candidate,
checks locks, prepares a reviewable plan, and performs revision-checked apply.
A plugin's new settings do not require another hardcoded allowlist in the agent.
Native user consent is still a host responsibility, not inferred from a schema.

Unowned configuration is rejected. When disabling a configured plugin, replace
it with one that owns its compatible section or deliberately remove/migrate that
section. GW does not silently ignore a saved policy because its implementation
was removed. Client compositions are validated independently. An overlay accepted
by one client need not be accepted by a client with different selected plugins.

### Assessment order and authority

The runtime evaluates fixed phases:

```text
validate event / resolve composition / pin session
    → local assessments
    → execution/model plans
    → external authority
    → canonical repository commit
    → non-authoritative observers
```

`Evaluator.after` imposes explicit ordering inside that sequence. Independent
contributors have stable name ordering; registration order is not a policy.
Normalized v1 event types remain the existing session, tool, model and selection
boundaries. Plugins do not invent new kernel event semantics by adding a string.

An evaluator receives detached event/config/session/result snapshots. It returns
an `Assessment`, not a rewritten final verdict. Effects combine as
`allow < advise < approve < deny`. Feature metadata has an owner and cannot replace
reserved runtime fields. Contributions, audit records and effects are bounded.
Invalid contributions and evaluator failures produce a denial at pre-action
boundaries; observer failure never grants permission or rewrites the canonical
record.

In `observe` mode local blocking is softened before external authority is applied.
In `baseline` mode normal evaluators do not run. An authority plugin must supply
an explicit deterministic baseline validator or the runtime rejects the baseline.
The reference authority rejects bypass when an external endpoint is configured.
A broken authority cannot disappear merely because an experiment asked for a
baseline. Post-action review remains advice, not retroactive enforcement.

### State and observations

The repository owns atomic event/result persistence and session policy snapshots.
Duplicate deliveries reuse the first committed result. This is **not exactly-once
inference under concurrent duplicate requests**; multiple processes may evaluate
before one wins the canonical commit. External executors still need their own
idempotency and transaction boundaries.

`Assessment.state` is persisted under the contributing plugin ID. A plugin can
read its latest snapshot through `repository.read_state(session_id, plugin_id)`.
The reference state adapter keeps existing policy counts in their canonical tables
instead of making a second copy. New plugin state has its own namespace.

The reference policy/context/agent plugins also use `HistoryRepository` for task,
recent-event, cache and learning-evidence access. They do not require a SQL handle.
An alternative state service must implement that facet when hosting them. The
reference local trace viewer resolves the standard state's explicit SQLite source
locator; a remote state backend needs a compatible source reader/observation
backend for rich original-record drill-down. Missing sources remain visible gaps,
not fabricated local paths.

The session stores the selected plugin IDs, declared API/implementation versions
and distribution origins once. Events carry the manifest hash and deterministic
per-evaluator timing/status. Changing the composition/version requires a fresh
session. This is declared-version pinning, not bytecode attestation: modifying
installed code without changing its version is outside that guarantee.

Observers receive copies after commit. Logging, inventory and the reference
compiler use no model calls. A plugin that performs research or classification
must account for that explicit workload; registration is not permission to make
unmetered calls from an observer. There is no transactional outbox to arbitrary
external sinks in this release.

## Migration from 0.7

Use the normal 0.8 installer. It installs core plus the reference bundle, then the
same requested optional libraries and agent registrations. `--agent-tools`
continues to include `gw-context`; `--knowledge` includes the knowledge package and
context compiler. Existing commands and the `gw_context_compile` tool remain.

A manual checkout installation now needs both:

```bash
python -m pip install . ./packages/gw-builtin
```

Add `".[agent]"` and the desired library directories for MCP/context/etc. Release
assets include separate wheels and source archives; no PyPI publication is implied.
The core alone is intentionally not the standard working product.

Start fresh native sessions after upgrading. Pre-0.8 session records are readable
history, but have no pinned plugin manifest; the runtime refuses to silently
reinterpret their policy through a new composition. Restart the MCP interface to
refresh its registered tools. Existing databases, trusted configuration files and
source references are not erased.

The native hook entry point chooses its codec before loading the full policy graph.
That lets an installed codec return a native denial for malformed configuration
or missing evaluator dependencies. Custom transports can select their own codec
with `--transport-plugin`. Missing codecs, host timeouts, ignored hooks, and
same-user tampering remain outside GW's containment guarantee.

## What this does not add

There is no hot reload, package marketplace, remote plugin execution protocol,
background orchestrator, arbitrary token-interception bus, or new authentication
system. Installed plugins run as trusted in-process Python with the host's OS
rights. Typed interfaces and copied inputs reduce accidental coupling; they do not
sandbox hostile code.

Per-goal rubrics, model IDs, learning modes and tool registries remain data inside
their domain plugins. Compiler algorithms and transport helpers remain ordinary
modules. Use the existing knowledge/context-source and learning-worker interfaces
when they are already the right extension point; a second runtime plugin is not
required for every new backend.

## Design references and evidence

[PyPA's entry-point specification](https://packaging.python.org/en/latest/specifications/entry-points/)
provides the installed-distribution discovery mechanism. The explicit hookspec
approach described by [pluggy](https://pluggy.readthedocs.io/en/stable/) is useful
prior art. GW does not add a pluggy dependency: its small fixed phase reducer and
service contracts need ordering and ownership, not a general multi-wrapper hook
framework.

Tests cover API/ownership failures, dependency cycles, deterministic ordering,
service cleanup, partial-contribution rejection, authority precedence, baseline
constraints, configuration isolation, state rollback, actual installed extension
registration, and stale tool/session manifests. Separate CI jobs run the kernel
without any reference or optional package, and build the reference bundle outside
the repository. Existing harness, context, provider and dashboard suites remain
regression gates. These checks establish implementation behavior, not productivity
or model-quality gains.

## Warm runtime reuse (0.8.1)

A runtime reuses its loaded plugin composition between events while re-reading
selection and validating configuration. Native hooks bind that composition for the
whole intercept/delivery operation. Package metadata is parsed once per distribution
in a discovery pass. There is no process-global cache of policy, permissions, or
mutable session state. Configuration changes apply to new sessions as before;
a changed composition rejects old sessions. Updating installed implementation code
requires restarting the runtime/MCP process; hot-swapping Python code in place is
not supported. Command-based hooks still launch their Python process per call.
