# Runnable examples

[Handbook](../docs/README.md) · [Recipes](../docs/RECIPES.md) · [Contributing](../CONTRIBUTING.md)

These examples use temporary directories, fixture events, and no model keys. They demonstrate library behavior; they do not launch a licensed agent or establish classifier accuracy. Run them from an installed checkout:

```bash
python -m pip install . ./packages/gw-knowledge
python examples/supervision_demo.py
python examples/knowledge_demo.py
```

Both print compact JSON summaries and exit nonzero if an expected invariant fails. The temporary source/config/cache files are removed when the process exits.

## Supervision without a model

[supervision_demo.py](supervision_demo.py) creates a private temporary policy, evaluates a matched denial, verifies duplicate-event handling, supplies two **fixture** failure outcomes, and confirms the next same-action attempt requires review. It does not run the shell commands named in those events.

Expected summary:

```json
{"canary":"deny","duplicate":true,"retry":"approve","events":5}
```

This demonstrates policy/state evaluation. To test a real native integration, run the [installation canary](../docs/GETTING_STARTED.md#prove-that-the-hook-runs) separately.

## Context reuse with source invalidation

[knowledge_demo.py](knowledge_demo.py) creates a source, assembles context, verifies a cache hit, adds a new relevant document, then verifies a miss with both documents present. Finally it clears the cache and proves the original source remains readable.

Expected summary:

```json
{"first_hit":false,"second_hit":true,"after_addition_hit":false,"documents":["architecture","operations"],"source_survives_eviction":true}
```

The example requires the independent `gw-knowledge` package, not an embedding model or managed service. It does not re-ingest changed files automatically.

## Policy fragments

[policies/coding.json](policies/coding.json) adjusts semantic error handling and exact retry limits. It requires an enabled classifier for semantic decisions; the fragment does not configure one.

[policies/submission-review.json](policies/submission-review.json) requires review for a semantic operation supplied by a custom host. Native mouse coordinates alone will not match it. The executor must bind `operation` to the actual action.

[policies/observe.json](policies/observe.json) softens local blocking decisions for evaluation. External authority still applies. None of these files should replace an existing global configuration blindly.

## What is deliberately absent

No example contains live credentials, silently downloads a model, submits an external form, grants standing authorization, or rewrites a vendor refusal. No fixture result is labeled a benchmark. Copy the smallest relevant part into a reviewed configuration and verify it in your own host.
