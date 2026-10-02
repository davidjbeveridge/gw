# Optional knowledge layer and context caching

[Handbook](README.md) · [Standalone package](../packages/gw-knowledge/README.md) · [Adapter contract](../packages/gw-knowledge/ADAPTERS.md) · [API](API.md)

GW v0.4 integrates **gw-knowledge v0.1**, an independently installable MIT package
under `packages/gw-knowledge`. It is not an answer cache, prompt/KV cache, or a
mandatory managed service. See the package's [standalone guide](../packages/gw-knowledge/README.md)
and [adapter contract](../packages/gw-knowledge/ADAPTERS.md).

## Install and enable

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.4.0/install.sh | bash -s -- --all --knowledge
gw knowledge init
```

PowerShell has the equivalent `-Knowledge` switch. The extra is opt-in; existing
core installations keep their dependency-free behavior. Neither installation nor
init uploads files, calls a model or connects to a cloud. `init` enables global
local storage and explicit writes; `--read-only` prevents writes.

```bash
gw knowledge --project /path/to/project ingest /path/to/architecture.md --id architecture
gw knowledge --project /path/to/project search 'provider failure'
gw knowledge --project /path/to/project context 'provider failure'
gw knowledge --project /path/to/project read architecture
gw knowledge --project /path/to/project check --query provider
```

Place `--project` and `--client` **before** the operation. Default project is the
current repository. All harnesses on the same configured project share knowledge
and valid context packets. Different projects get isolated collection IDs by
default. Use `gw knowledge --project PATH init --collection team-project` to bind
a stable name for cross-machine/shared use. Explicitly sharing a collection also
shares its knowledge among clients with the configured principal.

Sources are explicit snapshots, not live filesystem mounts. Re-ingest changes
with `--expected-revision REV`; no silent overwriting or source synchronization.
The current reference provider stores UTF-8 text and metadata, not PDF parsing or
arbitrary binary uploads. Findings can also be saved with the Python API or the
opt-in MCP knowledge_store tool, with a source and provenance metadata.

## Backend and cache config

Global `knowledge` configuration defaults:

```json
{"knowledge":{"enabled":false,"provider":"local","options":{},"tenant":"local","principal":"owner","collections":{},"allow_writes":false,"cache":{"ttl_seconds":300,"max_entries":256,"max_bytes":16777216,"allow_unversioned":false}}}
```

Local sources live under `$GW_HOME/knowledge/sources`; disposable packets under
`$GW_HOME/knowledge/cache`. `options.directory` can move local sources to another
disk. Global client overrides and locks apply. Project files cannot change these
connection, storage, principal or cache settings; project goals remain separate.
Config changes affect new knowledge operations; existing supervisor decision
sessions continue using their pinned policies as before.

For a self-hosted/cloud provider implementing the standard package contract:

```json
{"endpoint":"https://knowledge.example/v1/knowledge","key_env":"KNOWLEDGE_API_KEY"}
```

Save that as an operator-controlled options file, then:

```bash
gw knowledge init --provider http --options provider.json
```

Remote writes remain off unless `--allow-writes` is explicitly provided. Backend
setup is not a live compatibility or account-access check. Run `check` against
the actual service afterward. An arbitrary Alchemyst/LanceDB/vendor API needs an
adapter; no commercial backend is bundled or required. Install a plugin under
the `gw_knowledge.providers` entry-point group for other native integrations.

`gw knowledge cache-clear` evicts only the current scope's packets. `export`
produces JSONL owner-visible sources; `restore FILE` imports those explicit
records without silently changing differing existing sources. `reindex` rebuilds
the local provider's derived FTS index. It is a store-wide administrator operation.

## Agent and HTTP access

No automatic prompt injection or transcript storage was added. Access is explicit
through CLI, Python/HTTP, or MCP. Retrieved text stays evidence, never policy.

Install `mcp>=1.12,<2` into GW's environment to enable the optional official SDK
transport, then configure your MCP-capable harness to run:

```json
{"mcpServers":{"gw-knowledge":{"command":"/absolute/path/to/gw","args":["knowledge","--project","/absolute/project","mcp"]}}}
```

Scope and principal come from trusted GW configuration, not model-supplied tool
arguments. MCP is read-only by default. `mcp --writable` exposes knowledge_store
only when `knowledge.allow_writes` also permits it. Documents do not grant
permissions; native/enterprise authority remains the executor's responsibility.
The tool/skill deferred-loading project remains out of scope.

`gw serve` exposes an authenticated facade at POST `/v1/knowledge`:

```json
{"context":{"project":"/absolute/project","client":"codex"},"method":"context","request":{"query":"provider failure","max_chars":8000}}
```

The facade assigns scope and refuses a scope in `request`. It derives the
collection and principal from global configuration and the supplied existing
project path. An authenticated local caller can choose that project path; this
is not a project allowlist or enterprise identity boundary. For the independent
`gw.knowledge/1` wire contract instead, run `gw-knowledge ... serve`, which binds
one scope at startup.

## What is implemented

Independent package, read/mutation protocols, JSON Schema, local SQLite/FTS5
provider, HTTP adapter/reference service, optional real MCP tools/resources,
source revisions and optimistic writes, exact ranges/provenance, structured
filters, scope/reader checks, portable source export, context packets with TTL/LRU
and dependency invalidation, entry-point discovery and reusable conformance tests.

Not included: local vector search/embedding generation, commercial adapters,
enterprise source connectors/synchronization, automatic summaries/learning,
policy decisions from memory, or universal automatic context injection. Other
providers can implement semantic/hybrid modes; the local provider honestly
advertises keyword and structured only. No paid inference or managed-service
account was used in validation. No savings/quality/scale benchmark is claimed.
