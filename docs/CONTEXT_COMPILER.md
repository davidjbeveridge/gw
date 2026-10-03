# Compile the context the task needs

[Handbook](README.md) · [Agent tools](AGENT_INTERFACE.md) · [Knowledge](KNOWLEDGE.md)

Retrieval returns candidates. The compiler decides what belongs in a bounded
working context, preserves its provenance, and says what did not fit. It does not
make source text free to process or turn a saved instruction into authorization.

GW's reference compiler is deterministic and lives in the independently usable
`gw-context` package. It does not import GW, a knowledge store, or SQLite. It has no model calls. It leaves tool schemas, conversation
history, provider signatures and existing system instructions alone.

## Use it from the agent

Ask the agent to compile context for the task. `gw_context_compile` takes a task,
focused retrieval query, and optional relative paths to active skill files. It
returns the compiled text plus source revisions, exact ranges, selected items,
omissions, unavailable sources and budget accounting.

The one-shot tool does not permanently enable automatic injection. It can be
used by a native subscription-backed agent without redirecting that agent's
inference through a proxy. The agent consumes the returned tool evidence and can
read original sources where more detail is needed.

## Inputs and selection

| Input | Retention |
|---|---|
| Pinned or explicitly supplied task | Whole; compilation fails when the mandatory payload cannot fit |
| Configured task constraints | Required whole items |
| Required project files and active skill files | Whole, not machine-generated summaries |
| Optional project files | Exact bounded source chunks |
| Recent tool verdicts/outcomes for a bound session | Bounded metadata, not a copied transcript |
| Knowledge retrieval (optional) | Authorized source passages from the configured provider/cache |
| Installed context sources (optional) | Scoped evidence from one or several providers without requiring `gw-knowledge` |

The reference ranking orders required items first, then optional priorities,
lexical query overlap, and stable source identifiers. It deduplicates identical
source ranges and rejects conflicting revisions of the same source. It does not
claim that lexical overlap is semantic relevance. A semantic/hybrid knowledge
provider can supply better candidates through the existing retrieval interface.

Required content is atomic. A missing active skill or an insufficient mandatory
budget raises an error rather than quietly removing the instructions needed to
do the work. Optional omissions are reported with a reason and source identity.
No generated summary replaces an original passage without disclosure.

Source edits change the packet identity. Local file revisions are rechecked
before returning the result, so a detected edit during compilation aborts the
packet. This is not a distributed transaction across a changing filesystem and
remote knowledge service; each source's snapshot/retrieval contract still applies.

## Configuration and delivery

The agent can prepare/apply the desired configuration. The fields below are a
reference for adapter authors, not a requirement that the user write JSON:

```json
{
  "context_compiler": {
    "enabled": true,
    "max_chars": 12000,
    "project_files": ["README.md", "docs/architecture.md"],
    "required_files": [],
    "constraints": ["Do not deploy from this task."],
    "history_limit": 6,
    "knowledge": true,
    "knowledge_mode": "keyword",
    "knowledge_limit": 4,
    "delivery": "tools",
    "supervisor": false,
    "sources": {}
  }
}
```

`delivery: tools` leaves consumption explicit. `delivery: proxy` additionally
compiles evidence for compatible intercepted text requests and appends it as
source data in a user message. It does not rewrite tool definitions, arguments,
existing high-trust messages or signed/opaque provider state. Requests bound to
opaque provider continuation state are explicitly reported as skipped. Baseline
mode leaves payloads unchanged and refuses an explicit enrichment request.

`supervisor: true` supplies compiled evidence to task-goal decision calls. Its
budget is also bounded by the primary classifier's remaining configured input
capacity. Missing required context takes the normal abstention/error policy;
it does not result in a partial judgment presented as complete. Worker-model
selection remains a separate decision and is not automatically enriched by this
flag in the initial implementation.

When a direct MCP call has no bound native session, it includes the task and
project/knowledge evidence but does not guess which native history belongs to the
user. Automatic supervisor/proxy calls have an exact session ID and can include
its recent tool outcomes. No private session directory is scanned implicitly.

## Budget, privacy and tracing

The budget counts Unicode characters in the complete serialized task/items
payload, including item provenance. It is **not** a model-token count or a promise
that the full upstream prompt fits the model's context window. Original messages
and schemas remain outside this added packet's budget. Choose a budget that
leaves room for the worker's existing context and output.

File access is limited to explicitly configured relative text paths inside the
bound project, with size limits and symlink/escape checks. Common secret paths
are excluded, and detected secret-like content is rejected or omitted with an
explicit status. The heuristic is not complete DLP. Knowledge access uses the
provider's current scope/revision rules, not model-selected credentials.

