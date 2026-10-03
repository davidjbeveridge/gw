# An installed source, without gw-knowledge

This is an offline fixture, not a production knowledge provider. From the
repository root:

```bash
python -m pip install . ./packages/gw-context ./examples/context-source
python -m unittest discover -s tests -p test_context_independence.py -v
```

It installs an actual `gw_context.sources` entry point named `fixture`. The
acceptance test opens a fresh isolated interpreter, rejects all knowledge-package
imports, discovers and configures this source through the existing agent service,
and combines its evidence with project context. No knowledge directory is created.

Normal GW installers do **not** install this fixture. Real providers implement the
same [source contract](../../packages/gw-context/ADAPTERS.md) with their own access,
freshness and network behavior. The fixture supports `text` and `revision` options
so tests can vary evidence without invoking a service or model.
