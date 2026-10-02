# gW

## Install

**macOS or Linux · Python 3.10+**

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.6.0/install.sh | bash -s -- --all --agent-tools --plugins --knowledge
```

**Star this repository** using GitHub's **Star** button if the project is useful. **[Fork it](https://github.com/davidjbeveridge/gw/fork)** to try your own policies, adapters, and experiments. Contributions with reproducible results are especially welcome.

The installer adds user-level hooks for Claude Code, Codex, Gemini CLI, Cursor, Copilot/VS Code, and OpenCode's classic plugin API. It preserves unrelated settings and backs up changed files. It does not install those agents, change their authentication, redirect their inference, or grant permissions. Restart your agents afterward; in Codex, review and trust the hooks through `/hooks`.

<details>
<summary>Windows, optional knowledge support, and installation without a shell pipe</summary>

Windows PowerShell, with Python 3.10+ on PATH:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/davidjbeveridge/gw/v0.6.0/install.ps1))) -All
```

Add the independent knowledge package on macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.6.0/install.sh | bash -s -- --all --knowledge
```

On Windows, add `-Knowledge`. Neither option installs an embedding model or connects to a cloud knowledge service.

Prefer to inspect the installer first?

```bash
curl -fsSLo gw-install.sh https://raw.githubusercontent.com/davidjbeveridge/gw/v0.6.0/install.sh
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

> **Current scope:** gW 0.6 is a prerelease for cooperative, user-controlled workflows. The core works without a model key; semantic supervision is **off until configured**. There is no published gW efficacy or cost benchmark yet. See [what is tested](docs/VALIDATION.md), [what is planned](docs/ROADMAP.md), and the [security model](SECURITY.md).

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

Hooks and the optional [LiteLLM](https://docs.litellm.ai/docs/proxy/call_hooks) callback call the same Python library in their own processes. They share SQLite state; they do not need a gW daemon. `gw serve` is available for custom HTTP clients. LiteLLM remains the model gateway. [Caveman](https://docs.caveman.so/docs/proxy/litellm) can be a separately configured upstream compressor.

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

Then configure the **supervisor's decision backend**, separately from the model doing the work:

```bash
gw setup
```

For an already provisioned OpenRouter key:

```bash
gw setup --preset openrouter --check --yes
```

That explicit check sends one synthetic request before saving. It does not send your project or prove task-alignment accuracy. Other presets cover TypeSafe direct, local Kev/Laya servers, System One-compatible proxies, JSON chat classifiers, and custom bridges. The [decision setup guide](docs/DECISION_SETUP.md) explains credentials, model limits, and why CUA form models are not general-purpose drop-in supervisors.

Start a **new** agent session, then run the [harmless denial check](docs/GETTING_STARTED.md#prove-that-the-hook-runs). A hook file on disk is not evidence that the agent loaded it.

```bash
gw status
```

This reports sessions, drift observations, usage received through instrumented calls, and proposed automation candidates. It is not a complete transcript or a live dashboard.

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

## Evidence before percentages

The repository has cross-platform tests, installer checks, a real LiteLLM callback suite, and independent-package/MCP tests. Those establish specific implementation behavior. They do not establish that gW makes arbitrary agent work cheaper, faster, or more accurate.

There are **no published gW performance benchmarks yet**. The [benchmark plan](docs/BENCHMARKS.md) defines paired baselines, quality gates, overhead accounting, failure cases, and the artifacts needed to publish a result. Until then, no borrowed vendor percentage stands in for a gW measurement.

[Validation record](docs/VALIDATION.md) · [Current CI](https://github.com/davidjbeveridge/gw/actions/workflows/ci.yml).

## Read further

The design draws on [Jev Sentinel](https://github.com/shapor/jev-sentinel), [typed System One decisions](https://docs.typesafe.ai/concepts/system-one), [effective agent design](https://www.anthropic.com/engineering/building-effective-agents), and [retrieval-augmented generation](https://arxiv.org/abs/2005.11401). [RouteLLM](https://arxiv.org/abs/2406.18665), [Reflexion](https://arxiv.org/abs/2303.11366), and [Voyager](https://arxiv.org/abs/2305.16291) inform questions about routing and learning; gW does not claim to implement their methods or reproduce their results.

The [annotated references](docs/REFERENCES.md) connect each dependency, protocol, and research idea to the relevant part of the project. The [documentation index](docs/README.md) separates tutorials, explanations, reference material, and operating guides.

## Contributing

Fork the repository, work on a branch, and open a pull request with a reproducible example and the relevant tests. Especially useful contributions include verified native-harness versions, real workload evaluations, and knowledge adapters that pass the common contract tests. [Contribution guide](CONTRIBUTING.md).

MIT licensed. Local use does not require a gW account or a hosted service. The supervisor makes the call at its boundary. You decide where that boundary belongs.

## Operate GW through your agent

Install with `--agent-tools --plugins --knowledge`, then ask your agent to open
the dashboard, inspect a run, configure a decision cascade, or compile task context.
The agent uses GW tools rather than asking you to type commands or JSON. Native
trust/restart requirements remain explicit.

[Agent interface](docs/AGENT_INTERFACE.md) · [Fast/slow decisions](docs/DECISION_CASCADES.md) · [Context compiler](docs/CONTEXT_COMPILER.md)
