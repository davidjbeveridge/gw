# Contributing to gW

[Project](README.md) · [Handbook](docs/README.md) · [Roadmap](docs/ROADMAP.md) · [Security reporting](SECURITY.md#reporting)

Useful contributions make a boundary clearer, a behavior more reliable, or a result easier to reproduce. A small verified adapter fix is more valuable than a broad compatibility claim.

## Work on a branch

Fork the repository, clone your fork, and create a branch. Use Python 3.10+ in an isolated environment. Install the core and, when needed, the independent knowledge package:

```bash
python -m pip install . ./packages/gw-builtin ./packages/gw-context ./packages/gw-knowledge
python -m unittest discover -s tests -v
python -m unittest discover -s packages/gw-knowledge/tests -v
```

The dependency-free core suite skips optional integrations when their packages are absent. Install `litellm`, `mcp>=1.12,<2`, and `jsonschema` for the corresponding tests. The CI jobs run those dependencies explicitly. The optional skipped tests are not proof of coverage.

## Keep changes inspectable

Describe the problem, the smallest reproducer, your change, and its limits. Include the gW/native-agent versions and whether the evidence came from fixtures, a real API exchange, or a live agent session. Redact private data without removing the structure needed to reproduce the issue.

Do not weaken old tests to make a new model or adapter appear supported. Do not change native permissions, add blanket approvals, or hide unsupported operations behind a permissive fallback. Keep network calls, model downloads, and persistent writes explicit.

Runtime behavior changes need tests and the relevant reference update. Documentation-only changes should not bump package versions or move released tags. Preserve existing documentation paths where possible; add a short redirecting page if a move is necessary.

## Native adapters

Supply realistic input/output fixtures, a harmless pre-execution denial, failure/unknown-outcome coverage, idempotent bootstrap, and uninstall behavior that preserves unrelated settings. State where advice and approvals cannot be represented. Do not infer all-tool coverage from one shell check.

## Knowledge adapters

Implement the [versioned contract](packages/gw-knowledge/ADAPTERS.md), advertise capabilities honestly, and reuse the conformance checks. Add backend-specific tests for isolation, changed permissions, newly added documents, expiration, updates, and errors. A revision token must cover everything the cache relies on, or be absent.

Keep the package extractable: no imports from `gw_supervisor`, no source links that require the surrounding repository for basic use, and no mandatory commercial backend. An optional vector engine should not turn keyword-only installations into paid or heavyweight ones.

## Documentation standard

Write for someone trying to complete a task or understand a decision. Start with the thing they need, explain the constraint, and show a working example. Prefer one authoritative reference page over slightly different copies of the same instructions.

Label fragments, templates, and counterexamples. Commands must exist; fields must match implementation; code blocks must parse. Explain what a successful check proves and what it does not. Never call an unexecuted example a test result. Keep planned features in the roadmap, not in an installation promise.

Use descriptive links and a navigable heading hierarchy. Avoid decorative badges, repeated slogans, unsupported superlatives, and claims that the prose is itself exceptional. A sentence earns its place by helping the reader.

Run the documentation tests and offline examples:

```bash
python -m unittest discover -s tests -p test_documentation.py -v
python examples/supervision_demo.py
python examples/knowledge_demo.py
```

The last example requires `gw-knowledge`. Both use temporary data and no model keys. Documentation tests check local links/anchors, JSON blocks, sample policies, and executable demonstrations; they do not certify external sites or all shell commands on every platform.

## Performance claims

Use [the benchmark protocol](docs/BENCHMARKS.md). Include failures, classifier overhead, versions, and raw/sanitized per-run evidence. Smaller inputs, faster unit tests, or another project's results are not gW savings measurements. Negative findings are useful.

## Before opening the pull request

Review the diff for secrets and unrelated changes. Run the relevant tests. Link the documentation or source contract supporting external behavior. Describe unfinished integration work plainly rather than implying it shipped. The project is MIT-licensed; dependencies and contributed artifacts must remain compatible with their own terms.

## Context adapters and dependency isolation

The compiler and context source protocols live in `packages/gw-context`, with no
mandatory dependencies. Test it on its own, then test core + context without
knowledge. The explicit fixture in `examples/context-source` is a real installable
entry point, not a bundled production provider. Do not introduce a compiler import
from a knowledge backend or a knowledge dependency into the context package.

Run `python -m unittest discover -s packages/gw-context/tests -v` and
`python -m unittest discover -s tests -p test_context_independence.py -v`.

## Runtime changes

Read [PLUGINS.md](docs/PLUGINS.md) before adding extension machinery. New plugins
import `gw_supervisor.api`, declare owned configuration/services/tools, and return
assessments rather than rewriting final verdicts. Do not import a peer's concrete
implementation. Keep ordinary helpers inside a domain.

Install core, `packages/gw-builtin` and the optional libraries used by your tests.
Install `examples/runtime-plugin` to run real discovery/agent-administration
integration tests. Run the kernel-only suite without the reference distribution;
a full installation alone cannot prove separation. Keep legacy behavior tests and
add negative authority, collision, stale-manifest and cleanup tests as appropriate.
