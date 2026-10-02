# gW v0.5.0 — observability, learning and reviewed sync

Three independent, free MIT packages accompany the core: gw-observe 0.1.0,
gw-learning 0.1.0 and gw-sync 0.1.0. The existing knowledge package remains optional.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.5.0/install.sh | bash -s -- --all --plugins
gw trace init --baseline
gw trace serve --open
```

`--knowledge` adds the independent knowledge package. PowerShell supports
`-Plugins` and `-Knowledge`. Plugins are not silently enabled by installation.

## Included

- Deterministic per-goal auditing, proposed/directed drill-down and native delivery
  metadata, with uncertainty about host enforcement stated explicitly.
- Local source-referencing trace index, immutable run variables, explicit task
  outcomes, native Claude/Codex usage import, descriptive comparisons and dashboard.
- Standard OTLP/HTTP JSON export to existing compatible collectors.
- Measurement-only baseline mode with no classifier, policy or proxy changes.
- Learning plugins for repeated-tool and guidance proposals; explicitly configured
  research/expansion workers, lookback/modes, review and artifact history.
- Content-addressed harness bundles with local/HTTP providers, CAS channels,
  reviewed plans, conflict rejection and no automatic live activation.

Logging and visualization make no inference calls. Learning workers are separate,
explicit workloads and can incur their own provider costs. No causal savings,
automatic quality judgment, hidden activity reconstruction, subscription-dollar
allocation, enterprise access certification or benchmark orchestration is claimed.

CI gates publication on cross-platform/core/package checks, fresh installers,
independent package extraction, actual LiteLLM/MCP/schema checks, and browser E2E.
See docs/OBSERVABILITY.md, docs/LEARNING.md, docs/SYNC.md and docs/PLUGINS.md for
configuration, data ownership and support boundaries.
