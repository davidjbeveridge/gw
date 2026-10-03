# Working on gW

Start with [the handbook](docs/README.md), [the agent-readable index](llms.txt), and
[Contributing](CONTRIBUTING.md). Read current source before changing a contract.
Package versions and published tags are separate from documentation revisions.

For core classifier setup, use [the setup skill](skills/gw-setup/SKILL.md) and
[DECISION_SETUP.md](docs/DECISION_SETUP.md). `gw setup --describe` is a no-network
manifest. Worker-model configuration is a different concern. Never request raw
keys in chat or inspect unrelated credential stores.

For knowledge work, keep [gw-knowledge](packages/gw-knowledge/README.md) independently
buildable. It must not import the supervisor. The [adapter contract](packages/gw-knowledge/ADAPTERS.md)
and packaged schema are authoritative for that interface. MCP is the standard
agent-facing transport; the backend contract is project-defined and versioned.

Run the relevant tests before proposing changes:

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s packages/gw-knowledge/tests -v
```

Optional integrations need their real dependencies in the corresponding tests.
Native fixtures are not live-agent proof. Do not weaken protocol checks, native
permissions, or existing tests to make a new backend appear supported. Keep
network requests, downloads, source ingestion, and mutations explicit.

Documentation must distinguish shipped behavior, templates, and future work.
Run the documentation checks and offline examples described in CONTRIBUTING.md.
Do not invent benchmark results or copy vendor savings claims into gW results.

For context work, keep `packages/gw-context` independently buildable without
`gw-knowledge`, GW core or SQLite. Source contracts belong there; the core owns
source selection and delivery. Preserve the `gw_context_compile` agent tool.
Run its package tests and `tests/test_context_independence.py`, including a clean
installation with core + context + the explicit fixture source but no knowledge.

## Plugin runtime (0.8)

The public SDK is `gw_supervisor.api`; core must not import `gw_builtin` or optional
feature implementations except explicit legacy import aliases. Reference plugins
live in `packages/gw-builtin`. Peer integration uses named services. Keep core
verdict precedence and session pinning intact. Preserve independent package builds,
agent tool registration, baseline/authority behavior and native denial on handled
configuration errors. See `docs/PLUGINS.md` and `tests/test_runtime_plugins.py`.