The complete context packet is not persistently cached or stored as another
transcript. Knowledge retrieval can reuse its existing dependency-aware evidence
cache. That cache covers one provider's retrieval, not the final task/skills/history
packet. Any future whole-packet cache belongs to `gw-context` and must revalidate
scope, source revisions, live inputs, compiler settings and budget. Trace metadata records the packet ID,
selected source revisions/ranges, omissions and counts. The dashboard's Context
view shows compilation totals and evidence relationships; event detail contains
the selection record. Logging and the reference compiler make no inference calls. A selected external source may perform billable retrieval or embedding work; its costs are not inferred from the compiler's `model_calls: 0`.

## Independent API

```python
from gw_context import ContextItem, DeterministicContextCompiler

packet = DeterministicContextCompiler().compile(
    "Fix login validation without deploying",
    [ContextItem(
        id="testing-rule", kind="skill",
        content="Use a fixture database. Run the regression test before finishing.",
        source="project:skills/testing/SKILL.md", revision="reviewed-revision",
        required=True,
    )],
    query="login regression test",
    max_chars=4000,
)
print(packet["text"])
```

`ContextCompiler.compile(task, items, query, max_chars, scope)` is the provider-neutral
Python protocol. The `gw.context/1` packet carries exact source items, not vector
embeddings or a hard dependency on the GW supervisor. Another compiler can
implement the protocol, but must make its ranking, truncation, provenance and
inference behavior explicit. The GW reference adapter currently selects the
deterministic implementation; arbitrary worktree compiler plugins are not loaded.

## Limits worth testing

A large required skill may not fit. An optional chunk may be omitted even though
it would have helped. Keyword retrieval may miss a differently worded source.
A useful packet can increase input tokens while avoiding repeated research.
None of those trade-offs can be settled from a byte count alone. Use traced tasks
and independent completion criteria before claiming better outcomes or savings.

This is not the deferred universal tool/skill-loading optimizer. It does not
hide capabilities from the agent or shrink every native harness's initial prompt.
It supplies better organized, inspectable evidence at the integration paths GW
actually controls.

## Knowledge-independent installation and migration

The installer includes `gw-context` with `--agent-tools` (PowerShell `-AgentTools`).
Use `--context` / `-Context` to install only the context component alongside core.
The existing `--knowledge` / `-Knowledge` option installs both, preserving the
previous combined setup. None of these flags enables automatic retrieval or
injection. Third-party sources are installed/configured separately and never
selected merely because a package is present.

The agent tool remains `gw_context_compile`. Existing `context_compiler` settings,
project files, skill retention, proxy delivery and supervisor enrichment keep
their roles. No local knowledge database is opened unless the knowledge bridge is
explicitly enabled and used.

New Python imports use `gw_context`. `gw_knowledge.compiler` and the previous
package-root compiler names are compatibility aliases **when `gw-context` is
installed**. Importing `gw_knowledge` for storage/search does not import the compiler.
New compiler exceptions live under `gw_context` (`ContextError`, `InvalidRequest`,
`ContextBudgetExceeded`); use their public classes or documented error codes,
not knowledge-storage exception classes.

## Add a third-party source

A context source can use a managed knowledge API, an existing retriever, or an
in-memory collection. It implements `collect(ContextRequest) -> SourceResult`.
It does not have to implement the knowledge-store write/index/cache API. The
[standalone adapter guide](../packages/gw-context/ADAPTERS.md) specifies exact types,
limits, ownership and a complete installable offline example.

Configure sources globally or in a global client layer:

```json
{
  "context_compiler": {
    "knowledge": false,
    "sources": {
      "company-docs": {
        "provider": "your-installed-adapter",
        "options": {"key_env": "COMPANY_KNOWLEDGE_KEY"},
        "limit": 8,
        "on_error": "error"
      }
    }
  }
}
```

The provider name is an installed `gw_context.sources` entry point, not a module
path or a claim that this vendor adapter is bundled. `gw_setup_options` discovers
names without running them; managed plan/apply can configure those installed
sources. Project files cannot introduce sources or redirect their credentials.
Existing locks and setup revision checks still apply.

Several named sources can coexist. Namespaced provenance prevents providers with
the same document ID from colliding. The host supplies an opaque scope and checks
that the response matches it; adapters must still enforce real access against
their own principal and service. Returning the same scope string is not proof of
authorization. Sources cannot set `required` or `trust: host_instruction`.

Source failure stops compilation by default. `on_error: omit` explicitly allows
continuing while listing the unavailable source and error type. Raw vendor error
messages are not returned. Disabled sources do not run. Source implementations
own network deadlines, freshness and any model usage; synchronous compiler calls
do not supply a sandbox or an automatic timeout around arbitrary installed code.

The `sources` report contains collection status, revision and item count. Scope
is included in the compiled payload identity. `context.source` observations store
metadata only; they do not duplicate retrieved text or add inference calls.
