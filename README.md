# gW

## Install

**macOS or Linux · Python 3.10+** · Try the lean setup from the current source:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/main/install.sh | GW_REF=main bash -s -- --agents codex
```

**Star this repository** using GitHub's **Star** button if the project is useful. **[Fork it](https://github.com/davidjbeveridge/gw/fork)** to try your own policies, adapters, and experiments. Contributions with reproducible results are especially welcome.

The installer adds user-level hooks for Claude Code, Codex, Gemini CLI, Cursor, Copilot/VS Code, and OpenCode's classic plugin API. It preserves unrelated settings and backs up changed files. It does not install those agents, change their authentication, redirect their inference, or grant permissions. Restart your agents afterward; in Codex, review and trust the hooks through `/hooks`.

Replace `codex` with your agent. Fresh bootstrap starts with pinned tasks, exact
rules, retry limits, and a local event record. Semantic goals, context and
knowledge, tracing, learning, sync, and the gateway are opt-in. Verify the
[native denial check](docs/GETTING_STARTED.md#prove-that-the-hook-runs) before relying on it.

<details>
<summary>Pinned release, Windows, and optional knowledge support</summary>

The pinned v0.8.1 release predates the lean bootstrap on `main`. Its defaults
are unchanged. To install that release on macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh | bash -s -- --agents codex
```

Windows PowerShell, with Python 3.10+ on PATH:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.ps1))) -All
```

Add the independent knowledge package on macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh | bash -s -- --all --knowledge
```

On Windows, add `-Knowledge`. Neither option installs an embedding model or connects to a cloud knowledge service.

Prefer to inspect the installer first?

```bash
curl -fsSLo gw-install.sh https://raw.githubusercontent.com/davidjbeveridge/gw/v0.8.1/install.sh
less gw-install.sh
bash gw-install.sh --all
```

See [installation and first run](docs/GETTING_STARTED.md) for a local checkout, isolated trials, updates, and removal.

</details>

---

**The decider. Not another agent.**

Your agent can write the code. It should not have to rediscover, on every turn, whether it is still solving the right problem, whether the last three attempts failed, or whether a simpler tool is already available.

gW moves those recurring decisions into a small, configurable supervisor. Native hooks observe proposed actions. An optional model-gateway callback observes inference requests. The same engine applies your rules, asks a typed decision model when judgment is needed, and records what happened.

Keep the agent you like. Change the decisions around it.

