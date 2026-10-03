# GW reference plugins

`gw-builtin` supplies the standard behavior for the small GW runtime. It is an
independent MIT distribution, not an implementation hidden inside `gw-supervisor`.
One installation ships twelve separately replaceable plugin registrations.

The bundle includes state, policy, inference, governance, context, knowledge,
observability, learning, sync, harness integration, model gateways and agent
controls. Their interfaces are defined by `gw_supervisor.api` version 1. Ordinary
helpers are modules within those domains, not additional plugins.

## Install

The normal GW installer includes this bundle automatically. From a repository
checkout:

```bash
python -m pip install . ./packages/gw-builtin
```

From this directory, with a compatible core already installed:

```bash
python -m pip install .
```

Release assets include a wheel and an independently buildable source archive.
No PyPI publication is implied. Python 3.10+ is required. The compatible core range
is declared in this package's metadata; the libraries behind optional features
are installed separately.

`gw-context`, `gw-knowledge`, `gw-observe`, `gw-learning`, and `gw-sync` remain
standalone libraries. The reference registrations adapt those libraries into GW;
they do not force a commercial provider or a new mandatory cloud connection.
Selecting a bridge does not by itself enable its backend or launch any process.

## Inspect and replace

The agent can use `gw_runtime_inspect` or `gw_setup_options`. The corresponding
operator command is `gw runtime inspect`; `gw plugins` also shows installed
entry-point distributions. Replacing a domain means disabling its plugin ID and
enabling an installed replacement with the same consumed service contract.

Factories in `registration.py` declare configuration ownership, dependencies,
services, evaluators, commands and agent tools. Service facades in `services.py`
resolve implementation methods lazily. Peer calls go through the runtime's service
interfaces. The shared legacy CLI parser preserves established command syntax;
new plugins register commands and tools without editing that parser.

The actual scope, migration rules, authoring example, service protocols, error
semantics and deployment boundaries are documented in the
[runtime plugin guide](https://github.com/davidjbeveridge/gw/blob/main/docs/PLUGINS.md).
The [extension example](https://github.com/davidjbeveridge/gw/tree/main/examples/runtime-plugin)
imports only the public SDK and is installed in CI as a separate distribution.

## Compatibility

Existing feature-module imports under `gw_supervisor` are lazy compatibility
aliases to this bundle. They require this distribution. New extensions must use
`gw_supervisor.api`, not those aliases or another reference plugin's private
modules. The substantial standalone library packages have their own contracts.

Configuration names and stored data are retained. Start fresh agent sessions after
migration to establish a plugin manifest; old session records remain available
for inspection. There is no live migration of an old session's authority, no
implicit permission grant and no automatic installation of generated plugin code.
