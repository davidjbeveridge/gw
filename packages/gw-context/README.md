# gw-context

**Compile context without choosing a knowledge platform.**

`gw-context` is an independent MIT package for Python 3.10+. Its default compiler
has no runtime dependencies, model calls, database, provider credentials, or
imports from GW or `gw-knowledge`. Install this directory with
`python -m pip install .`; release assets include its wheel and source archive.
No PyPI publication is implied.

## Compile supplied evidence

```python
from gw_context import ContextItem, DeterministicContextCompiler

packet = DeterministicContextCompiler().compile(
    "Fix the parser and add a regression test",
    [ContextItem(
        id="testing-guidance", kind="skill", content="Use fixture data, not production.",
        source="project:SKILL.md", revision="reviewed-v1", required=True,
    )],
    query="parser regression", max_chars=4000, scope="my-project/principal",
)
print(packet["text"])
```

The output is a `gw.context/1` packet with selected source identities/revisions,
exact character ranges, omissions, budget accounting, and a content-derived ID.
The optional scope participates in that ID. Task and required items are retained
whole; insufficient mandatory budget raises `ContextBudgetExceeded`. Optional
items are ordered by priority, lexical overlap, and stable source identifiers.
Conflicting revisions are rejected and identical source ranges are deduplicated.

The budget covers Unicode characters in the serialized packet, **not model
tokens or the worker's entire existing prompt**. No arbitrary transcript rewriting,
semantic ranking guarantee, tool-schema pruning or generated summary is implied.

## Bring your own sources

`ContextSource.collect(ContextRequest) -> SourceResult` is a separate contract for
retrieval. A caller may supply one source, several sources, or no provider at all.
The compiler only consumes typed items; it does not instantiate or run providers.
A host may load explicitly configured installed `gw_context.sources` entry points.

See [ADAPTERS.md](ADAPTERS.md) for a complete implementation, error behavior, scope,
trust and packaging. Sources must return authorized evidence, not mandatory host
instructions. Network/model work performed by a source is outside the deterministic
compiler's `model_calls` counter and must be measured separately.

## Ownership and caching

Providers own authoritative content, indexes and retrieval caches. This package
currently owns no persistent cache: it assembles complete packets on demand. A
future final-packet cache belongs at this layer and must include access scope,
source revisions, task/history, compiler settings and the target budget. A cached
retrieval result is not a cached complete agent context.

GW core supplies task/policy, project files and session evidence, then delivers
the packet through its unchanged `gw_context_compile` tool or an opt-in integration.
That host adapter can use `gw-knowledge` for retrieval, but the dependency is not
required by this package or by third-party sources.

## Test or extract

```bash
python -m unittest discover -s tests -v
```

The tests exercise pure compilation, source validation, Unicode ranges, and fresh
processes that reject knowledge/harness/database imports. This directory can be
copied to another repository and built unchanged. Integration and setup guide:
https://github.com/davidjbeveridge/gw/blob/main/docs/CONTEXT_COMPILER.md.
