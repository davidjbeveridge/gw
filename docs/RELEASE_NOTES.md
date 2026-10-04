# GW v0.8.1 — fix measured cache and context overhead

- Per-goal exact decision caching now uses declared dependencies for both the
  provider request and key. Compatible misses are batched; custom goals retain
  full state unless an explicit contract is supplied. Cached labels are not
  cached authority, and metric checks still run every time.
- Agent context delivery no longer includes the same content as both `payload`
  and `text`. Detailed omission diagnostics are explicit. The SDK stays compatible.
- Warm runtimes reuse loaded plugin compositions, and hook delivery runs within
  the same scope. Repeated package-metadata parsing and redundant default copying
  are removed. History and cache-expiry queries have additive SQLite indexes.
- The reference bundle is v0.1.1. Restart agents/MCP and start fresh sessions when
  upgrading; no existing release tag or source document is changed.

The regression tests cover exact dependencies, task/source/model/scope changes,
partial batch failures, custom rubrics, duplicate delivery, authority revalidation,
SDK/agent/proxy representations, configuration changes, metadata reads and indexes.
No live model or productivity benchmark is claimed. Larger-scale knowledge-cache
and frontier-agent comparisons remain separate experiments.
