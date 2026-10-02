# gw-knowledge

**Portable knowledge adapters and dependency-aware context caching.** Independent
of GW, any agent harness, model provider, or commercial service. MIT licensed.

Python 3.10+, standard library only for the core. SQLite must include FTS5.
Package version: **0.2.0**. Adapter protocol: **`gw.knowledge/1`**.

## Install independently

From this directory, or a standalone source archive:

```bash
python -m pip install .
gw-knowledge --version
```

From the GW release (no GW supervisor installation required):

```bash
python -m pip install 'https://github.com/davidjbeveridge/gw/archive/v0.6.0.zip#subdirectory=packages/gw-knowledge'
```

A separate `gw_knowledge-0.2.0-py3-none-any.whl` and standalone source ZIP are
published with GW v0.6.0. No PyPI publication is implied. Copy this directory to
another repository and build it unchanged: it has its own package metadata,
license, documentation, tests, CLI, schemas, and conformance helpers. It imports
nothing from `gw_supervisor`. Both packages can evolve independently.

## Use

```bash
gw-knowledge --store ./knowledge --collection demo ingest README.md --id readme
gw-knowledge --store ./knowledge --collection demo search 'adapter contract'
gw-knowledge --store ./knowledge --collection demo context 'adapter contract'
# Repeat context: a valid packet is reused without repeating search/extraction.
gw-knowledge --store ./knowledge --collection demo check --query adapter
```

`ingest` explicitly copies one UTF-8 source file. This does NOT watch/synchronize
its original path or crawl its source URI. Re-ingest after changing the source.
Exact repeated ingestion is idempotent. A differing update requires
`--expected-revision REV`; deletion requires `--revision REV`. Read the current
revision using `read ID`. Old revisions fail explicitly; the reference provider
is a current-version store, not an unlimited history archive.

Metadata is a bounded object of JSON scalar values:

```bash
gw-knowledge --store ./knowledge ingest README.md --id design --metadata '{"kind":"architecture"}'
gw-knowledge --store ./knowledge search --mode structured --filters '{"kind":"architecture"}'
gw-knowledge --store ./knowledge export > sources.jsonl
gw-knowledge --store ./restored restore sources.jsonl
```

Export contains owner-visible authoritative documents and metadata, not caches.
Restore is streaming and idempotent, but is not an atomic whole-corpus batch: a
later conflicting record does not undo earlier imports. Reindexing is explicit
(`reindex`). Clearing/evicting cached context never deletes original documents.

## Architecture

```
knowledge sources -> provider search/read -> bounded evidence packet
      |                 |                       |
 durable store      derived indexes        disposable cache
```

The local provider stores authoritative text and metadata in a transactional,
on-disk SQLite database. FTS5 chunks are a derived index rebuilt from those
originals. This intentionally avoids a second blob store and its transaction/GC
complexity. The context cache is a separate SQLite database, with independent
TTL, LRU entry and logical-byte limits.

### Python API

```python
from gw_knowledge import (
    LocalKnowledgeProvider, ContextCache, Scope, DocumentInput, SearchRequest,
)

scope = Scope(tenant="local", collection="gw-project", principal="owner")
with LocalKnowledgeProvider("./knowledge") as provider:
    receipt = provider.put(scope, DocumentInput(
        document_id="architecture", title="Architecture decision",
        text="Decision failures use the configured per-goal error policy.",
        source="file:///project/docs/architecture.md",
        metadata={"kind": "decision", "verified": True},
    ))
    with ContextCache("./context-cache") as cache:
        packet = cache.assemble(provider, SearchRequest(scope, "decision failures"),
                                max_chars=8000)
        # Present packet["evidence"] as source data, not as system instructions.
```

The caller assigns trusted scope/principal and controls whether any evidence is
supplied to a model. The library performs no inference, automatic summarization,
transcript capture, prompt injection, authorization decisions, or model routing.
A metadata value `verified: true` is the writer's assertion, not certification.

## Adapter interface

See [ADAPTERS.md](ADAPTERS.md) and packaged
[`schemas/contract-v1.json`](src/gw_knowledge/schemas/contract-v1.json).

`KnowledgeProvider` has four required read operations: `capabilities`, `revision`,
`search`, and `read`. `MutableKnowledgeProvider` adds optional writes/deletes and
export. The HTTP adapter explicitly reports unsupported bulk export. A read-only
knowledge system is a first-class backend. `EmbeddingProvider` is an optional
component interface; it is not a mandatory call to a cloud model.

Search is text-query-first. Modes are `keyword`, `structured`, `semantic`, and
`hybrid`; backends advertise which they implement. **Local v0.1 implements only
keyword and structured search.** It never labels keyword matches semantic search.
Plug in a vector/hybrid engine behind the same interface; no vector database,
embedding download, or commercial API is required. No LanceDB/Alchemyst-specific
adapter is claimed in this release.

### Remote provider

```python
from gw_knowledge.http import HttpKnowledgeProvider
provider = HttpKnowledgeProvider(
    "https://knowledge.example/v1/knowledge", key_env="KNOWLEDGE_API_KEY",
)
```

