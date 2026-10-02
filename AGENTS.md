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