[Documentation](docs/README.md) · [First run](docs/GETTING_STARTED.md) · [Architecture](docs/ARCHITECTURE.md) · [Examples](examples/README.md) · [FAQ](docs/FAQ.md) · [Releases](https://github.com/davidjbeveridge/gw/releases)

> **Current scope:** gW is for cooperative, user-controlled workflows. Fresh bootstraps on `main` use deterministic supervision without a model key. Existing policy is preserved. See [why the defaults changed](docs/HARNESS_RESEARCH.md#why-semantic-gating-is-opt-in), [implementation validation](docs/VALIDATION.md), and the [security model](SECURITY.md).

## A runtime, not a monolith

GW's core now owns configuration, plugin lifecycle, session identity and verdict
precedence. The standard behavior ships in **`gw-builtin`**, a separate MIT bundle
of replaceable domain plugins: policy, inference, context, governance, storage,
observability, learning, sync and agent/gateway/harness integrations.

The normal installer includes the reference bundle. You do not need to assemble
the graph manually. Ask your agent to inspect `gw_runtime_inspect`, explain the
active providers, or prepare a reviewed plugin/configuration change.

Plugin authors build against `gw_supervisor.api`, not another plugin's private
modules. Services have one selected owner; additive evaluators can coexist. The
independent context and knowledge packages stay independent. No cloud service or
new mandatory model call is introduced by this split.

[Runtime architecture and authoring](docs/PLUGINS.md) ·
[Installable extension example](examples/runtime-plugin/README.md)

## Why this exists

An agent run can be wrong without being dangerous. It can keep investigating after the answer is known, repeat a failed command, use a browser for something an installed CLI does directly, or spend a strong model's reasoning budget on a routine classification. A second frontier agent watching the first can make the run more expensive without making it easier to understand.

There is a more useful division of labor. Code handles exact rules and state. A decision model handles bounded judgments. The working agent handles the task. External permissions remain external permissions.

The starting point was [Jev Sentinel](https://github.com/shapor/jev-sentinel): compare a proposed action with the job the agent was actually given. gW generalizes that pattern beyond security research. The question is not simply “is this command dangerous?” It is “does this action belong in this task, under this policy, with this available evidence?”

The project is an open-source implementation of that idea, not a claim that one classifier can replace planning or guarantee good judgment. [TypeSafe's System One model](https://docs.typesafe.ai/concepts/system-one) is a useful fit for the decision interface; it is not a mandatory dependency.

## What it does today

| Concern | Implemented behavior | Important limit |
|---|---|---|
| Task focus | Compare tool actions with a pinned task; aggregate alignment observations into cumulative drift | Needs a configured classifier and a task; the supervisor does not see an entire hidden reasoning process |
| Repeated failures | Request review after consecutive failures of the same recorded action | Exact redacted fingerprints, not general loop detection |
| Tool efficiency | Recommend a matching registered executable when it is available | Does not silently substitute tools or execute the recommendation |
| Research before invention | Ask whether a proposed action lacks sufficient grounding | Advice based on supplied evidence; gW does not perform the research itself |
| Model choice | Filter arbitrary configured models by operation, modalities, capabilities, and availability, then apply preferences or classification | Native-harness and custom-adapter choices are plans, not automatically launched executors |
| Request efficiency | Optional JSON tool-result minification, pinned-task injection, and output-token caps | No arbitrary transcript rewriting; smaller requests are not proof of cheaper successful work |
| Reusable knowledge | Separate `gw-knowledge` package: source storage, search, exact reads, and revision-aware context caching | Local backend is keyword/structured, not vector search or automatic memory extraction |
| Learning from repetition | Record a candidate after repeated successful work | Does not generate, install, or promote code on its own |
| Governance integration | Local rules plus a replaceable external authority interface | Not an OS sandbox, enterprise identity system, or completed Warden integration |

These behaviors are configurable. “Stay on task” is a supplied goal, not a privileged rule hidden in the implementation. The current primitives are choice, metric, repetition, and registry evaluation. New goals can use those primitives without another supervisor class; new primitives still require code.

## How it fits together

```text
                              Your task and policy
                                      |
Agent tool hooks ---------------------+---------------- Model-gateway callback
                                      |
                               Shared gW engine
                                      |
                    rules / optional classifier / selection
                                      |
                    verdict + explanation + recorded state
                                      |
                              Host enforces verdict

Optional, separate: agent or application -> knowledge API/MCP -> source-backed context
```

Hooks and the optional [LiteLLM](https://docs.litellm.ai/docs/proxy/call_hooks) callback call the same runtime and selected plugins in their own processes. They share SQLite state; they do not need a gW daemon. `gw serve` is available for custom HTTP clients. LiteLLM remains the model gateway. [Caveman](https://docs.caveman.so/docs/proxy/litellm) can be a separately configured upstream compressor.

A proposed action receives one of four outcomes:

| Outcome | Meaning |
|---|---|
| `allow` | No gW objection. The host's normal permission checks still apply. |
| `advise` | Continue, with recorded advice; delivery to the agent depends on the adapter. |
| `approve` | Human review is required. Adapters without a supported approval prompt deny instead. |
| `deny` | Do not execute through this controlled path. |

A post-tool check cannot undo an action. gW does not claim otherwise. [Read the execution model](docs/ARCHITECTURE.md).

## First useful run

Inspect the installation and pin a concrete task in your project:

```bash
gw doctor
gw task 'Fix login validation and add regression tests. Do not deploy.' --project .
```

Start a **new** agent session, then run the [harmless denial check](docs/GETTING_STARTED.md#prove-that-the-hook-runs). A hook file on disk is not evidence that the agent loaded it.

```bash
gw status
```

This reports sessions, drift observations, usage received through instrumented calls, and proposed automation candidates. It is not a complete transcript or a live dashboard.

If you need model judgment, [configure a backend and opt in to one goal](docs/DECISION_SETUP.md#opt-in-to-a-semantic-goal). Backend setup alone does not turn on bundled semantic goals in the lean setup.

## Your policy, not our house rules

Configuration resolves from built-in defaults to global settings, a client override, a reviewed project snapshot, and a project-client override. A client here means an adapter identity such as `codex`, not a customer or a billing account.

A project might make alignment failures require review and stop exact retries sooner:

```json
{
  "version": 1,
  "goals": {
    "task_alignment": {"on_error": "approve"},
    "retry_limit": {"threshold": 2}
  }
}
```

Save that in the project's `.gw.json`, then review and import it:

```bash
gw trust --project .
```

It applies to new sessions. Existing sessions keep their task and policy snapshot. An agent editing `.gw.json` does not silently change its running policy. Global `locked` paths can prevent project overrides, but user-owned files are not a boundary against other processes running as you.

See [configuration](docs/CONFIGURATION.md) for complete merge semantics, exact rules, custom goals, examples, and counterexamples.

## Models are capabilities, not three price tiers

An image generator is not a cheap coding model. A decision model is not a chat model with shorter answers. A subscription-backed agent is not an API balance.

gW's registry represents identity, operations, input/output modalities, capability tags, execution path, billing, and declared availability separately. OpenRouter models, direct providers, local models, media generators, and native subscription-backed harnesses can coexist. Selection first removes incompatible candidates; your preferences choose among what remains.

```bash
gw models list
gw models select --operation decision --input text --output decisions
gw models select --operation image.generate --input text --output image
```

These commands select; they do not invoke the chosen model. The proxy can apply compatible aliases to intercepted requests. Other execution kinds need their own executor. Quota and availability are operator declarations, not live account monitoring. [Model contracts and examples](docs/MODELS.md).

## Knowledge that can leave with you

The optional [`gw-knowledge`](packages/gw-knowledge/README.md) distribution is independent of the supervisor. It has its own license, CLI, schemas, tests, and version. It imports nothing from `gw_supervisor`.

Its local implementation stores explicit source snapshots and an FTS5 index. A separate cache keeps bounded evidence packets, invalidated when the relevant corpus, source, index, or access state changes. Clearing the cache does not delete the documents. Knowledge remains evidence, not authority.

```bash
# After installing with --knowledge, run from a project containing README.md:
gw knowledge init
gw knowledge ingest README.md --id readme
gw knowledge context 'decision provider'
```

The same read contract supports a local provider or a cloud adapter. Standard [MCP](https://modelcontextprotocol.io/docs/learn/architecture) access is optional. No commercial provider is required; none is bundled as a turnkey integration. See [knowledge setup](docs/KNOWLEDGE.md) and the [adapter contract](packages/gw-knowledge/ADAPTERS.md).

## Who should use it—and who should not

Use gW when you own the workflow, can inspect its behavior, and want repeatable decisions around an agent without replacing the agent. It is also a reference implementation for developers exploring typed supervision, capability-first routing, and portable context reuse.

Do **not** rely on it as containment for an adversarial agent, a compliance certification, or an unattended credential/payment/legal-assent broker. It cannot control actions the host never exposes, make a vendor honor an unsupported hook, or force a model to stop refusing. It does not turn a prior approval in memory into present authorization.

A simple deterministic script may be the better tool for an already understood workflow. A native hook may be enough for one rule in one agent. gW is useful when sharing policy, state, and integration boundaries is worth the added component. [Security](SECURITY.md) · [FAQ](docs/FAQ.md).

## Context without a knowledge-store dependency

The independently installable [`gw-context`](packages/gw-context/README.md) package
combines task constraints, active skills, project files, session evidence and
optional retrieval results. It works without `gw-knowledge`, with its local/remote
provider, or with multiple third-party context sources at once.

The existing agent tool is still `gw_context_compile`. The agent-tools installer
includes the compiler; a knowledge-only installation remains independently usable.
Use the [compiler guide](docs/CONTEXT_COMPILER.md) for setup and the
[source adapter contract](packages/gw-context/ADAPTERS.md) for integrations. The
reference compiler makes no model calls and never silently drops required content.

## What the harness research taught us

The best evidence is for **bounded handoffs and verifiable source delivery**. The
studies do not establish that installing the full harness improves developer
productivity or lowers total cost.

| Finding | What it means for the setup |
|---|---|
| [Scope and continuity](docs/HARNESS_RESEARCH.md#scope-and-continuity): a scaffold improved AI-rated quality by 21.7 points across 64 staged episodes and preserved 20 handoffs versus none. | Keep a pinned task and a short, evidence-backed handoff when work resumes. Most milestones stopped at a resource guard; this was chiefly useful partial progress. |
| [Configured repository work](docs/HARNESS_RESEARCH.md#configured-repository-work): ordinary OpenCode delivered 4/4 accepted artifacts; configured nonsemantic gW delivered 2/4, with one failure and one missing capture. | Start with a small deterministic setup. A hook event or an available tool does not mean the worker used it. The context tool was never called in this cohort. |
| [Semantic gating](docs/HARNESS_RESEARCH.md#why-semantic-gating-is-opt-in): early supervised trials blocked some edits that passed the grader offline. | Keep model-based gating off by default. Enable a specific goal only after checking it against ordinary supporting work and providing a review path. |
| [Source-backed answers](docs/HARNESS_RESEARCH.md#source-backed-answers): early comparisons lost on quality; the final repair improved 8/12 to 10/12 with 26.1% more tokens. | Use source-backed context where the answer needs it. Verify the supporting span reached the worker and measure accepted answers as well as tokens. |
| [Overhead and caching](docs/HARNESS_RESEARCH.md#overhead-and-accounting): PR #1 removed duplicated output and unnecessary repeated work in controlled checks. | Keep dependency-aware reuse and recheck current authority. Cache hits, smaller payloads, and fixture speedups are not evidence of cheaper completed tasks. |

**Keep** exact rules and retry limits where they serve the workflow, one verified
native hook path, task and policy pinning, and compact evidence with provenance.
**Consider pruning** duplicate hooks and context injection, generic always-on
classifier or reviewer passes, and unused routing, knowledge, or learning
components. Enable them one at a time against a named failure and a measurable
quality threshold. Keep human authorization for consequential actions.

**Still open:** the fresh Jev/Clef diagnostic and the semantic OpenCode pilot were
prepared but never run. We still need to measure hook enforcement, natural context
uptake, false denials, accepted work, and total cost on fresh tasks before making
deployment or savings claims.

[Research write-ups and bounds](docs/HARNESS_RESEARCH.md) · [Curated evidence branch](https://github.com/davidjbeveridge/gw/tree/research/harness-performance/research/harness-performance) · [Benchmark protocol](docs/BENCHMARKS.md) · [Implementation validation](docs/VALIDATION.md)

## Read further

The design draws on [Jev Sentinel](https://github.com/shapor/jev-sentinel), [typed System One decisions](https://docs.typesafe.ai/concepts/system-one), [effective agent design](https://www.anthropic.com/engineering/building-effective-agents), and [retrieval-augmented generation](https://arxiv.org/abs/2005.11401). [RouteLLM](https://arxiv.org/abs/2406.18665), [Reflexion](https://arxiv.org/abs/2303.11366), and [Voyager](https://arxiv.org/abs/2305.16291) inform questions about routing and learning; gW does not claim to implement their methods or reproduce their results.

The [annotated references](docs/REFERENCES.md) connect each dependency, protocol, and research idea to the relevant part of the project. The [documentation index](docs/README.md) separates tutorials, explanations, reference material, and operating guides.

## Contributing

Fork the repository, work on a branch, and open a pull request with a reproducible example and the relevant tests. Especially useful contributions include verified native-harness versions, real workload evaluations, and knowledge adapters that pass the common contract tests. [Contribution guide](CONTRIBUTING.md).

MIT licensed. Local use does not require a gW account or a hosted service. The supervisor makes the call at its boundary. You decide where that boundary belongs.

## Operate GW through your agent

Opt in with `--agent-tools` to inspect a run, configure a decision backend, or
compile task context from the agent. Add `--plugins` for the dashboard or
`--knowledge` for a source store if needed. Native trust and restart
requirements remain explicit.

[Agent interface](docs/AGENT_INTERFACE.md) · [Fast/slow decisions](docs/DECISION_CASCADES.md) · [Context compiler](docs/CONTEXT_COMPILER.md)
