# Context source and compiler contracts

[Package overview](README.md)

The source contract supplies evidence. The compiler contract selects and arranges
it. Neither requires the other to own a database, embedding model, or agent runtime.
These are versioned project interfaces, not an industry-wide retrieval standard.

## A complete source

```python
from gw_context import ContextItem, ContextRequest, SourceResult

class CompanyDocs:
    def __init__(self, client):
        self.client = client

    def collect(self, request: ContextRequest) -> SourceResult:
        # The client binds credentials/tenant and enforces access independently.
        # search_authorized is an illustrative vendor adapter method, not a GW API.
        hits = self.client.search_authorized(request.query or request.task, limit=request.limit)
        items = tuple(ContextItem(
            id=hit.id, kind="knowledge", content=hit.text,
            source=hit.source_uri, revision=hit.revision, start_char=hit.start_char,
        ) for hit in hits)
        return SourceResult(items=items, scope=request.scope, revision=None)
```

The example assumes a client with the shown fields; adapt the real vendor's API.
An actually installable, no-network fixture is supplied in the parent repository
under `examples/context-source`. It requires only `gw-context`, not `gw-knowledge`.

## Request and result

`ContextRequest` contains a nonempty `task`, host-bound `scope`, optional `query`,
and requested `limit` (1–256, default 16). Scope is an opaque isolation key, **not an
authentication token**. Hosts select the scope; models do not select provider
credentials, tenants or principals through this contract. Adapters must enforce
real access before returning text. Echoing the scope does not establish access.

`SourceResult` contains a tuple of typed `ContextItem` objects, matching `scope`,
and an optional corpus `revision`. A missing revision stays unknown. Do not label
a hash of returned hits as a corpus revision: that cannot invalidate an empty
result when a new relevant document appears. The result is bounded to 256 items
and two million content characters; the request's smaller item limit also applies.
Adapters own network deadlines and provider-side pagination/budgets.

`ContextItem` fields are `id`, `kind`, `content`, `source`, `revision`, `required`
(default false), `priority` (0–1000; smaller is earlier), `start_char` (default 0),
and `trust` (default `evidence`). `end_char` is derived from content length. Use a
real source version or a content hash for an immutable passage; do not invent a
provider-supplied revision. This is provenance, not a promise that it is current.

`collect(source, request, namespace=...)` validates the result and namespaces
item/source identities so unrelated providers do not collide. It rejects scope
mismatch, over-limit results, and any source item with `required=True` or trust
other than `evidence`. Only the host supplies mandatory instructions directly to
the compiler. The source cannot promote itself by placing instructions in text.

## Package an adapter

An installed package registers a factory:

```toml
[project.entry-points."gw_context.sources"]
company = "company_context:from_options"
```

The factory takes one options dictionary and returns an object implementing
`collect`. An optional `close()` releases clients/resources after collection.
`open_source(name, options)` selects exactly one installed entry point; missing
or duplicate names are errors. It does not support arbitrary file/module paths.
`installed_sources()` lists names without importing or running provider code.
Factories and plugins are trusted operator-installed code, not sandboxed workers.

Options should contain credential references such as `key_env`, not credentials.
Actual provider endpoints/protocols are the adapter's responsibility. This package
does not pretend that every REST or MCP server already implements this contract.

## Pure compiler

`ContextCompiler.compile(task, items, *, query="", max_chars=16000, scope="")`
returns a packet. The reference implementation is `DeterministicContextCompiler`.
It makes no calls to `ContextSource`, performs no provider discovery, and stores
nothing. The host assembles its own items and the validated source items first.

The packet contains `protocol`, `id`, `payload`, `text`, `compiled_chars`,
`max_chars`, `selected`, `omitted`, `ranking`, `model_calls`, and `budget_unit`.
The optional nonempty scope is included in payload/identity. `text` is canonical
JSON of payload. Context-source reports are added by the host, not guessed by the
compiler. Host selection and delivery remain outside this package.

`ContextError` is a ValueError base. `InvalidRequest` uses `code: invalid_request`;
`ContextBudgetExceeded` uses `code: context_budget_exceeded`. Required-content loss,
invalid values and conflicting source versions fail rather than quietly weakening
instructions. Optional budget omissions are explicit. Error classes are context
errors, not knowledge-storage errors.

## Failure, freshness and costs

GW fails a source by default. The operator can explicitly permit omission and
receive an unavailable-source report instead. Arbitrary vendor exception text is
not suitable for logs; retain error categories and authorized provenance only.
The source's own freshness and access guarantees govern its result. Compilation
cannot make independently read sources a distributed atomic snapshot.

There is no final-packet cache in this release. A source may cache retrieval under
its own contract, but must still respect request scope and current access. The
compiler's zero-model-call counter covers compilation, not billable embeddings,
retrieval or inference inside a selected adapter. Observability should measure
those source operations separately without duplicating the source text.
