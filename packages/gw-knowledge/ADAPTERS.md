# Knowledge adapter contract v1

The **same required read interface** is used by local providers, remote services,
context assembly, CLI, MCP and GW. Backends are independently installable.

## Required Python protocol

```python
class KnowledgeProvider(Protocol):
    def capabilities(self) -> dict: ...
    def revision(self, scope: Scope) -> str | None: ...
    def search(self, request: SearchRequest) -> dict: ...
    def read(self, request: ReadRequest) -> dict: ...
```

`Scope(tenant, collection, principal)` is assigned by the trusted executor. Scope
fields are exact identifiers, never wildcards. A model must not choose its own
principal. A backend must enforce its authoritative access controls before
returning passages, source metadata, or search results.

Capabilities return `protocol: gw.knowledge/1`, stable `provider_id`, implemented
`search_modes`, `revision_tracking`, `writes`, `index_version`, and `optional_operations`. Optional
operations explicitly name put/delete/export/reindex where implemented. The
HTTP service does not advertise bulk export or index administration. Do not claim
vector/semantic support merely because you can run keyword search.

Revision tokens are opaque and scope-bound. If non-null they MUST change for
**any change that could affect results**, including new documents, ingestion,
metadata filters, index/embedding/ranking configuration, permission revocation,
deletes and expiration. A hash of the currently returned passages is not a corpus
revision. Return `None` if your backend cannot meet this promise. An adapter's
embedding model fingerprint, preprocessing and chunker version belong in index
revisioning. Do not reuse vectors across incompatible embedding models.

Search requests have `scope`, `query`, `mode`, scalar-equality `filters`, `limit`,
and optional `cursor`. Modes: keyword, structured, semantic, hybrid. Local
structured searches have an empty query; filters are exact JSON scalar equality
(`true`, `1` and `"1"` are distinct). Scores are backend-specific; report score_kind
and do not compare raw BM25/vector scores across providers. Pagination cursors
must bind to the query, scope and snapshot or explicitly fail after a change.

Search results contain `scope`, `revision`, `hits`, and `next_cursor`. A passage
contains `scope`, `document_id`, `revision`, `title`, `source`, `metadata`, `text`,
`start_char`, `end_char`, `start_line`, `end_line`, and `expires_at`; score fields
are optional. Ranges use **Unicode code points, start inclusive/end exclusive**,
and 1-based source lines. Return the exact source text, not an unmarked synthesis.
Do not fetch an arbitrary source URI on read; resolve the authorized document ID.

Read accepts an optional current revision and exact character range. A specified
revision MUST match, otherwise raise Conflict. Missing/inaccessible share NotFound.
Full historical revision storage is not required. If the backend cannot produce
exact passages with provenance, it cannot implement this read contract honestly.

## Optional capabilities

`MutableKnowledgeProvider`: put, delete, export. Put accepts DocumentInput and an
optional expected_revision. Create with none; differing updates require compare-
and-swap. Exact idempotent retries may succeed unchanged. Delete always requires
the current revision. `writes: false` is valid and must reject mutation. Export
is optional in remote implementations and may raise Unsupported explicitly.

`EmbeddingProvider`: fingerprint plus embed(texts). This is a backend component,
not part of every query and not automatically invoked by the local provider.

## Errors

Typed SDK errors map to wire codes: InvalidRequest/invalid_request,
NotFound/not_found, Conflict/revision_conflict, Unsupported/unsupported,
Unavailable/unavailable. Never turn a network or malformed response error into
an empty search or a cached success. Avoid including credentials, query text or
source content in external error messages.

## HTTP wire format

POST the following JSON to the explicitly configured endpoint:

```json
{"protocol":"gw.knowledge/1","method":"search","request":{"scope":{"tenant":"local","collection":"demo","principal":"owner"},"query":"decision failures","mode":"keyword","filters":{},"limit":8}}
```

Response: `{"protocol":"gw.knowledge/1","result":...}`. Error:
`{"protocol":"gw.knowledge/1","error":{"code":"revision_conflict"}}`.
The canonical JSON Schema is packaged under `gw_knowledge/schemas/contract-v1.json`;
load it with importlib.resources. Runtime validators also enforce relationships
that JSON Schema cannot express, such as scope equality and text/range lengths.
Unknown protocol versions and unsupported operations must fail explicitly.

The reference server uses POST `/v1/knowledge`, bearer auth, no redirects/CORS,
bounded bodies, and a host-bound scope. A production service can derive scope
from an authenticated identity, but MUST NOT trust the principal in request JSON
without checking it against that identity. A cloud adapter must also decide how
permission changes invalidate local context packets.

## Installed adapter discovery

Publish a Python distribution with an explicit entry point:

```toml
[project.entry-points."gw_knowledge.providers"]
mybackend = "mybackend.adapter:from_options"
```

`from_options(options: dict) -> KnowledgeProvider` should open the backend without
implicit crawling, source uploads, or model downloads. Then:

```python
from gw_knowledge.registry import open_provider
provider = open_provider("mybackend", {"endpoint": "https://example.test/kb"})
```

Only explicitly installed and selected plugins are loaded; an adapter is trusted
code. GW permits connection/plugin configuration only in global settings, never
an agent-writable project policy.

## Conformance

Subclass `ReadConformanceMixin` alongside unittest.TestCase. Trusted setUp must
provide `provider`, `scope`, `fixture_query`, and `fixture_document_id` referencing
a seeded visible text document. The mixin tests capabilities, revision behavior,
search/read consistency, and character-range reads without writing fixtures.
`check_provider(provider, scope, query)` is the equivalent read-only smoke.

Also run backend-specific tests for cross-scope isolation, revoked access,
expiration, index rebuilds, concurrent changes, malformed data and failures.
The reference suite runs the same read conformance tests against both SQLite and
a real HTTP service. Do not treat protocol compatibility as semantic retrieval
quality, authorization assurance, or production performance evidence.

## Referenced standards

- MCP tools/resources and SDK: https://modelcontextprotocol.io/specification/2026-07-28
- Official Python SDK: https://github.com/modelcontextprotocol/python-sdk
- SQLite FTS5: https://sqlite.org/fts5.html
- JSON Schema: https://json-schema.org/draft/2020-12

MCP is the standard agent transport. The backend interface is this project's
versioned open contract. No universal knowledge-store standard is asserted.
