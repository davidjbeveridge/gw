# The gW handbook

[Project overview](../README.md) · [Source](../gw_supervisor/) · [Standalone knowledge package](../packages/gw-knowledge/README.md)

These documents describe **gW 0.6.0 and gw-knowledge 0.2.0**. Examples marked as runnable use those interfaces. Plans and research are kept separate from implemented behavior. Installation remains pinned to the published release; documentation updates on `main` do not move that tag.

## Start here

**New installation:** follow [Getting started](GETTING_STARTED.md), prove a harmless denial, then configure the [decision backend](DECISION_SETUP.md). Do not start by enabling every optional component.

**Evaluating the design:** read [Architecture and method](ARCHITECTURE.md), [Security](../SECURITY.md), and [Benchmarks](BENCHMARKS.md). These explain the boundaries as well as the intended benefits.

**Integrating another system:** use the [HTTP and Python API](API.md), [extension contracts](EXTENSIONS.md), and [native adapter guide](ADAPTERS.md). Knowledge adapters have their own [standalone contract](../packages/gw-knowledge/ADAPTERS.md).

## Guides

| Guide | What you will get |
|---|---|
| [Getting started](GETTING_STARTED.md) | An isolated trial, installation choices, a working denial check, and an update/removal path |
| [Decision setup](DECISION_SETUP.md) | TypeSafe, OpenRouter, local models, compatible gateways, credential references, and a synthetic connection check |
| [Proxy integration](PROXY.md) | LiteLLM setup, request correlation, supported transformations, Caveman, and streaming boundaries |
| [Knowledge setup](KNOWLEDGE.md) | Explicit ingestion, source-backed context, cross-agent reuse, remote adapters, and MCP |
| [Recipes](RECIPES.md) | Small working policies and common wrong approaches, with links to runnable examples |
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnose missing hooks, unavailable classifiers, route mismatches, stale knowledge, and setup errors |

## Concepts and reference

| Document | Scope |
|---|---|
| [Architecture and method](ARCHITECTURE.md) | Event processing, responsibility boundaries, state, and why the pieces are separate |
| [Configuration](CONFIGURATION.md) | Precedence, locks, rules, goal primitives, defaults, session pinning, and limitations |
| [Native adapters](ADAPTERS.md) | Installed locations, native events, approval/advice differences, and host verification |
| [CLI reference](CLI.md) | Every public command family, argument placement, side effects, and exit semantics |
| [API reference](API.md) | Event envelopes, verdicts, model interception, knowledge facade, authentication, and errors |
| [Model registry](MODELS.md) | Operations, modalities, execution kinds, selection policy, catalog import, and subscription boundaries |
| [Extension contracts](EXTENSIONS.md) | Decision, authority, inference, credential, and knowledge interfaces |
| [FAQ](FAQ.md) | Direct answers about behavior, economics, safety, portability, and deliberate omissions |

## Evidence and development

[Validation record](VALIDATION.md) documents executed checks. [Benchmark design](BENCHMARKS.md) describes the evidence required for efficacy and efficiency claims. [Annotated references](REFERENCES.md) explain the upstream work. [Roadmap](ROADMAP.md) distinguishes next steps from shipped features. [Contributing](../CONTRIBUTING.md) covers changes to code and prose.

[Runnable examples](../examples/README.md) use temporary state and require no model key. The [agent-readable index](../llms.txt) provides a compact map. The [setup skill](../skills/gw-setup/SKILL.md) is for agents helping an operator configure a decision backend; it does not authorize them to retrieve secrets.

## How to read the examples

A **configuration fragment** must be merged into the intended file; it is not a command to replace your entire policy. A **template** contains explicit placeholders for your model, path, or endpoint. A **runnable example** includes its prerequisites and expected behavior. A **counterexample** deliberately shows a mistake and is labeled as such.

References to an upstream capability do not mean the gW adapter supports every version of it. Likewise, protocol tests are not a live-model benchmark. Where support stops, the documentation says what remains the host's or operator's responsibility.

## Optional operational plugins

[Observability and run comparison](OBSERVABILITY.md) · [Learning](LEARNING.md) · [Sync](SYNC.md) · [Plugin contracts](PLUGINS.md)

## Agent-driven operation and context

[Agent tools and setup](AGENT_INTERFACE.md) · [Decision cascades](DECISION_CASCADES.md) · [Context compiler](CONTEXT_COMPILER.md)
