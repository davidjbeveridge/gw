# gW v0.7.0 — context independent of knowledge

`gw-context` 0.1.0 is an independent MIT package containing the compiler, context
items, validation, exact chunking, and context-source interfaces. It imports no GW,
knowledge backend or SQLite. The agent tool remains `gw_context_compile`.

GW can combine project/session/skill evidence with several explicitly configured
third-party context sources without installing `gw-knowledge`. The existing
knowledge integration remains optional and retains its source-backed retrieval
cache. Whole compiled packets are not persistently cached.

Agent-tools installation now includes `gw-context`; `--context`/`-Context` installs
it separately. `--knowledge`/`-Knowledge` still installs the combined experience.
`gw-knowledge` 0.3.0 retains optional historical compiler import aliases but no
longer loads the compiler during normal knowledge imports.

Source adapters are installed entry points, not worktree imports. The host checks
scope, namespaces source identities, records failures, and rejects source-authored
mandatory instructions. Errors stop compilation unless explicit omission is
configured. Logging and the reference compiler require no inference; external
source costs and latency belong to their adapters.

Release gates include the existing OS/Python/MCP/proxy/browser tests, standalone
package extraction, and new core-plus-context installations without knowledge.
The external source example is an offline fixture; no live vendor integration,
retrieval-quality improvement or savings benchmark is claimed.