This endpoint must implement the published contract. An arbitrary vendor API is
not automatically compatible. Use a small Python or HTTP bridge for that vendor.
Credentials are environment/private-file references; never include tokens in
endpoint URLs. HTTPS is required except on loopback. Redirects are refused.

A CLI provider-options file can contain:

```json
{"endpoint":"https://knowledge.example/v1/knowledge","key_env":"KNOWLEDGE_API_KEY"}
```

```bash
gw-knowledge --provider http --options provider.json --collection demo search 'topic'
```

To test self-hosting, provision a private `GW_KNOWLEDGE_SERVER_TOKEN` outside chat:

```bash
gw-knowledge --store ./knowledge --collection demo serve --port 7788
```

The reference service binds loopback and fixes tenant/collection/principal at
startup. The token does not grant the caller permission to choose another scope.
Reads are default; `--writable` explicitly enables writes. Off-machine hosting
requires a proper TLS/identity layer. This is not a turnkey multi-tenant cloud.

### Standard MCP access

Install the optional official Python SDK transport:

```bash
python -m pip install '.[mcp]'
gw-knowledge --store ./knowledge --collection demo mcp
```

For installed wheels, install the wheel with the `mcp` extra or install
`mcp>=1.12,<2` in the same environment. Start with stdio; there is no new public
port. Tools are `knowledge_search`, `knowledge_read`, and `knowledge_context`;
resources use `knowledge://documents/{document_id}/{revision}`. The exact read
tool also supports IDs that are inconvenient in a resource URI. `--writable`
adds `knowledge_store`, not arbitrary filesystem access or privilege changes.

Example MCP client configuration (adapt the host's config location, not the
server protocol):

```json
{"mcpServers":{"knowledge":{"command":"gw-knowledge","args":["--store","/absolute/knowledge","--collection","demo","mcp"]}}}
```

MCP is the industry protocol here. `gw.knowledge/1` is the project's documented,
versioned backend contract, not a claimed industry-wide knowledge standard.

## Cache validity

Cache keys include provider identity, scope/principal, complete search request,
index version, assembler version, corpus revision and evidence budget. Local
scope revisions change on additions, edits, metadata/reader changes, deletions,
expiration and index rebuilds. New documents invalidate cached retrieval even
when earlier matching documents are unchanged; empty searches are invalidated too.

A versioned hit checks the backend revision before returning evidence. Backend
failure never returns a stale packet. Assembly checks revisions before/after and
reads exact source ranges, retrying at most three times on concurrent changes.
The cache trusts a provider's promise that revisions cover ACL/index changes;
that promise must be implemented and tested by adapter authors.

Backends with no revision token are **not cached by default**. Explicit
`allow_unversioned=True` permits bounded TTL reuse but re-reads every source on a
hit to revalidate access/version/content. New documents can be missed until TTL
expiry in that mode; the result is labeled accordingly. No stale-on-error mode.

`max_chars` bounds the serialized `evidence` array, including provenance. It is
Unicode characters, not tokens or total HTTP response bytes. Clipped passages
retain exact character offsets and source revisions; metadata is never silently
dropped to squeeze in more text. The result says `truncated`. No savings or
retrieval-quality percentage is claimed without workload evaluation.

## Security and limitations

All content, including cached content, is untrusted evidence—not instructions,
policy or standing approval. The local provider defaults each document to its
owner; SDK readers can be explicitly added. Reads/search filter access before
returning content; only the owner can change/delete/export. Scope is a host
assertion, not a workload identity attestation. Same-user processes can edit the
files, so this is not an enterprise security boundary or encrypted vault.

Storage/cache directories are user-private on Unix. Windows needs user-only
ACLs managed by the operator. Deleted/evicted data is logically inaccessible via
the provider; database free pages, WALs and backups are not cryptographically
erased. A document delete does not guarantee immediate physical erasure of every
old cached copy. Source revisions prevent serving those copies; use cache-clear
and manage backups/retention where deletion obligations require it.

No PDF/OCR parsing, enterprise connectors, source syncing, generative summaries,
vector index, Alchemyst integration or cloud SLA is included. Local storage is
on disk with bounded chunks, but large-corpus throughput has not been benchmarked.

## Test independently

```bash
python -m pip install .
python -m unittest discover -s tests -v
# Additional actual-MCP and JSON Schema checks:
python -m pip install '.[mcp]' jsonschema
python -m unittest discover -s tests -v
```

CI additionally copies this directory out of the GW repository, builds/installs
its wheel without GW, and executes the tests from outside the repository. Adapter
authors can reuse `gw_knowledge.conformance.ReadConformanceMixin` and the read-only
`check_provider()` smoke; passing is not a retrieval or security audit.

## Context compiler (0.2)

`gw_knowledge.compiler.ContextCompiler` is a standalone protocol. The bundled
`DeterministicContextCompiler` ranks exact `ContextItem` values, preserves required
items whole, rejects conflicting source revisions, and returns a bounded
`gw.context/1` packet with provenance and omissions. No model call, generated
summary or tool-schema pruning is performed. See the compiler module and
`tests/test_compiler.py` for independently runnable examples.
