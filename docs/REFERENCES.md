# References and prior art

[Handbook](README.md) · [Architecture](ARCHITECTURE.md) · [Benchmark plan](BENCHMARKS.md)

These links explain the technologies and ideas behind gW. They are not endorsements, performance evidence for this implementation, or a list of bundled integrations. Official documentation can change independently of a released adapter; test the version you run.

## Decisions rather than another reasoning loop

**[Jev Sentinel](https://github.com/shapor/jev-sentinel).** The direct starting point: score a proposed agent action against its assigned task. gW adopts the per-action supervisory pattern, not the cyber-specific taxonomy or the project's benchmark claims. Its own rules, goals, state, and non-cyber interfaces are separate implementation work.

**[TypeSafe System One](https://docs.typesafe.ai/concepts/system-one), [quickstart](https://docs.typesafe.ai/introduction/quickstart), and [Jev introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev).** The typed state/questions/answers contract motivates the decision-provider abstraction. gW consumes Choice labels and validates them. A provider's efficiency or calibration claim does not establish gW's workload performance, and typed output is not proof of correct judgment.

**[OpenRouter's TypeSafe SDK/System One guide](https://openrouter.ai/docs/guides/community/typesafe-sdk).** Documents the compatible routed endpoint and credential/model naming. This is distinct from an arbitrary chat endpoint. [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) informs the separate JSON-chat fallback protocol.

**[Kev](https://github.com/jaredpalmer/kev), [Laya](https://github.com/NandhaKishorM/laya), and [Laya-MLX](https://github.com/mizorewww/laya-mlx).** Examples of independently runnable typed decision systems. gW supplies compatible endpoint configuration where implemented; it does not bundle their weights or assert equal quality. Laya's HTTP server and the MLX runtime are distinct setup paths.

**[CUA-S1 forms](https://huggingface.co/cua-ai/cua-s1-forms).** An example of a specialist form-action model. It belongs in a capability-aware system, but the model card's task does not make it a general-purpose supervisor. gW requires an explicit appropriate bridge rather than inventing a universal CUA endpoint.

## Harness and tool boundaries

The native adapters are grounded in the relevant upstream contracts:

| Technology | Primary reference | Why it matters |
|---|---|---|
| Claude Code | [Hooks](https://code.claude.com/docs/en/hooks) | Lifecycle, permission decisions, additional context, settings scope |
| Codex | [Hooks](https://developers.openai.com/codex/hooks), [agent security](https://developers.openai.com/codex/enterprise/agent-security) | Supported events and the difference between a denial and hook failure |
| Gemini CLI | [Hook reference](https://geminicli.com/docs/hooks/reference/) | Native event/output shapes and host behavior |
| Cursor | [Hooks](https://cursor.com/docs/hooks) | Cursor-specific envelopes instead of assumed Claude compatibility |
| Copilot | [Hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference) | Tool events and permission result contract |
| VS Code | [Agent hooks](https://code.visualstudio.com/docs/agent-customization/hooks) | Editor host configuration and behavior |
| OpenCode | [Plugins](https://opencode.ai/docs/plugins/) | Classic plugin callbacks used by the current adapter |
| Agent Skills | [Overview and specification](https://agentskills.io/home) | Portable instructions and progressive resource access; universal loading optimization remains deferred in gW |

The [gW adapter guide](ADAPTERS.md) describes the narrower implemented subset. Vendor documentation alone does not prove a released gW adapter handles every new event.

## Model requests and economics

**[LiteLLM call hooks](https://docs.litellm.ai/docs/proxy/call_hooks) and [custom callbacks](https://docs.litellm.ai/docs/observability/custom_callback).** The integration surfaces for request inspection/modification and completed-call observation. gW adds policy around the gateway rather than rebuilding provider connectivity.

**[OpenRouter model catalog](https://openrouter.ai/docs/guides/overview/models).** The source for explicit-list catalog import. Discovered metadata is not proof of account access, live quota, or the execution path required for a particular operation.

**[Caveman's LiteLLM integration](https://docs.caveman.so/docs/proxy/litellm), [engine](https://docs.caveman.so/docs/proxy/engine), and [security model](https://docs.caveman.so/docs/proxy/security).** Relevant to optional compression and source recovery. Caveman is separately operated; gW's built-in JSON minifier is much narrower. No Caveman result is republished as a gW benchmark.

**[OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).** Explains why stable request prefixes matter. Provider computation reuse differs from gW's application-level context packets. The knowledge cache does not supply a portable KV cache across models.

## Knowledge, storage, and interoperability

**[MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture) and [official Python SDK](https://github.com/modelcontextprotocol/python-sdk).** The standard agent-facing tool/resource transport. `gw.knowledge/1` is the project's backend contract, not a competing claim of a universal industry knowledge-store API.

**[SQLite FTS5](https://sqlite.org/fts5.html).** The local reference index uses full-text search, exact source chunks, and conventional structured metadata filtering. Keyword search is not advertised as embeddings. [SQLite WAL](https://sqlite.org/wal.html) is relevant to local concurrent access and operational backup practices.

**[JSON Schema 2020-12](https://json-schema.org/draft/2020-12), [Python Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol), and [Python entry points](https://packaging.python.org/en/latest/specifications/entry-points/).** The basis for documented wire shapes, structural adapter interfaces, and explicitly installed plugin discovery. Passing a schema or structural protocol check does not prove backend authorization correctness.

**[LanceDB](https://docs.lancedb.com/) and [Alchemyst](https://getalchemystai.com/docs/llms.txt).** Examples of a richer retrieval backend and a managed knowledge platform that could sit behind an adapter. Neither is a bundled gW integration. Their indexing, synchronization, access controls, and operational behavior must be mapped and evaluated rather than assumed from a similar API name.

## Research and design reading

| Work | Relevant idea | Relationship to gW |
|---|---|---|
| [ReAct](https://arxiv.org/abs/2210.03629) — Yao et al. | Interleaving reasoning, actions, and observations | Context for the worker loop that gW surrounds; not a replacement worker implementation |
| [RouteLLM](https://arxiv.org/abs/2406.18665) — Ong et al. | Learning routing decisions from preference data | Relevant to evaluating cost/quality trade-offs; gW does not train or reproduce these routers |
| [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) — Lewis et al. | External retrievable knowledge alongside model parameters | Background for source-backed context; gW's local provider does not implement the paper's trained retriever/generator |
| [Reflexion](https://arxiv.org/abs/2303.11366) — Shinn et al. | Feedback retained as experience for later attempts | Relevant to future learning; current gW stores candidates and explicit knowledge, not this reflection pipeline |
| [Voyager](https://arxiv.org/abs/2305.16291) — Wang et al. | An expanding library of executable skills | Relevant to proposed deterministic-tool learning; generation and automatic promotion are not shipped |

**[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)** argues for understanding simple compositional patterns before adding framework complexity. **[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)** and **[effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)** provide useful context for bounded evidence, durable progress, and changing harness assumptions. These are design references, not evidence that gW reproduces another system's outcomes.

## Evidence discipline

Prefer a primary specification, source file, model card, or research paper over a secondhand capability claim. When a source describes a feature we have not implemented, label it as inspiration or a possible adapter. When a source publishes a benchmark, retain its setup and limitations rather than borrowing the number.

The same standard applies to this project. [Validation](VALIDATION.md) says which checks ran. [Benchmarks](BENCHMARKS.md) says what remains to be measured. A link should help a reader investigate a claim, not make the page look more scientific.
