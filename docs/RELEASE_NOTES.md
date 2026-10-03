# GW v0.8.0 — domain plugins, small runtime

The standard behavior is now a separate `gw-builtin` 0.1.0 distribution with twelve
replaceable registrations. Core retains configuration, discovery/lifecycle,
session identities, verdict reduction and a generic command host. Independent
context, knowledge, observation, learning and sync packages remain independent.

Plugin API v1 supports owned configuration, lazy named services, ordered evaluators,
commands, project-bound agent tools, namespaced state and non-authoritative
observations. Installed entry points do not activate unless selected. API/ownership/
dependency conflicts fail explicitly; authority precedence remains in core.

The installer includes the reference bundle automatically. Existing commands and
configuration fields remain; old Python feature imports are compatibility aliases.
Start fresh native sessions after upgrading, and restart GW MCP after composition
changes. No old session is silently migrated to a new plugin graph.

The agent can inspect `gw_runtime_inspect` and prepare reviewed changes to installed
plugin selection and explicitly editable configuration. No automatic package
installation, credential discovery, permission grant, background worker or cloud
service was added.

Validation includes isolated core-only installations, an independently built
reference bundle, an installed SDK-only example extension, cross-platform
regressions, native installers, real MCP exchanges, LiteLLM and browser tests.
These are implementation checks, not task-quality or cost-savings benchmarks.

See docs/PLUGINS.md for architecture, API, examples, migration and failure limits.
