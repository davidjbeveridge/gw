# gW v0.6.0 — agent tools, decision cascades and context compilation

The agent can operate GW through a host-bound MCP interface: inspect runs, open
the local dashboard, prepare/apply requested setup, check decision backends,
select models and retrieve compiled context. Native approval remains unchanged.

Decision strategies now support a bounded primary/fallback cascade or one
compatible adaptive endpoint. Every stage keeps its latency/usage; no recursive
reasoning rescue or permission override is introduced.

The independent gw-knowledge 0.2.0 compiler assembles exact project, task, skill,
outcome and knowledge evidence. Required content is retained whole or fails the
budget check. Optional omissions and provenance are inspectable. Automatic
proxy/supervisor delivery is opt-in; baseline and opaque provider state remain
unchanged. gw-observe 0.2.0 displays compilation activity and source relationships.

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.6.0/install.sh | bash -s -- --all --agent-tools --plugins --knowledge
```

No specific Glide endpoint, universal vendor-runtime coverage, paid-provider
accuracy, or cost/quality improvement is claimed. Tests use fixtures, real MCP
stdio, local HTTP services, isolated packaging and the existing cross-platform
suite. See the agent, decision cascade, and context compiler guides.
