# gw v0.4.0 — pluggable knowledge and context caching

Adds **gw-knowledge 0.1.0**, a separate MIT-licensed distribution. It has no GW
imports and can be copied, built and installed independently. The release includes
both wheels and a standalone knowledge source archive.

## Included

- Provider-neutral `gw.knowledge/1` contract, typed Python protocols, packaged
  JSON Schema, installed-adapter entry points and reusable conformance tests.
- SQLite/FTS5 local sources and indexes, keyword and structured search, exact
  source ranges/provenance, explicit ingestion/export, revisions and CAS updates.
- Context packets with scope/principal-aware keys, source/index/corpus/ACL
  invalidation, bounded TTL/LRU, and no stale-on-error or answer replay.
- HTTP adapter and scope-bound reference service for self-hosted/cloud bridges.
- Optional standard MCP tools/resources through the actual Python SDK.
- GW CLI/API integration; no automatic transcript capture or context injection.

## Install

Python 3.10+, macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.4.0/install.sh | bash -s -- --all --knowledge
gw knowledge init
gw knowledge ingest docs/CONFIGURATION.md --id configuration
gw knowledge context 'decision provider'
```

Use a source file that exists in your project. The PowerShell installer supports
`-Knowledge`. Existing installation without the switch remains dependency-free.
See docs/KNOWLEDGE.md and packages/gw-knowledge/README.md for standalone/MCP setup.

## Validation and boundaries

CI gates publication on the existing six OS/Python combinations, fresh installers
on all three OSes, real LiteLLM tests, and a new independent-package job. That job
extracts the knowledge package outside the repository, builds/installs its wheel
without GW, and tests actual MCP stdio and JSON Schema contracts. No managed
provider accounts, paid model inference or production-scale benchmarks are used.

The local provider implements keyword/structured search, not vector embeddings.
Semantic/hybrid backends can implement the same interface. No commercial vendor
adapter, enterprise synchronization, generative memory extractor, automatic prompt
injection or policy authority from stored knowledge is claimed. Remote services
must implement the wire contract or supply an adapter. Scope is host-bound, not
an enterprise identity attestation; local files are not encrypted/tamper-proof.
